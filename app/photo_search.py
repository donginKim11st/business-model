"""네이버 이미지 검색 + 원본 이미지 안전 fetch. DB·LLM 무관.

fetch_as_data_uri 방어(리뷰 반영):
- 호스트 allowlist(네이버 이미지 CDN만) → 오픈프록시/SSRF 리바인딩을 실질 차단
  (임의 도메인을 못 넣으므로 공격자 DNS 리바인딩 벡터가 닫힘).
- http/https·80/443 포트만.
- DNS 해석 후 모든 IP가 공인인지 검사(사설/루프백/링크로컬/예약/멀티캐스트/CGNAT/ipv4-mapped 차단).
- 스트리밍으로 8MB 상한(무제한/청크 응답 OOM 방지, Content-Length 미신뢰).
- content-type 정확 화이트리스트(공격자 제어 헤더의 XSS 차단).
"""
import base64
import ipaddress
import socket
from urllib.parse import urlparse

from config import settings


class PhotoSearchError(Exception):
    pass


_NAVER_IMAGE_URL = "https://openapi.naver.com/v1/search/image"
_MAX_IMG = 8 * 1024 * 1024
_TIMEOUT = 10
_ALLOWED_HOST_SUFFIXES = (".naver.net", ".pstatic.net")   # 네이버 이미지 CDN
_ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
_ALLOWED_PORTS = {None, 80, 443}
_CGNAT = ipaddress.ip_network("100.64.0.0/10")


def _http(client):
    if client is not None:
        return client
    import httpx
    return httpx


def search(query, n=9, client=None):
    """상품명 query → [{'thumbnail':..., 'link':...}] (최대 n, link 있는 것만)."""
    if not (settings.naver_client_id and settings.naver_client_secret):
        raise PhotoSearchError("네이버 API 키가 설정되지 않았습니다. .env에 NAVER_CLIENT_ID/NAVER_CLIENT_SECRET을 추가하세요.")
    q = (query or "").strip()
    if not q:
        raise PhotoSearchError("검색어가 비어 있습니다.")
    n = max(1, min(int(n), 20))
    headers = {
        "X-Naver-Client-Id": settings.naver_client_id,
        "X-Naver-Client-Secret": settings.naver_client_secret,
    }
    params = {"query": q, "display": n, "sort": "sim", "filter": "large"}
    try:
        resp = _http(client).get(_NAVER_IMAGE_URL, headers=headers, params=params, timeout=_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, dict):
            raise PhotoSearchError("예상치 못한 응답 형식")
        items = data.get("items") or []
        out = [{"thumbnail": it.get("thumbnail"), "link": it.get("link")}
               for it in items if isinstance(it, dict) and it.get("link")]
    except PhotoSearchError:
        raise
    except Exception as e:
        raise PhotoSearchError(f"네이버 이미지검색 실패: {e}") from e
    return out[:n]


def _ip_blocked(ip_str):
    """해석된 IP가 접근 금지 대역인지. ipv4-mapped 정규화 후 판정."""
    ip = ipaddress.ip_address(ip_str)
    mapped = getattr(ip, "ipv4_mapped", None)
    if mapped is not None:
        ip = mapped
    return (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
            or ip.is_multicast or ip.is_unspecified or ip in _CGNAT)


def _guard_url(url):
    """SSRF/오픈프록시 방어: 네이버 CDN 호스트 + http(s)/허용포트 + 모든 해석 IP 공인."""
    p = urlparse(url or "")
    if p.scheme not in ("http", "https"):
        raise PhotoSearchError("http/https 이미지 URL만 허용됩니다.")
    host = (p.hostname or "").lower()
    if not host:
        raise PhotoSearchError("잘못된 이미지 URL입니다.")
    if not any(host == s[1:] or host.endswith(s) for s in _ALLOWED_HOST_SUFFIXES):
        raise PhotoSearchError("허용되지 않은 이미지 출처입니다.")
    try:
        port = p.port
    except ValueError as e:
        raise PhotoSearchError("잘못된 포트입니다.") from e
    if port not in _ALLOWED_PORTS:
        raise PhotoSearchError("허용되지 않은 포트입니다.")
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError as e:
        raise PhotoSearchError(f"호스트를 해석할 수 없습니다: {host}") from e
    for info in infos:
        if _ip_blocked(info[4][0]):
            raise PhotoSearchError("허용되지 않은 대상(내부 네트워크)입니다.")


def fetch_as_data_uri(url, client=None):
    """추천 이미지 URL → data URI. 가드 통과 후 스트리밍으로 8MB 상한·형식 검증. 실패 시 PhotoSearchError."""
    _guard_url(url)
    hclient = client
    close = False
    if hclient is None:
        import httpx
        hclient = httpx.Client(timeout=_TIMEOUT, follow_redirects=False)
        close = True
    try:
        with hclient.stream("GET", url) as resp:
            resp.raise_for_status()
            ctype = (resp.headers.get("content-type") or "").split(";")[0].strip().lower()
            if ctype == "image/jpg":
                ctype = "image/jpeg"
            if ctype not in _ALLOWED_TYPES:
                raise PhotoSearchError("지원하지 않는 이미지 형식입니다.")
            buf = bytearray()
            for chunk in resp.iter_bytes():
                buf += chunk
                if len(buf) > _MAX_IMG:                     # Content-Length 미신뢰, 실제 바이트로 캡
                    raise PhotoSearchError("8MB 이하 이미지만 가능합니다.")
    except PhotoSearchError:
        raise
    except Exception as e:
        raise PhotoSearchError(f"이미지 다운로드 실패: {e}") from e
    finally:
        if close:
            hclient.close()
    return f"data:{ctype};base64,{base64.b64encode(bytes(buf)).decode()}"

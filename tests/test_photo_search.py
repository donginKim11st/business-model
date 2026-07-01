import base64
import pytest
from app import photo_search

NAVER = "https://shop1.phinf.naver.net/x.png"   # allowlist 통과 호스트


# ---- 검색용 페이크(.get) ----
class _Resp:
    def __init__(self, *, json_data=None, status=200):
        self._json = json_data
        self.status_code = status

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


class _FakeGet:
    def __init__(self, resp):
        self._resp = resp
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self._resp


# ---- fetch용 페이크(.stream) ----
class _StreamResp:
    def __init__(self, chunks=(b"",), headers=None, status=200):
        self._chunks = list(chunks)
        self.headers = headers or {}
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")

    def iter_bytes(self):
        for c in self._chunks:
            yield c


class _FakeStream:
    def __init__(self, resp):
        self._resp = resp
        self.calls = []

    def stream(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        outer = self._resp

        class _Ctx:
            def __enter__(self):
                return outer

            def __exit__(self, *a):
                return False

        return _Ctx()


def _keys(monkeypatch, cid="id", sec="sec"):
    monkeypatch.setattr(photo_search.settings, "naver_client_id", cid)
    monkeypatch.setattr(photo_search.settings, "naver_client_secret", sec)


def _dns(monkeypatch, ip="1.2.3.4"):
    monkeypatch.setattr(photo_search.socket, "getaddrinfo",
                        lambda host, *a, **k: [(2, 1, 6, "", (ip, 0))])


# ---- search ----
def test_search_parses_items_and_sends_auth(monkeypatch):
    _keys(monkeypatch)
    fake = _FakeGet(_Resp(json_data={"items": [
        {"thumbnail": "https://t/1", "link": "https://i/1.jpg"},
        {"thumbnail": "https://t/2", "link": "https://i/2.jpg"},
    ]}))
    out = photo_search.search("삼다수", n=9, client=fake)
    assert out == [{"thumbnail": "https://t/1", "link": "https://i/1.jpg"},
                   {"thumbnail": "https://t/2", "link": "https://i/2.jpg"}]
    url, kw = fake.calls[0]
    assert "naver" in url
    assert kw["headers"]["X-Naver-Client-Id"] == "id"
    assert kw["params"]["query"] == "삼다수"


def test_search_skips_items_without_link(monkeypatch):
    _keys(monkeypatch)
    fake = _FakeGet(_Resp(json_data={"items": [
        {"thumbnail": "https://t/1"},
        {"thumbnail": "https://t/2", "link": "https://i/2.jpg"},
    ]}))
    assert photo_search.search("x", client=fake) == [{"thumbnail": "https://t/2", "link": "https://i/2.jpg"}]


def test_search_missing_keys_raises_clear(monkeypatch):
    _keys(monkeypatch, "", "")
    with pytest.raises(photo_search.PhotoSearchError, match="네이버 API 키"):
        photo_search.search("x")


def test_search_empty_query_raises(monkeypatch):
    _keys(monkeypatch)
    with pytest.raises(photo_search.PhotoSearchError):
        photo_search.search("   ", client=_FakeGet(_Resp(json_data={"items": []})))


def test_search_limits_n(monkeypatch):
    _keys(monkeypatch)
    items = [{"thumbnail": f"https://t/{i}", "link": f"https://i/{i}.jpg"} for i in range(20)]
    assert len(photo_search.search("x", n=6, client=_FakeGet(_Resp(json_data={"items": items})))) == 6


def test_search_api_failure_wrapped(monkeypatch):
    _keys(monkeypatch)
    with pytest.raises(photo_search.PhotoSearchError):
        photo_search.search("x", client=_FakeGet(_Resp(status=401)))


def test_search_non_dict_json_wrapped(monkeypatch):
    _keys(monkeypatch)
    with pytest.raises(photo_search.PhotoSearchError):
        photo_search.search("x", client=_FakeGet(_Resp(json_data=["not", "dict"])))


# ---- fetch: 정상/형식 ----
def test_fetch_ok_https(monkeypatch):
    _dns(monkeypatch)
    png = b"\x89PNG\r\n\x1a\n" + b"x" * 20
    out = photo_search.fetch_as_data_uri(NAVER, client=_FakeStream(
        _StreamResp(chunks=[png[:8], png[8:]], headers={"content-type": "image/png"})))
    assert out.startswith("data:image/png;base64,")
    assert base64.b64decode(out.split(",", 1)[1]) == png


def test_fetch_allows_http_scheme(monkeypatch):
    _dns(monkeypatch)
    out = photo_search.fetch_as_data_uri(
        "http://shop1.phinf.naver.net/a.png",                 # 네이버 CDN은 http 서빙 → 허용돼야 함
        client=_FakeStream(_StreamResp(chunks=[b"\x89PNGdata"], headers={"content-type": "image/png"})))
    assert out.startswith("data:image/png;base64,")


def test_fetch_normalizes_jpg(monkeypatch):
    _dns(monkeypatch)
    out = photo_search.fetch_as_data_uri(NAVER, client=_FakeStream(
        _StreamResp(chunks=[b"jpgdata"], headers={"content-type": "image/jpg"})))
    assert out.startswith("data:image/jpeg;base64,")


def test_fetch_rejects_non_image(monkeypatch):
    _dns(monkeypatch)
    with pytest.raises(photo_search.PhotoSearchError, match="형식"):
        photo_search.fetch_as_data_uri(NAVER, client=_FakeStream(
            _StreamResp(chunks=[b"<html>"], headers={"content-type": "text/html"})))


def test_fetch_rejects_xss_content_type(monkeypatch):
    _dns(monkeypatch)
    evil = 'image/png"><img src=x onerror=alert(1)>'          # startswith(image/)지만 화이트리스트 밖
    with pytest.raises(photo_search.PhotoSearchError):
        photo_search.fetch_as_data_uri(NAVER, client=_FakeStream(
            _StreamResp(chunks=[b"x"], headers={"content-type": evil})))


# ---- fetch: 크기 캡(스트리밍, Content-Length 미신뢰) ----
def test_fetch_streaming_cap_ignores_content_length(monkeypatch):
    _dns(monkeypatch)
    big = [b"x" * (4 * 1024 * 1024)] * 3                       # 12MB 스트림
    with pytest.raises(photo_search.PhotoSearchError, match="8MB"):
        photo_search.fetch_as_data_uri(NAVER, client=_FakeStream(
            _StreamResp(chunks=big, headers={"content-type": "image/png", "content-length": "10"})))


def test_fetch_size_boundary_exact_8mb_ok(monkeypatch):
    _dns(monkeypatch)
    exact = b"\x89PNG" + b"x" * (8 * 1024 * 1024 - 4)          # 정확히 8MB
    out = photo_search.fetch_as_data_uri(NAVER, client=_FakeStream(
        _StreamResp(chunks=[exact], headers={"content-type": "image/png"})))
    assert base64.b64decode(out.split(",", 1)[1]) == exact


# ---- fetch: 가드(SSRF/오픈프록시) ----
def test_fetch_rejects_dangerous_scheme():
    for bad in ("file:///etc/passwd", "ftp://shop1.phinf.naver.net/a", "gopher://x/1"):
        with pytest.raises(photo_search.PhotoSearchError):
            photo_search.fetch_as_data_uri(bad)


def test_fetch_rejects_non_naver_host():
    with pytest.raises(photo_search.PhotoSearchError, match="출처"):
        photo_search.fetch_as_data_uri("https://evil.com/a.png")
    with pytest.raises(photo_search.PhotoSearchError, match="출처"):
        photo_search.fetch_as_data_uri("https://evilnaver.net/a.png")   # 접미사 위장 차단


def test_fetch_rejects_bad_port():
    with pytest.raises(photo_search.PhotoSearchError, match="포트"):
        photo_search.fetch_as_data_uri("https://shop1.phinf.naver.net:22/a.png")


def test_fetch_blocks_private_cgnat_and_metadata(monkeypatch):
    for ip in ("127.0.0.1", "10.0.0.5", "192.168.0.1", "169.254.169.254", "100.64.0.1"):
        _dns(monkeypatch, ip)                                 # 네이버 호스트라도 IP가 내부면 차단
        with pytest.raises(photo_search.PhotoSearchError, match="내부 네트워크"):
            photo_search.fetch_as_data_uri(NAVER)


def test_fetch_dns_failure_wrapped(monkeypatch):
    def _boom(*a, **k):
        raise OSError("no such host")
    monkeypatch.setattr(photo_search.socket, "getaddrinfo", _boom)
    with pytest.raises(photo_search.PhotoSearchError, match="해석할 수 없"):
        photo_search.fetch_as_data_uri(NAVER)

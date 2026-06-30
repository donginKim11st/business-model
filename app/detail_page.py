"""view + draft → self-contained 편집형 PDP 상세페이지 HTML. DB·LLM·IO 무관 순수.

업로드 이미지가 있으면 그 대표 색에 맞춰 PDP 배경 팔레트를 자동 생성하고,
없으면 category_l1 기반 테마 팔레트를 쓴다.
"""
import base64
import colorsys
import io
import pathlib
from jinja2 import Environment, FileSystemLoader, select_autoescape

_TEMPLATES = pathlib.Path(__file__).parent / "templates"
_env = Environment(loader=FileSystemLoader(str(_TEMPLATES)),
                   autoescape=select_autoescape(["html"]))

# 카테고리별 PDP 테마 팔레트 (이미지 없을 때 폴백).
_THEMES = {
    "food":    {"bg": "#eef6ec", "panel": "#f7fbf4", "soft": "#e2efdd", "primary": "#3f9d4f", "ink": "#1f3a25", "on": "#ffffff"},
    "beauty":  {"bg": "#fbedf1", "panel": "#fdf5f7", "soft": "#f6e0e8", "primary": "#df5d86", "ink": "#46202f", "on": "#ffffff"},
    "tech":    {"bg": "#eef1f7", "panel": "#f5f7fc", "soft": "#e2e8f4", "primary": "#3b6fd4", "ink": "#1d2a44", "on": "#ffffff"},
    "fashion": {"bg": "#f1efea", "panel": "#faf8f4", "soft": "#e9e4db", "primary": "#1f1d1b", "ink": "#1f1d1b", "on": "#ffffff"},
    "default": {"bg": "#f4efe9", "panel": "#fcf8f2", "soft": "#f3e6da", "primary": "#ff5a1f", "ink": "#2a2018", "on": "#ffffff"},
}


def _theme(category_l1):
    """category_l1 문자열 → 테마 팔레트 dict (매칭 없으면 default)."""
    c = category_l1 or ""

    def has(*ks):
        return any(k in c for k in ks)

    if has("식품", "라면", "면", "밥", "국", "밀키트", "간식", "음료", "커피", "건강식", "과자", "즉석", "차"):
        return _THEMES["food"]
    if has("뷰티", "화장", "스킨", "미용", "향수", "바디", "헤어", "코스메", "마스크"):
        return _THEMES["beauty"]
    if has("가전", "전자", "디지털", "컴퓨터", "노트북", "폰", "음향", "가구", "주방가전"):
        return _THEMES["tech"]
    if has("의류", "패션", "신발", "잡화", "액세서리", "가방", "속옷"):
        return _THEMES["fashion"]
    return _THEMES["default"]


def _hex(rgb):
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(round(c)))) for c in rgb)


def _mix_white(rgb, f):
    """rgb 를 흰색 쪽으로 f(0~1)만큼 섞음 (틴트)."""
    return tuple(c + (255 - c) * f for c in rgb)


def _dominant_rgb(image_data_uri):
    """data URI 이미지 → 대표(빈도×채도 가중) 색 RGB. 디코드 실패 시 None."""
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        b64 = (image_data_uri or "").split(",", 1)[1]
        img = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")
        img.thumbnail((96, 96))
        q = img.quantize(colors=8)
        pal = q.getpalette()
        counts = q.getcolors() or []          # [(count, palette_index), ...]
        best, best_score = None, -1
        for count, idx in counts:
            r, g, b = pal[idx * 3:idx * 3 + 3]
            mx, mn = max(r, g, b), min(r, g, b)
            if mx > 240 or mx < 30:           # 거의 흰/검 제외
                continue
            score = count * ((mx - mn) + 12)  # 빈도 × (채도+여유)
            if score > best_score:
                best, best_score = (r, g, b), score
        if best is None and counts:           # 전부 흰/검이면 최빈색 폴백
            idx = max(counts)[1]
            best = tuple(pal[idx * 3:idx * 3 + 3])
        return best
    except Exception:
        return None


def _palette_from_rgb(rgb):
    """대표색 → PDP 팔레트. primary 는 흰 글씨 대비 위해 명도 상한·채도 하한 보정."""
    h, l, s = colorsys.rgb_to_hls(*(c / 255.0 for c in rgb))
    s = max(s, 0.4)                            # 무채색이면 채도 보강
    l = min(l, 0.46)                           # primary: 흰 글씨 대비 위해 충분히 진하게
    primary = tuple(c * 255 for c in colorsys.hls_to_rgb(h, l, s))
    return {
        "bg": _hex(_mix_white(primary, 0.88)),
        "panel": _hex(_mix_white(primary, 0.96)),
        "soft": _hex(_mix_white(primary, 0.78)),
        "primary": _hex(primary),
        "ink": _hex(tuple(c * 0.5 for c in primary)),
        "on": "#ffffff",
    }


def build_html(view, draft, image_data_uri=None):
    """편집형 PDP HTML 문자열.

    image_data_uri 있으면 그 대표 색으로 팔레트를 만들어 배경을 맞추고,
    없으면(또는 색 추출 실패 시) category 테마로 폴백. None → 사진 슬롯 플레이스홀더.
    """
    view = view or {}
    theme = _theme(view.get("category_l1"))
    if image_data_uri:
        rgb = _dominant_rgb(image_data_uri)
        if rgb:
            theme = _palette_from_rgb(rgb)
    return _env.get_template("detail_page.html").render(
        v=view, d=draft or {}, image=image_data_uri, theme=theme)

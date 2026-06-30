"""view + draft → self-contained 편집형 PDP 상세페이지 HTML. DB·LLM·IO 무관 순수.

업로드 이미지가 있으면 그 대표 색에 맞춰 PDP 배경 팔레트를 자동 생성하고,
없으면 category_l1 기반 테마 팔레트를 쓴다.
"""
import base64
import colorsys
import functools
import io
import pathlib
from jinja2 import Environment, FileSystemLoader, select_autoescape

_TEMPLATES = pathlib.Path(__file__).parent / "templates"
_env = Environment(loader=FileSystemLoader(str(_TEMPLATES)),
                   autoescape=select_autoescape(["html"]))

# 스타일 → 템플릿. minimal=시스템폰트 기존 레이아웃, airy/contrast=Pretendard 에디토리얼.
_TEMPLATE_BY_STYLE = {
    "minimal": "detail_page.html",
    "airy": "detail_editorial.html",
    "contrast": "detail_editorial.html",
}
STYLES = tuple(_TEMPLATE_BY_STYLE)
_FONT = pathlib.Path(__file__).parent / "static" / "fonts" / "PretendardVariable.woff2"


@functools.lru_cache(maxsize=1)
def _font_css():
    """Pretendard variable woff2 → @font-face(data URI). 폰트 부재 시 빈 문자열(시스템폰트 폴백)."""
    try:
        b64 = base64.b64encode(_FONT.read_bytes()).decode()
    except OSError:
        return ""
    return ("@font-face{font-family:Pretendard;font-weight:45 920;font-style:normal;"
            "font-display:block;src:url(data:font/woff2;base64,%s) format('woff2')}" % b64)

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


SLOTS = (
    {"key": "hero",   "label": "히어로", "role": "상단 대표컷 · 페이지 배경색의 기준"},
    {"key": "detail", "label": "디테일", "role": "소재·질감 클로즈업"},
    {"key": "usage",  "label": "사용씬", "role": "실사용·연출 컷"},
    {"key": "sub",    "label": "보조",   "role": "추가 각도·패키지"},
)


def build_html(view, draft, images=None, style="contrast"):
    """흰색 적응형 PDP HTML. images = {slot_key: data_uri}. 히어로 있으면 그 색으로 액센트.

    style: 'contrast'(기본·톤 교차 에디토리얼)·'airy'(밝은 에디토리얼) | 'minimal'(기존 시스템폰트).
    알 수 없으면 ValueError.
    """
    if style not in _TEMPLATE_BY_STYLE:
        raise ValueError(f"unknown style: {style!r} (allowed: {', '.join(STYLES)})")
    view = view or {}
    images = images or {}
    hero = images.get("hero")
    if hero:
        rgb = _dominant_rgb(hero)
        theme = _palette_from_rgb(rgb) if rgb else _theme(view.get("category_l1"))
    else:
        theme = _theme(view.get("category_l1"))
    font_css = "" if style == "minimal" else _font_css()
    return _env.get_template(_TEMPLATE_BY_STYLE[style]).render(
        v=view, d=draft or {}, images=images, theme=theme,
        style=style, numbered=(style == "contrast"), font_css=font_css)

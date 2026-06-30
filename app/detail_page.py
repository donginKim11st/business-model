"""view + draft → self-contained 편집형 PDP 상세페이지 HTML. DB·LLM·IO 무관 순수."""
import pathlib
from jinja2 import Environment, FileSystemLoader, select_autoescape

_TEMPLATES = pathlib.Path(__file__).parent / "templates"
_env = Environment(loader=FileSystemLoader(str(_TEMPLATES)),
                   autoescape=select_autoescape(["html"]))

# 카테고리별 PDP 테마 팔레트 (풀블리드 편집형 패널 색).
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


def build_html(view, draft, image_data_uri=None):
    """편집형 PDP HTML 문자열. image_data_uri None → 사진 슬롯 플레이스홀더."""
    view = view or {}
    return _env.get_template("detail_page.html").render(
        v=view, d=draft or {}, image=image_data_uri, theme=_theme(view.get("category_l1")))

"""view + draft → self-contained 상세페이지 HTML. DB·LLM·IO 무관 순수."""
import pathlib
from jinja2 import Environment, FileSystemLoader, select_autoescape

_TEMPLATES = pathlib.Path(__file__).parent / "templates"
_env = Environment(loader=FileSystemLoader(str(_TEMPLATES)),
                   autoescape=select_autoescape(["html"]))


def build_html(view, draft, image_data_uri=None):
    """상세페이지 HTML 문자열. image_data_uri None → 사진 슬롯 플레이스홀더."""
    return _env.get_template("detail_page.html").render(
        v=view or {}, d=draft or {}, image=image_data_uri)

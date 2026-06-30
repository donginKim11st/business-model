import json
import pathlib
from app.insight import build_view
from app import detail_page

FIX = pathlib.Path(__file__).parent / "fixtures"
VIEW = build_view(json.loads((FIX / "product_full.json").read_text(encoding="utf-8")))
DRAFT = {
    "titles": ["건강한 한 끼, 쿡시 사골 미역국 쌀국수", "글루텐프리로 안심하고 즐기는 국물 면", "따뜻한 국물로 추운 날씨를 이겨내세요"],
    "selling_points": [
        {"text": "글루텐프리와 높은 쌀 함량으로 건강한 식사", "sources": ["naver"]},
        {"text": "간편한 조리법으로 누구나 쉽게", "sources": ["naver"]},
    ],
    "target_copy": "아이와 어른 모두가 즐길 수 있는 건강한 한 끼.",
    "faqs": [{"q": "글루텐이 있나요?", "a": "아니요, 글루텐프리입니다."}],
    "spec_highlights": ["글루텐프리", "높은 쌀 함량"],
    "price_positioning": "최저 21,060원으로 합리적입니다.",
}


def _solid_uri(rgb):
    import base64
    import io
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), rgb).save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def test_no_images_uses_category_theme_and_placeholders():
    html = detail_page.build_html(VIEW, DRAFT, None)
    assert "건강한 한 끼" in html                     # 헤드라인
    assert "글루텐프리와 높은 쌀 함량으로 건강한 식사" in html   # 셀링포인트
    assert "#3f9d4f" in html                          # 식품(라면/면류) 카테고리 그린 액센트
    assert "대표 이미지 영역" in html                 # 히어로 플레이스홀더
    assert "<img" not in html                         # 이미지 없음


def test_design_omits_numbers_and_source_phrases():
    html = detail_page.build_html(VIEW, DRAFT, None)
    assert "네이버" not in html                       # 데이터 출처(플랫폼명) 인용 없음
    assert "유튜브" not in html
    assert "다나와" not in html
    assert "class=no" not in html                     # 01/02 피처 번호(구 class=no) 없음
    assert '"%02d"' not in html                       # 번호 포맷 흔적 없음


def test_hero_image_drives_accent_and_renders():
    html = detail_page.build_html(VIEW, DRAFT, {"hero": _solid_uri((200, 40, 40))})
    assert "#3f9d4f" not in html                      # 카테고리 그린 아님 → 이미지 색으로 대체
    assert html.count("<img") == 1                    # 히어로 1장
    assert "대표 이미지 영역" not in html


def test_multiple_slots_render_multiple_images():
    images = {"hero": _solid_uri((200, 40, 40)), "detail": _solid_uri((40, 120, 200))}
    html = detail_page.build_html(VIEW, DRAFT, images)
    assert html.count("<img") == 2                    # 히어로 + 디테일


def test_sections_adapt_to_content():
    html = detail_page.build_html(VIEW, DRAFT, None)
    assert "선물로도 좋아요" in html                  # VIEW.gift 있음 → 선물 섹션
    assert "구매 전 궁금증" in html                   # faqs 있음 → FAQ
    no_faq = detail_page.build_html(VIEW, dict(DRAFT, faqs=[]), None)
    assert "구매 전 궁금증" not in no_faq             # faqs 없으면 FAQ 숨김


def test_self_contained():
    html = detail_page.build_html(VIEW, DRAFT, None)
    assert "<style" in html
    assert "/static/" not in html
    assert "http://" not in html.split("</style>")[0]
    assert "https://" not in html.split("</style>")[0]

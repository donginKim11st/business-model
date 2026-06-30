import json
import pathlib
from app.insight import build_view
from app import detail_page

FIX = pathlib.Path(__file__).parent / "fixtures"
VIEW = build_view(json.loads((FIX / "product_full.json").read_text(encoding="utf-8")))

DRAFT = {
    "titles": ["건강한 한 끼, 쿡시 사골 미역국 쌀국수", "글루텐프리로 더 건강하게", "따뜻한 국물의 매력"],
    "selling_points": [
        {"text": "글루텐프리와 높은 쌀 함량으로 건강한 선택", "sources": ["naver"]},
        {"text": "간편한 조리법으로 누구나 쉽게", "sources": ["naver"]},
    ],
    "target_copy": "아이와 어른 모두가 즐길 수 있는 건강한 한 끼.",
    "faqs": [{"q": "글루텐이 있나요?", "a": "아니요, 글루텐프리입니다."}],
    "spec_highlights": ["글루텐프리", "높은 쌀 함량"],
    "price_positioning": "최저 21,060원으로 합리적입니다.",
}


def test_build_html_v1_placeholder_when_no_image():
    html = detail_page.build_html(VIEW, DRAFT, None)
    assert "쿡시 사골 미역국 쌀국수" in html          # 상품명
    assert "건강한 한 끼" in html                      # 헤드라인(titles[0])
    assert "글루텐프리와 높은 쌀 함량으로 건강한 선택" in html   # 셀링포인트
    assert "[근거: naver]" in html                     # 출처 태그
    assert "글루텐이 있나요?" in html                  # FAQ
    assert "분석 기반" in html                         # 근거 푸터
    assert "<img" not in html                          # v1: 이미지 없음
    assert "상품 사진 영역" in html                    # 플레이스홀더


def test_build_html_v2_embeds_image():
    uri = "data:image/png;base64,iVBORw0KGgo="
    html = detail_page.build_html(VIEW, DRAFT, uri)
    assert f'src="{uri}"' in html                      # 업로드 이미지 슬롯
    assert "상품 사진 영역" not in html                # 플레이스홀더 대체됨


def test_build_html_hides_missing_sections():
    view = dict(VIEW, price=None, specs=[])
    draft = dict(DRAFT, spec_highlights=[], price_positioning="")
    html = detail_page.build_html(view, draft, None)
    assert "최저가" not in html                        # price 없으면 가격 박스 숨김
    assert "왜 이 제품인가" in html                    # 다른 섹션(셀링포인트)은 정상 렌더


def test_build_html_is_self_contained():
    html = detail_page.build_html(VIEW, DRAFT, None)
    assert "<style" in html                            # CSS 인라인
    assert "/static/" not in html                      # 외부 CSS/JS 참조 없음
    assert "http://" not in html.split("</style>")[0]  # style 내 외부 fetch 없음


def _solid_uri(rgb):
    """단색 PNG 의 data URI (이미지 색 추출 테스트용)."""
    import base64
    import io
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), rgb).save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def test_dominant_rgb_and_palette_from_image():
    rgb = detail_page._dominant_rgb(_solid_uri((200, 40, 40)))   # 붉은 상품 이미지
    assert rgb is not None
    assert rgb[0] > rgb[1] and rgb[0] > rgb[2]                   # 붉은색 우세
    pal = detail_page._palette_from_rgb(rgb)
    assert pal["on"] == "#ffffff"
    pr, pg, pb = int(pal["primary"][1:3], 16), int(pal["primary"][3:5], 16), int(pal["primary"][5:7], 16)
    assert pr > pg and pr > pb                                   # primary 도 붉은 계열


def test_image_palette_overrides_category_theme():
    html_cat = detail_page.build_html(VIEW, DRAFT, None)         # v1: 식품(라면/면류)=그린
    html_img = detail_page.build_html(VIEW, DRAFT, _solid_uri((200, 40, 40)))
    assert "#3f9d4f" in html_cat                                 # 카테고리 그린 테마
    assert "#3f9d4f" not in html_img                            # 이미지 색으로 대체됨
    assert html_cat != html_img


def test_invalid_image_falls_back_to_category_theme():
    html = detail_page.build_html(VIEW, DRAFT, "data:image/png;base64,iVBORw0KGgo=")
    assert "#3f9d4f" in html                                     # 디코드 실패 → 그린 폴백, 안전

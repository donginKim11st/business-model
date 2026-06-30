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
    assert "21,060" in html                            # 가격
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
    assert "핵심 스펙" not in html                     # spec/price 둘 다 없으면 스펙 패널 숨김


def test_build_html_is_self_contained():
    html = detail_page.build_html(VIEW, DRAFT, None)
    assert "<style" in html                            # CSS 인라인
    assert "/static/" not in html                      # 외부 CSS/JS 참조 없음
    assert "http://" not in html.split("</style>")[0]  # style 내 외부 fetch 없음

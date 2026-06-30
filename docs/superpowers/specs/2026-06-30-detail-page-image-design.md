# 상세페이지 이미지 생성 — 설계 문서

작성일: 2026-06-30
상태: 설계 승인 (브레인스토밍 완료, 구현 플랜 대기)
선행: [셀러 상세페이지 최적화 툴](2026-06-30-seller-listing-tool-design.md) — 이 기능은 그 위에 더한다.

## 한 줄 정의

셀러가 생성한 상세페이지 **텍스트 초안 + 상품 사진**을 Lumos 톤의 **긴 상세페이지 HTML**로 깔고,
헤드리스 브라우저로 캡처해 **바로 쓰는 상세페이지 PNG**를 내려주는 기능.

## 배경 — 데이터 현실 (브레인스토밍 중 실측)

`insights_demo`·`insights` 두 DB 모두:
- `identity.status = done` **0건**, `catalogs.identity.url` **0건** — 정형(identity) 데이터가 라이브 적재 안 됨.
- identity 추출 CSV(`all_brands.csv`)의 `url`은 **공식 페이지 URL**일 뿐 이미지 URL이 아니며, 의류 브랜드용이라 식품 위주 우주와 겹치지 않음.

→ "공식 페이지 URL 사진"은 현재 데이터로 불가능. **사진 소스 = 셀러 직접 업로드**로 확정.

## 범위 — v1 / v2 (둘 다 빌드, 사진 슬롯이 이음새)

레이아웃에 **상품 사진 슬롯** 하나를 두고, 그 슬롯을 채우는 방식만 단계별로 다르다.

| | 사진 슬롯 | 입력 |
|---|---|---|
| **v1** | 빈 **플레이스홀더 박스**("상품 사진 영역") | 업로드 없음 — 기존 텍스트 데이터만으로 즉시 PNG 생성 |
| **v2** | 셀러가 올린 **이미지로 채움** | multipart 이미지 업로드 |

`detail_page.build_html(view, draft, image_data_uri=None)` 의 `image_data_uri` 인자가 유일한 분기점.

## 접근 결정

- **렌더링 엔진:** Playwright(헤드리스 Chromium). HTML 문자열 → `set_content` → `screenshot(full_page=True)`.
  대안 기각: wkhtmltoimage(구형 WebKit, modern CSS 깨짐), gstack browse/claude-in-chrome(개발도구 의존 = 프로덕션 취약).
- **사진 인라인:** 업로드 이미지를 **base64 data URI**로 HTML에 인라인 → 헤드리스가 파일 서빙 없이 자급. 디스크 저장·정리 불필요.
- **draft 재전송:** 클라이언트가 이미 생성한 draft(JSON)를 이미지 요청에 함께 보냄 → **LLM 재호출 없음**, 미리보기=이미지 일치.
- **단독 산출물:** 상세페이지는 앱 화면이 아니라 산출물이라 `base.html`(검색 헤더/내비) 없이 단독 HTML.

## 아키텍처

```
app/
├── detail_page.py     view + draft (+ image_data_uri) → 긴 상세페이지 HTML 문자열 (순수)
├── render.py          HTML 문자열 → PNG bytes (Playwright, 외부 I/O)
├── main.py            (수정) 라우트 추가
└── templates/
    └── detail_page.html   앱 크롬 없는 단독 긴 상세페이지(~860px 폭), Lumos 토큰 재사용
```

**새 라우트:** `POST /product/{uid}/detail-image`
- form: `draft`(JSON 문자열) + (v2) `photo`(이미지 파일, 선택)
- 처리: `get_product` → `build_view` → `json.loads(draft)`(부재 시 `generate.draft` 폴백) → `image_data_uri = base64(photo) if photo else None` → `detail_page.build_html(...)` → `render.html_to_png(...)`
- 응답: `image/png`, `Content-Disposition: attachment; filename=<상품명>_상세.png`

**경계/격리:** `business-model` 비의존 유지. `detail_page.py`는 순수(DB·LLM·IO 무관) → 단위 테스트 용이. `render.py`만 Playwright I/O. `build_view`/`generate.draft` 재사용.

## 인터페이스 계약

```python
# detail_page.py (순수)
build_html(view: dict, draft: dict, image_data_uri: str | None = None) -> str
#   image_data_uri None → 사진 슬롯을 플레이스홀더 박스로; 값 있으면 <img src=...>로 채움.

# render.py (외부 I/O)
async html_to_png(html: str) -> bytes      # Playwright full_page 캡처, device_scale_factor=2
class RenderError(Exception): ...           # 렌더 실패(미설치/타임아웃/크래시) 래핑
```

## 상세페이지 레이아웃 (위→아래, 단독 HTML)

폭 ~860px, 따뜻한 배경에 흰 카드 스택, Lumos 토큰(`--bg #f2f0ec`, `--accent #ff5a1f` 등).

1. **히어로** — 상품 사진 슬롯(v1 점선 플레이스홀더 ~360px / v2 업로드 이미지 `object-fit:cover`) + 헤드라인(`draft.titles[0]`) + 상품명 + 카테고리
2. **핵심 셀링포인트** — `draft.selling_points` 굵은 불릿(선셋 아이콘), 각 포인트에 `[근거: naver]` 출처 태그
3. **타깃·사용씬** — `draft.target_copy` 한 문단 + `view.targets` 칩
4. **선제 대응 FAQ** — `draft.faqs` Q&A
5. **스펙 하이라이트** — `draft.spec_highlights` (없으면 섹션 숨김)
6. **가격 포지션** — 큰 볼드 가격(`view.price`, 없으면 숨김)
7. **근거 푸터** — "실제 리뷰 {analyzed_count}건 분석 기반" 신뢰 배지(네이버/유튜브/다나와 출처 수)

부분 데이터 안전: 스펙·가격 없으면 섹션 숨김, 사진 없으면(v1) 플레이스홀더.

## 데이터 흐름

```
[셀러] "상세페이지 생성"(기존) → draft 표시
   ↓ v1: "이미지로 내보내기"  /  v2: "상품 사진" 선택 후 내보내기
[JS] POST /product/{uid}/detail-image  (form: draft + (v2) photo)
[서버] get_product(uid) → build_view → json.loads(draft) → image_data_uri(v2) →
       detail_page.build_html → render.html_to_png → PNG 응답
[브라우저] PNG 다운로드 (blob)
```

**render.html_to_png 핵심:**
```python
async def html_to_png(html: str) -> bytes:
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(device_scale_factor=2)
        await page.set_content(html, wait_until="networkidle")
        png = await page.screenshot(full_page=True, type="png")
        await browser.close()
        return png
```

## 에러 처리

원칙: 이미지 생성 실패가 인사이트/초안 화면을 막지 않는다(독립).

| 코드패스 | 무엇이 잘못되나 | 사용자가 보는 것 |
|---|---|---|
| uid 없음 | 잘못된 요청 | 404 |
| draft 필드 부재 | 초안 없이 호출 | `generate.draft` 재생성 폴백 (실패 시 502 친절 메시지) |
| draft JSON 깨짐 | 잘못된 전송 | 400 "초안 데이터 오류" |
| v2 업로드 비이미지 | content-type ≠ image/* | 400 "이미지 파일만 업로드" |
| v2 업로드 과대 | 8MB 초과 | 400 "8MB 이하 이미지" |
| Playwright 미설치/Chromium 없음 | 환경 미비 | 500 + 로그 "playwright install chromium 필요" |
| 렌더 타임아웃/크래시 | 브라우저 실패 | 500 → JS "이미지 생성 실패, 다시 시도" (초안 화면 유지) |

JS: 내보내기 버튼 렌더 중 비활성("이미지 생성 중…"), 성공 시 blob→다운로드, 실패 시 메시지.

## 테스트 전략

**① 단위 — `detail_page.build_html` (순수, 가장 두껍게)**
- `image_data_uri=None` → 플레이스홀더 박스 마크업, `<img>` 없음 (v1)
- data URI 주어짐 → `<img src="data:image...">` 슬롯 채움 (v2)
- specs/price 없으면 해당 섹션 미렌더, 셀링포인트 출처 태그 렌더, 근거 푸터에 analyzed_count 반영
- 픽스처: 기존 `product_full` 뷰 + 샘플 draft dict 재사용

**② 라우트 — FastAPI `TestClient`**
- `render.html_to_png` 모킹(가짜 PNG bytes) → POST가 `image/png` + `Content-Disposition: attachment`
- uid 없음 → 404, draft 부재 → 재생성 폴백(`generate.draft` 모킹), draft 깨짐 → 400
- v1(파일 없음): `build_html`이 `image_data_uri=None`으로 호출됨 검증
- v2(파일 있음): data URI 임베드 검증, 비이미지 → 400, 과대 → 400

**③ 렌더 통합 — `@pytest.mark.render` (기본 skip)**
- 실제 Playwright로 작은 HTML→PNG 1회, PNG 매직바이트(`\x89PNG`) 확인. Chromium 설치 필요해 기본 skip.

## 범위 밖 (NOT in scope)

- PDF 출력
- 다중 이미지(여러 컷)·이미지 편집/크롭 — v1/v2는 단일 히어로 사진 슬롯까지
- 공식 페이지 URL→og:image 자동 추출 (데이터 미적재로 보류; 향후 identity 적재 시 재검토)
- 이미지 영속 저장(업로드는 data URI 인라인, 디스크 미저장)

## 의존성

- `playwright` (Python) + `playwright install chromium` (README 명시, 새 인프라는 이것뿐)

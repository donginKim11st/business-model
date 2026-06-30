# 흰색 적응형 PDP + N이미지 슬롯 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 상세페이지 이미지를 깨끗한 흰색 기반의 적응형 PDP로 바꾸고, 셀러가 여러 장의 사진을 슬롯(히어로/디테일/사용씬/보조)별로 직접 배정해 채울 수 있게 한다.

**Architecture:** `detail_page.build_html(view, draft, images)` 가 단일 이미지 대신 **슬롯→data URI dict**를 받는다. 흰색 베이스 + 텍스트 중립 다크, 액센트 색은 히어로 이미지에서 추출(없으면 카테고리 테마). 템플릿은 콘텐츠(셀링포인트 수·타깃·선물·FAQ)와 채워진 이미지 슬롯에 따라 적응 렌더. 라우트는 슬롯별 명명 파일 필드를 받아 dict 조립, `_draft.html`은 슬롯 카드로 위치 배정.

**Tech Stack:** Python, FastAPI, Jinja2, Playwright, Pillow(색 추출), pytest.

## Global Constraints

- `business-model` 코드 비import. `detail_page.py` 순수(DB·LLM·네트워크 IO 없음 — Pillow 인메모리 디코드는 허용). `render.py` 만 Playwright I/O.
- 상세페이지 HTML self-contained: CSS 인라인, 이미지 인라인(data URI), 외부 fetch 없음.
- **흰색 베이스**(`--bg #ffffff`), 텍스트 중립 다크(`--ink #191613`), **액센트 색만** 히어로 이미지 추출색(없으면 카테고리 테마)으로 절제 사용(번호 아님 — 라벨·구분바·FAQ Q·푸터). 액센트 면적 ≤ 화면 10%.
- **슬롯 = `hero / detail / usage / sub`** 4종. `hero` 가 배경 팔레트 기준. 채워진 슬롯만 렌더, 빈 슬롯은 깔끔한 플레이스홀더.
- 콘텐츠 적응: 셀링포인트 수만큼 피처 섹션 교차, `v.gift` 있으면 선물 섹션, `d.faqs` 있으면 FAQ, `d.target_copy` 있으면 타깃 패널.
- **금지(이 이미지는 셀러 자기 PDP):** 가격/시장최저가, AI 스펙 섹션, **"01·02" 피처 번호**, **"네이버/유튜브/다나와 후기 기반" 같은 데이터 출처 인용 문구**.
- 업로드 검증: 슬롯별 content-type `image/*` 만, 8MB 이하, 디스크 미저장(data URI 인라인). 0장도 유효(전부 플레이스홀더).
- 이미지 생성 실패가 인사이트/초안 화면을 막지 않는다(독립): RenderError → 500.
- Playwright/LLM 은 테스트에서 모킹. 출력 pristine.

### 기존 계약 (재사용)

```python
# app/insight.py build_view(doc) -> view dict (uid/keyword/category_l1/type/analyzed_count/
#   source_counts/ad_flagged/strengths/weaknesses/targets/gift/specs/identity_status/price)
#   targets = {who:[{label,points:[{point,n,evidence}]}], when:[...], where:[...], why:[...]}
#   gift = [{point,n,evidence}, ...]
# app/generate.py draft(view) -> {titles:[..], selling_points:[{text,sources}], target_copy,
#   faqs:[{q,a}], spec_highlights:[..], price_positioning}
# app/detail_page.py 기존: _theme(category_l1), _hex, _mix_white, _dominant_rgb, _palette_from_rgb (유지)
# app/render.py async html_to_png(html)->bytes, RenderError
# app/main.py: from app import data, generate, render, detail_page (모듈 속성, monkeypatch 가능)
```

### 슬롯 계약 (모든 소비자가 의존)

```python
# detail_page.SLOTS — 순서 있는 tuple. _draft.html 슬롯 카드 + 라우트 필드명의 단일 진실원.
SLOTS = (
  {"key": "hero",   "label": "히어로", "role": "상단 대표컷 · 페이지 배경색의 기준"},
  {"key": "detail", "label": "디테일", "role": "소재·질감 클로즈업"},
  {"key": "usage",  "label": "사용씬", "role": "실사용·연출 컷"},
  {"key": "sub",    "label": "보조",   "role": "추가 각도·패키지"},
)
# build_html(view, draft, images=None) — images = {slot_key: data_uri}. 빈 슬롯은 dict에서 생략.
# 라우트 멀티파트 파일 필드명 = 슬롯 key (hero/detail/usage/sub). app.js 가 채워진 슬롯만 전송.
```

---

## File Structure

- `app/detail_page.py` — (수정) `SLOTS` 추가, `build_html(view, draft, images=None)` (단일 image_data_uri → dict). 색 추출 함수 유지.
- `app/templates/detail_page.html` — (전면 교체) 흰색 적응형 PDP (슬롯·콘텐츠 적응, 번호·출처문구 없음).
- `app/main.py` — (수정) detail-image 라우트 멀티슬롯 명명 파일 필드 + dict 조립 + 검증 헬퍼. draft 라우트는 `_draft.html` 에 `slots` 전달.
- `app/templates/_draft.html` — (수정) 슬롯 카드 4개(파일선택).
- `app/static/app.js` — (수정) 채워진 슬롯을 슬롯명 필드로 FormData 전송.
- `tests/test_detail_page.py` · `tests/test_detail_image_routes.py` — (수정)
- `README.md` — (수정)

---

## Task 1: 백엔드 — 슬롯 계약(build_html dict + 흰색 적응형 템플릿 + 멀티슬롯 라우트)

**Files:**
- Modify: `app/detail_page.py`, `app/main.py`
- Replace: `app/templates/detail_page.html`
- Test: `tests/test_detail_page.py`, `tests/test_detail_image_routes.py`

**Interfaces:**
- Consumes: `_theme`, `_dominant_rgb`, `_palette_from_rgb` (기존), `build_view`/`generate.draft`/`render.html_to_png`
- Produces: `detail_page.SLOTS`, `detail_page.build_html(view, draft, images=None) -> str`, 라우트 `POST /product/{uid}/detail-image` (필드 `draft` + 슬롯 파일 `hero/detail/usage/sub`)

- [ ] **Step 1: test_detail_page.py 재작성 (실패 테스트)**

기존 파일 상단 import/픽스처(VIEW, DRAFT, `_solid_uri`)는 유지하고, 테스트 본문을 아래로 교체한다. (`_solid_uri` 헬퍼가 없으면 함께 둔다.)

```python
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
    assert "후기 기반" not in html                    # 데이터 출처 인용 문구 없음
    assert "네이버 " not in html                      # 푸터 플랫폼 카운트 없음
    assert "class=num" not in html                    # 01/02 피처 번호 없음


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
```

- [ ] **Step 2: 실패 확인**

Run: `python3 -m pytest tests/test_detail_page.py -v`
Expected: FAIL — 새 동작/문구 미구현(예: `대표 이미지 영역` 없음, `<img` 카운트 불일치).

- [ ] **Step 3: app/detail_page.py 수정 — SLOTS + build_html(images dict)**

`build_html` 함수만 아래로 교체하고, 파일 끝(또는 _theme 위)에 `SLOTS` 상수를 추가한다. `_theme/_hex/_mix_white/_dominant_rgb/_palette_from_rgb` 는 그대로 둔다.

```python
SLOTS = (
    {"key": "hero",   "label": "히어로", "role": "상단 대표컷 · 페이지 배경색의 기준"},
    {"key": "detail", "label": "디테일", "role": "소재·질감 클로즈업"},
    {"key": "usage",  "label": "사용씬", "role": "실사용·연출 컷"},
    {"key": "sub",    "label": "보조",   "role": "추가 각도·패키지"},
)


def build_html(view, draft, images=None):
    """흰색 적응형 PDP HTML. images = {slot_key: data_uri}. 히어로 있으면 그 색으로 액센트."""
    view = view or {}
    images = images or {}
    hero = images.get("hero")
    if hero:
        rgb = _dominant_rgb(hero)
        theme = _palette_from_rgb(rgb) if rgb else _theme(view.get("category_l1"))
    else:
        theme = _theme(view.get("category_l1"))
    return _env.get_template("detail_page.html").render(
        v=view, d=draft or {}, images=images, theme=theme)
```

- [ ] **Step 4: app/templates/detail_page.html 전면 교체 (흰색 적응형)**

```html
<!doctype html><html lang=ko><head><meta charset=utf-8>
<style>
:root{--accent:{{ theme.primary }};--tint:{{ theme.soft }};--ink:#191613;--sub:#6e6a63;--line:#eceae6;--bg:#ffffff}
*{box-sizing:border-box;margin:0;padding:0}
body{width:1000px;background:var(--bg);color:var(--ink);
  font:16px/1.7 -apple-system,"Apple SD Gothic Neo","Segoe UI",system-ui,sans-serif;-webkit-font-smoothing:antialiased}
img{display:block;max-width:100%}
.eyebrow{display:inline-block;font-size:13px;font-weight:800;letter-spacing:.18em;color:var(--accent);margin-bottom:24px}
.hero{padding:112px 80px 0}
.hero h1{font-size:54px;line-height:1.18;font-weight:800;letter-spacing:-.03em;max-width:760px}
.hero .lede{margin-top:22px;font-size:21px;line-height:1.6;color:var(--sub);max-width:620px}
.hero-img{margin-top:56px;height:520px;border-radius:20px;overflow:hidden}
.hero-img img{width:100%;height:100%;object-fit:cover}
.hero-img.ph{display:flex;align-items:center;justify-content:center;
  background:var(--tint);color:var(--accent);font-size:16px;font-weight:700;letter-spacing:.04em}
.tags{margin-top:28px}
.tags span{display:inline-block;font-size:15px;font-weight:700;color:var(--accent);margin:4px 18px 4px 0}
.statement{padding:128px 80px;text-align:center}
.statement .rule{width:48px;height:3px;background:var(--accent);margin:0 auto 32px;border-radius:2px}
.statement p{font-size:36px;line-height:1.4;font-weight:800;letter-spacing:-.02em;max-width:760px;margin:0 auto}
.feat{display:flex;gap:56px;align-items:center;padding:72px 80px}
.feat.rev{flex-direction:row-reverse}
.feat-txt{flex:1}
.feat .kicker{width:44px;height:4px;background:var(--accent);border-radius:2px;margin-bottom:22px}
.feat-txt h2{font-size:30px;line-height:1.4;font-weight:800;letter-spacing:-.02em}
.feat-img{flex:1;height:380px;border-radius:18px;overflow:hidden}
.feat-img img{width:100%;height:100%;object-fit:cover}
.feat-img.ph{display:flex;align-items:center;justify-content:center;background:var(--tint);
  color:var(--accent);font-weight:700;font-size:15px;opacity:.8}
.target{margin:48px 80px;padding:72px 64px;background:var(--tint);border-radius:24px}
.target h2{font-size:32px;font-weight:800;letter-spacing:-.02em;margin-bottom:18px}
.target p{font-size:19px;line-height:1.75;color:#4a463f;max-width:680px}
.chips{margin-top:28px}
.chip{display:inline-block;padding:10px 20px;background:#fff;border-radius:999px;margin:5px 7px 5px 0;font-size:15px;font-weight:600}
.gift{padding:72px 80px;border-top:1px solid var(--line)}
.gift h2{font-size:28px;font-weight:800;letter-spacing:-.02em;margin-bottom:10px}
.gift p{font-size:17px;color:var(--sub)}
.faq{padding:96px 80px 40px}
.faq h2{font-size:30px;font-weight:800;letter-spacing:-.02em;margin-bottom:36px}
.qa{padding:26px 0;border-top:1px solid var(--line)}
.qa:first-of-type{border-top:0}
.qa .q{font-size:19px;font-weight:700;margin-bottom:8px}
.qa .q::before{content:"Q  ";color:var(--accent);font-weight:800}
.qa .a{font-size:16px;color:#4a463f;padding-left:26px}
.foot{margin-top:64px;padding:56px 80px;background:#faf8f5;border-top:1px solid var(--line);text-align:center}
.foot .badge{font-size:21px;font-weight:800;letter-spacing:-.01em}
.foot .badge b{color:var(--accent)}
</style></head>
<body>

<section class=hero>
  <span class=eyebrow>{{ v.category_l1 or 'PRODUCT' }}</span>
  <h1>{{ d.titles[0] if d.titles else v.keyword }}</h1>
  {% if d.titles and d.titles|length > 1 %}<p class=lede>{{ d.titles[1] }}</p>{% endif %}
  {% if images.get('hero') %}<div class=hero-img><img src="{{ images.hero }}" alt="대표 이미지"></div>
  {% else %}<div class="hero-img ph">대표 이미지 영역 · 업로드 시 채워집니다</div>{% endif %}
  {% if d.spec_highlights %}<div class=tags>{% for s in d.spec_highlights %}<span>#{{ s|replace(' ','') }}</span>{% endfor %}</div>{% endif %}
</section>

{% if d.titles and d.titles|length > 2 %}<section class=statement>
  <div class=rule></div><p>{{ d.titles[2] }}</p>
</section>{% endif %}

{% set feat_imgs = [images.get('detail'), images.get('usage'), images.get('sub')] %}
{% for s in d.selling_points %}
<section class="feat{{ ' rev' if loop.index0 % 2 else '' }}">
  <div class=feat-txt>
    <div class=kicker></div>
    <h2>{{ s.text }}</h2>
  </div>
  {% set fi = feat_imgs[loop.index0] if loop.index0 < 3 else None %}
  {% if fi %}<div class=feat-img><img src="{{ fi }}" alt=""></div>
  {% else %}<div class="feat-img ph">이미지</div>{% endif %}
</section>
{% endfor %}

{% if d.target_copy %}<section class=target>
  <span class=eyebrow>FOR YOU</span>
  <h2>이런 분께 추천합니다</h2>
  <p>{{ d.target_copy }}</p>
  {% set chips = [] %}
  {% for dim, groups in v.targets.items() %}{% for g in groups %}{% for p in g.points %}{% if chips.append(p.point) %}{% endif %}{% endfor %}{% endfor %}{% endfor %}
  {% if chips %}<div class=chips>{% for t in chips %}<span class=chip>{{ t }}</span>{% endfor %}</div>{% endif %}
</section>{% endif %}

{% if v.gift %}<section class=gift>
  <span class=eyebrow>GIFT</span>
  <h2>선물로도 좋아요</h2>
  <p>{% for g in v.gift %}{{ g.point }}{% if not loop.last %} · {% endif %}{% endfor %}</p>
</section>{% endif %}

{% if d.faqs %}<section class=faq>
  <h2>구매 전 궁금증</h2>
  {% for f in d.faqs %}<div class=qa><div class=q>{{ f.q }}</div><div class=a>{{ f.a }}</div></div>{% endfor %}
</section>{% endif %}

<section class=foot>
  <div class=badge>실제 리뷰 <b>{{ v.analyzed_count }}건</b> 분석 기반</div>
</section>
</body></html>
```

- [ ] **Step 5: test_detail_page 통과 확인**

Run: `python3 -m pytest tests/test_detail_page.py -v`
Expected: PASS (6 passed).

- [ ] **Step 6: test_detail_image_routes.py 재작성 (멀티슬롯)**

기존 파일을 아래로 교체.

```python
import io
import json
import pathlib
from fastapi.testclient import TestClient
from app import main

FIX = pathlib.Path(__file__).parent / "fixtures"
DOC = json.loads((FIX / "product_full.json").read_text(encoding="utf-8"))
DRAFT = {"titles": ["A", "B", "C"], "selling_points": [{"text": "간편", "sources": ["naver"]}],
         "target_copy": "x", "faqs": [{"q": "q", "a": "a"}], "spec_highlights": ["s"], "price_positioning": "p"}
PNG = b"\x89PNG\r\n\x1a\n" + b"FAKE"


def _client(monkeypatch, *, doc=DOC, draft_fn=None, img_capture=None):
    monkeypatch.setattr(main.data, "get_product", lambda uid, **k: doc)
    if draft_fn:
        monkeypatch.setattr(main.generate, "draft", draft_fn)

    def _build(view, d, images=None):
        if img_capture is not None:
            img_capture["images"] = images
        return "<html></html>"
    monkeypatch.setattr(main.detail_page, "build_html", _build)

    async def _png(html):
        return PNG
    monkeypatch.setattr(main.render, "html_to_png", _png)
    return TestClient(main.app)


def _img(color_byte=b"\x89PNG"):
    return io.BytesIO(color_byte + b"data")


def test_no_files_renders_with_empty_images(monkeypatch):
    cap = {}
    c = _client(monkeypatch, img_capture=cap)
    r = c.post("/product/P7863/detail-image", data={"draft": json.dumps(DRAFT)})
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert cap["images"] == {}                        # 0장 → 빈 dict (전부 플레이스홀더)


def test_multiple_slots_embedded_by_key(monkeypatch):
    cap = {}
    c = _client(monkeypatch, img_capture=cap)
    files = {"hero": ("h.png", _img(), "image/png"), "usage": ("u.jpg", _img(), "image/jpeg")}
    r = c.post("/product/P7863/detail-image", data={"draft": json.dumps(DRAFT)}, files=files)
    assert r.status_code == 200
    assert set(cap["images"].keys()) == {"hero", "usage"}          # 채운 슬롯만
    assert cap["images"]["hero"].startswith("data:image/png;base64,")
    assert cap["images"]["usage"].startswith("data:image/jpeg;base64,")


def test_unknown_uid_404(monkeypatch):
    c = _client(monkeypatch, doc=None)
    assert c.post("/product/NOPE/detail-image", data={"draft": json.dumps(DRAFT)}).status_code == 404


def test_malformed_draft_400(monkeypatch):
    c = _client(monkeypatch)
    assert c.post("/product/P7863/detail-image", data={"draft": "{bad"}).status_code == 400


def test_absent_draft_regenerates(monkeypatch):
    c = _client(monkeypatch, draft_fn=lambda view, **k: DRAFT)
    r = c.post("/product/P7863/detail-image", data={})
    assert r.status_code == 200


def test_non_image_slot_400(monkeypatch):
    c = _client(monkeypatch)
    files = {"hero": ("h.txt", io.BytesIO(b"hi"), "text/plain")}
    r = c.post("/product/P7863/detail-image", data={"draft": json.dumps(DRAFT)}, files=files)
    assert r.status_code == 400


def test_oversize_slot_400(monkeypatch):
    c = _client(monkeypatch)
    big = io.BytesIO(b"\x89PNG" + b"x" * (8 * 1024 * 1024 + 1))
    files = {"detail": ("big.png", big, "image/png")}
    r = c.post("/product/P7863/detail-image", data={"draft": json.dumps(DRAFT)}, files=files)
    assert r.status_code == 400


def test_render_error_500(monkeypatch):
    monkeypatch.setattr(main.data, "get_product", lambda uid, **k: DOC)
    monkeypatch.setattr(main.detail_page, "build_html", lambda v, d, images=None: "<html></html>")
    async def _boom(html):
        raise main.render.RenderError("boom")
    monkeypatch.setattr(main.render, "html_to_png", _boom)
    c = TestClient(main.app)
    r = c.post("/product/P7863/detail-image", data={"draft": json.dumps(DRAFT)})
    assert r.status_code == 500
```

- [ ] **Step 7: 실패 확인**

Run: `python3 -m pytest tests/test_detail_image_routes.py -v`
Expected: FAIL — 라우트가 아직 멀티슬롯/`images` dict 미지원.

- [ ] **Step 8: app/main.py 수정 — 멀티슬롯 라우트 + 검증 헬퍼**

import 에 `base64` 가 모듈 상단에 없으면 추가(`import base64`). 기존 `detail_image` 라우트를 아래로 교체하고, 그 위에 헬퍼/예외/상수를 둔다. (`_MAX_IMG` 가 이미 있으면 중복 정의하지 말 것.)

```python
class _BadImage(Exception):
    pass


async def _slot_to_data_uri(photo):
    """업로드 파일 → data URI. 비이미지/과대면 _BadImage."""
    ctype = photo.content_type or ""
    if not ctype.startswith("image/"):
        raise _BadImage("이미지 파일만 업로드")
    raw = await photo.read(_MAX_IMG + 1)
    if len(raw) > _MAX_IMG:
        raise _BadImage("8MB 이하 이미지")
    return f"data:{ctype};base64,{base64.b64encode(raw).decode()}"


@app.post("/product/{uid}/detail-image")
async def detail_image(uid: str, draft: str = Form(None),
                       hero: UploadFile = File(None), detail: UploadFile = File(None),
                       usage: UploadFile = File(None), sub: UploadFile = File(None)):
    doc = data.get_product(uid)
    if doc is None:
        return Response("상품을 찾을 수 없습니다.", status_code=404)
    view = build_view(doc)
    if draft:
        try:
            d = json.loads(draft)
        except (ValueError, TypeError):
            return Response("초안 데이터 오류", status_code=400)
    else:
        try:
            d = generate.draft(view)
        except GenerateError:
            return Response("초안 생성 실패", status_code=502)
    images = {}
    for key, photo in (("hero", hero), ("detail", detail), ("usage", usage), ("sub", sub)):
        if photo is not None:
            try:
                images[key] = await _slot_to_data_uri(photo)
            except _BadImage as e:
                return Response(str(e), status_code=400)
    html = detail_page.build_html(view, d, images)
    try:
        png = await render.html_to_png(html)
    except render.RenderError:
        return Response("이미지 생성 실패", status_code=500)
    fname = quote(f"{view['keyword']}_상세.png")
    return Response(png, media_type="image/png",
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{fname}"})
```

`_MAX_IMG` 가 파일에 없으면 모듈 상수로 추가:
```python
_MAX_IMG = 8 * 1024 * 1024  # 8MB
```

- [ ] **Step 9: 통과 + 전체 스위트 확인**

Run: `python3 -m pytest tests/test_detail_image_routes.py -v && python3 -m pytest -q`
Expected: 라우트 8 passed; 전체 PASS(+ live/render skip), pristine.

- [ ] **Step 10: Commit**

```bash
git add app/detail_page.py app/templates/detail_page.html app/main.py tests/test_detail_page.py tests/test_detail_image_routes.py
git commit -m "feat: 흰색 적응형 PDP + N이미지 슬롯(build_html images dict + 멀티슬롯 라우트)"
```

---

## Task 2: 프런트 — 슬롯 카드 위치배정 UI

**Files:**
- Modify: `app/main.py` (draft 라우트가 `_draft.html` 에 `slots` 전달), `app/templates/_draft.html`, `app/static/app.js`
- Test: 라우트 렌더 스모크(TestClient) + 수동

**Interfaces:**
- Consumes: `detail_page.SLOTS` (Task 1), `POST /product/{uid}/detail-image` 슬롯 필드(Task 1)
- Produces: `_draft.html` 에 슬롯별 `<input type=file id="slot-{key}">` + 내보내기 버튼; app.js 가 채워진 슬롯을 슬롯명 필드로 전송.

- [ ] **Step 1: 실패 테스트 — draft 라우트가 슬롯 카드 렌더** `tests/test_routes.py` 에 추가

```python
def test_draft_fragment_has_slot_cards(monkeypatch):
    draft = {"titles": ["A", "B", "C"], "selling_points": [{"text": "간편", "sources": ["naver"]}],
             "target_copy": "x", "faqs": [{"q": "q", "a": "a"}], "spec_highlights": ["s"], "price_positioning": "p"}
    monkeypatch.setattr(main.data, "get_product", lambda uid, **k: DOC)
    monkeypatch.setattr(main.generate, "draft", lambda v, **k: draft)
    c = TestClient(main.app)
    r = c.post("/product/P7863/draft")
    assert r.status_code == 200
    for key in ("hero", "detail", "usage", "sub"):
        assert f'id="slot-{key}"' in r.text            # 슬롯별 파일 입력
    assert "히어로" in r.text and "사용씬" in r.text   # 슬롯 라벨
    assert "이미지로 내보내기" in r.text
```

(파일 상단에 `DOC` 픽스처가 없으면: `import json, pathlib; DOC = json.loads((pathlib.Path(__file__).parent/"fixtures"/"product_full.json").read_text(encoding="utf-8"))` 를 추가한다.)

- [ ] **Step 2: 실패 확인**

Run: `python3 -m pytest tests/test_routes.py::test_draft_fragment_has_slot_cards -v`
Expected: FAIL — 슬롯 카드 미렌더.

- [ ] **Step 3: app/main.py — draft 라우트가 SLOTS 전달**

draft 라우트의 두 `TemplateResponse(... "_draft.html" ...)` 컨텍스트에 `"slots": detail_page.SLOTS` 를 추가한다.
```python
        return templates.TemplateResponse(request, "_draft.html", {"d": d, "uid": uid, "slots": detail_page.SLOTS, "error": None})
```
```python
    except GenerateError:
        return templates.TemplateResponse(request, "_draft.html", {"d": None, "uid": uid, "slots": detail_page.SLOTS, "error": True})
```

- [ ] **Step 4: app/templates/_draft.html — 슬롯 카드로 교체**

기존 `<div class=export>...</div>` 블록을 아래로 교체한다(draft-json 스크립트와 .draft 본문은 유지).
```html
<div class=export>
  <div class=slot-grid>
    {% for s in slots %}
    <label class=slot-card>
      <span class=slot-label>{{ s.label }}</span>
      <span class=slot-role>{{ s.role }}</span>
      <input type=file id="slot-{{ s.key }}" data-slot="{{ s.key }}" accept="image/png,image/jpeg,image/webp">
    </label>
    {% endfor %}
  </div>
  <button id=exportbtn data-uid="{{ uid }}">이미지로 내보내기</button>
</div>
```

- [ ] **Step 5: app/static/app.js — 채워진 슬롯을 슬롯명 필드로 전송**

내보내기 핸들러에서 단일 `photo` 추가 부분을 슬롯 순회로 교체한다. `fd.append("draft", draftEl.textContent);` 다음의 두 줄
```javascript
    const photo = document.getElementById("photo");
    if (photo && photo.files[0]) fd.append("photo", photo.files[0]);
```
을 아래로 교체:
```javascript
    document.querySelectorAll("input[data-slot]").forEach((inp) => {
      if (inp.files[0]) fd.append(inp.dataset.slot, inp.files[0]);
    });
```

- [ ] **Step 6: app/static/app.css — 슬롯 카드 최소 스타일 추가**

`app.css` 끝에 추가:
```css
.slot-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin: 12px 0; }
.slot-card { display: flex; flex-direction: column; gap: 4px; padding: 12px 14px;
  border: 1px solid var(--line); border-radius: 12px; background: var(--card); cursor: pointer; }
.slot-label { font-weight: 700; font-size: 14px; }
.slot-role { color: var(--muted); font-size: 12px; }
.slot-card input { margin-top: 6px; font-size: 12px; }
```

- [ ] **Step 7: 통과 + 전체 스위트 확인**

Run: `python3 -m pytest tests/test_routes.py -v && python3 -m pytest -q`
Expected: 슬롯 카드 테스트 PASS; 전체 PASS, pristine.

- [ ] **Step 8: Commit**

```bash
git add app/main.py app/templates/_draft.html app/static/app.js app/static/app.css tests/test_routes.py
git commit -m "feat: 슬롯 카드 위치배정 UI(히어로/디테일/사용씬/보조) + 멀티슬롯 전송"
```

---

## Task 3: README + 전체 스위트 + 수동 스모크

**Files:**
- Modify: `README.md`
- Test: 전체 자동 스위트 + 수동 렌더 스모크

**Interfaces:**
- Consumes: Task 1·2
- Produces: 없음(마감)

- [ ] **Step 1: README.md — 상세페이지 이미지 섹션 갱신**

`## 상세페이지 이미지` 섹션 본문을 아래로 교체.
```markdown
## 상세페이지 이미지

상품 화면에서 "상세페이지 생성" → 슬롯별(히어로/디테일/사용씬/보조)로 상품 사진을 배정 →
"이미지로 내보내기" → 흰색 기반 적응형 PDP PNG 다운로드.
- 히어로 사진 색에 맞춰 페이지 액센트가 자동 적용된다(없으면 카테고리 테마).
- 올린 슬롯만 채워지고, 빈 슬롯·없는 섹션은 우아하게 적응한다(사진 0장도 유효).
- 가격·시장최저가·데이터 출처 문구는 PDP 이미지에 넣지 않는다(셀러 자기 PDP 용도).
```

- [ ] **Step 2: 전체 자동 스위트**

Run: `python3 -m pytest -q`
Expected: 전체 PASS (live/render skip), pristine.

- [ ] **Step 3: 수동 렌더 스모크 (실 Mongo + Chromium + 키)**

```bash
playwright install chromium   # 1회
RUN_RENDER=1 python3 -m pytest tests/test_render.py -m render -v
# 서버 기동 후: 상품 → 생성 → 슬롯에 사진 배정 → 내보내기 → 흰색 PDP PNG 확인
```
Expected: 렌더 스모크 PASS. 수동: 슬롯에 1~4장 배정 시 해당 위치에 채워지고 히어로 색으로 액센트 적용.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: README 흰색 적응형 PDP + 슬롯 위치배정 반영"
```

---

## Self-Review (작성자 점검 완료)

**1. 스펙 커버리지:**
- 흰색 베이스 + 이미지색 액센트(없으면 카테고리) → Task 1 build_html + 템플릿 ✓
- N이미지 슬롯(hero/detail/usage/sub) + dict 계약 → Task 1 SLOTS/build_html/라우트 ✓
- 위치배정 UI(슬롯 카드) → Task 2 _draft.html/app.js ✓
- 콘텐츠 적응(셀링포인트/선물/FAQ/타깃) → Task 1 템플릿 + test_sections_adapt ✓
- 번호·출처문구·가격·스펙 제거 → Task 1 템플릿 + test_design_omits_numbers_and_source_phrases ✓
- 슬롯별 검증(image/8MB), 0장 유효, 독립성(500) → Task 1 라우트 + 라우트 테스트 ✓
- self-contained, business-model 비의존, detail_page 순수 → Global Constraints + test_self_contained ✓

**2. 플레이스홀더 스캔:** 모든 코드 스텝에 실제 코드·명령·기대출력. TBD/TODO 없음 ✓

**3. 타입 일관성:** 슬롯 key(hero/detail/usage/sub)가 SLOTS ↔ build_html(images dict) ↔ 템플릿 images.get(key) ↔ 라우트 파일필드 ↔ _draft.html `slot-{key}`/`data-slot` ↔ app.js `inp.dataset.slot` 전부 일치. `build_html(view, draft, images=None)` 시그니처가 Task1 정의 ↔ 라우트 호출 ↔ 라우트 테스트 스파이 일치 ✓

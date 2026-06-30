# 상세페이지 이미지 생성 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 셀러의 텍스트 초안 + (선택) 업로드 상품 사진을 Lumos 톤의 긴 상세페이지 HTML로 깔고 Playwright로 캡처해 바로 쓰는 상세페이지 PNG를 내려준다.

**Architecture:** 기존 `sellering-tools`에 더한다. `detail_page.build_html(view, draft, image_data_uri=None)`(순수)이 self-contained 상세페이지 HTML(인라인 CSS·인라인 이미지)을 만들고, `render.html_to_png(html)`(Playwright)가 PNG로 캡처한다. 사진 슬롯이 v1(빈 플레이스홀더)/v2(업로드)의 유일한 이음새다.

**Tech Stack:** Python 3.11+, FastAPI, Jinja2, Playwright(헤드리스 Chromium), python-multipart, pytest.

## Global Constraints

- `business-model` 코드는 절대 import 하지 않는다.
- `detail_page.py` 는 순수(DB·LLM·네트워크 IO 없음). `render.py` 만 Playwright I/O.
- 상세페이지 HTML 은 **self-contained**: CSS 인라인(`<style>`), 이미지 인라인(base64 data URI), 외부 fetch 없음(Playwright `set_content` 로 렌더).
- 사진 슬롯 이음새: `build_html(view, draft, image_data_uri=None)` — `None` → 플레이스홀더 박스, 값 있으면 `<img src=...>`.
- 생성 초안(draft)은 클라이언트가 이미지 요청에 JSON 으로 재전송 → LLM 재호출 없음. draft 부재 시에만 `generate.draft` 재생성 폴백.
- 업로드 검증(v2): content-type `image/*` 만, 8MB 이하. 업로드는 data URI 인라인(디스크 미저장).
- Lumos 디자인 토큰 유지: `--bg #f2f0ec`, `--card #fff`, `--accent #ff5a1f`, `--accent-2 #ffb020`, `--radius 18px`, 소프트 섀도, 큰 볼드 숫자.
- 이미지 생성 실패가 인사이트/초안 화면을 막지 않는다(독립).
- Playwright 호출은 테스트에서 모킹. 실제 렌더 테스트는 `@pytest.mark.render` 로 기본 skip(Chromium 필요).

### 기존 계약 (재사용 — 변경 금지)

```python
# app/insight.py
build_view(doc) -> dict   # {uid, keyword, category_l1, type, analyzed_count, source_counts,
                          #  ad_flagged, strengths, weaknesses, targets, gift, specs, identity_status, price}
#   strengths/weaknesses item = {point, n, evidence:[{source,date,url,quote}]}
#   targets = {who:[{label,points}], when:[...], where:[...], why:[...]}
#   price = {min, median, low_mall, n_malls, spread_pct} | None

# app/generate.py
draft(view, client=None) -> dict   # {titles:[3], selling_points:[{text,sources:[..]}],
                                   #  target_copy, faqs:[{q,a}], spec_highlights:[..], price_positioning}
class GenerateError(Exception): ...
```

### 기존 통합 지점

- `app/main.py`: `from app import data, generate` (모듈 속성, monkeypatch 가능). 라우트는 `TemplateResponse(request, name, ctx)` 현대 시그니처. draft 라우트(`POST /product/{uid}/draft`)가 `_draft.html` 조각 반환.
- `app/templates/product.html`: 하단 `<section class=gen><button id=genbtn data-uid="{{ v.uid }}">상세페이지 생성</button><div id=draft></div></section>`.
- `app/static/app.js`: `#genbtn` 클릭 → `POST /product/{uid}/draft` → `#draft` 에 조각 삽입.

---

## File Structure

- `app/detail_page.py` — `build_html(view, draft, image_data_uri=None) -> str` (순수). 자체 Jinja Environment 로 `detail_page.html` 렌더.
- `app/templates/detail_page.html` — self-contained 긴 상세페이지(인라인 `<style>` Lumos, 사진 슬롯 조건부).
- `app/render.py` — `async html_to_png(html) -> bytes` (Playwright) + `RenderError`.
- `app/main.py` — (수정) `POST /product/{uid}/detail-image` 추가, draft 라우트에 uid 컨텍스트 추가.
- `app/templates/_draft.html` — (수정) draft JSON 스크립트 + 내보내기 컨트롤.
- `app/static/app.js` — (수정) 내보내기 핸들러(blob 다운로드).
- `tests/test_detail_page.py` · `tests/test_render.py` · `tests/test_detail_image_routes.py`
- `requirements.txt` · `pyproject.toml` · `README.md` — (수정)

---

## Task 1: detail_page.build_html + 상세페이지 템플릿 (순수, 코어)

**Files:**
- Create: `app/detail_page.py`, `app/templates/detail_page.html`
- Test: `tests/test_detail_page.py`

**Interfaces:**
- Consumes: `build_view` 출력(view), `generate.draft` 출력(draft)
- Produces: `detail_page.build_html(view: dict, draft: dict, image_data_uri: str | None = None) -> str`

- [ ] **Step 1: 실패 테스트 작성** — `tests/test_detail_page.py`

```python
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
    assert "가격 포지션" not in html                   # price 없으면 섹션 숨김
    assert "스펙 하이라이트" not in html               # spec_highlights 없으면 숨김


def test_build_html_is_self_contained():
    html = detail_page.build_html(VIEW, DRAFT, None)
    assert "<style" in html                            # CSS 인라인
    assert "/static/" not in html                      # 외부 CSS/JS 참조 없음
    assert "http://" not in html.split("</style>")[0]  # style 내 외부 fetch 없음
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python3 -m pytest tests/test_detail_page.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.detail_page'`

- [ ] **Step 3: app/detail_page.py 구현**

```python
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
```

- [ ] **Step 4: app/templates/detail_page.html 구현 (self-contained)**

```html
<!doctype html><html lang=ko><head><meta charset=utf-8>
<style>
:root{--bg:#f2f0ec;--card:#fff;--cream:#faf6f0;--fg:#1a1a1a;--muted:#938d83;
  --line:#ece7df;--accent:#ff5a1f;--accent-2:#ffb020;--radius:18px;
  --shadow:0 1px 2px rgba(20,16,10,.04),0 10px 30px rgba(20,16,10,.06);}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--fg);font:15px/1.6 -apple-system,"Segoe UI",system-ui,sans-serif;
  -webkit-font-smoothing:antialiased;width:860px;padding:28px}
section{background:var(--card);border-radius:var(--radius);box-shadow:var(--shadow);
  padding:24px 26px;margin-bottom:18px}
.photo{height:360px;border-radius:var(--radius);overflow:hidden;margin-bottom:18px;
  box-shadow:var(--shadow)}
.photo img{width:100%;height:100%;object-fit:cover;display:block}
.ph{height:360px;border:2px dashed var(--line);border-radius:var(--radius);
  display:flex;align-items:center;justify-content:center;color:var(--muted);
  background:var(--cream);margin-bottom:18px;font-size:15px}
.headline{font-size:30px;font-weight:800;letter-spacing:-.02em;margin:.1em 0}
.subtitle{color:var(--muted);font-size:14px}
h2{font-size:15px;font-weight:700;margin:0 0 14px}
.sp{display:flex;gap:10px;align-items:flex-start;padding:8px 0}
.sp .dot{color:var(--accent);font-weight:800;font-size:18px;line-height:1.2}
.sp .src{color:var(--accent);font-size:12px;font-weight:600;margin-left:6px}
.tag{display:inline-block;padding:5px 12px;background:#f6f3ee;border-radius:999px;margin:3px;font-size:13px}
.faq dt{font-weight:600;margin-top:10px}
.faq dd{color:#4a463f;margin-top:2px}
.spec{display:inline-block;padding:5px 12px;background:#fff2ea;color:var(--accent);
  border-radius:999px;margin:3px;font-size:13px;font-weight:600}
.price-big{font-size:30px;font-weight:800;letter-spacing:-.01em;margin-right:6px}
.foot{text-align:center;color:var(--muted);font-size:13px;background:transparent;box-shadow:none}
.foot b{color:var(--fg)}
</style></head>
<body>
{% if image %}<div class=photo><img src="{{ image }}" alt="상품 사진"></div>
{% else %}<div class=ph>상품 사진 영역</div>{% endif %}

<section>
  <div class=headline>{{ d.titles[0] if d.titles else v.keyword }}</div>
  <div class=subtitle>{{ v.keyword }} · {{ v.category_l1 or '' }}</div>
</section>

{% if d.selling_points %}<section><h2>핵심 셀링포인트</h2>
  {% for s in d.selling_points %}<div class=sp><span class=dot>●</span><div>{{ s.text }}
    {% if s.sources %}<span class=src>[근거: {{ s.sources|join(', ') }}]</span>{% endif %}</div></div>{% endfor %}
</section>{% endif %}

{% if d.target_copy %}<section><h2>이런 분께 추천</h2>
  <p>{{ d.target_copy }}</p>
  <div style="margin-top:10px">
  {% for dim, groups in v.targets.items() %}{% for g in groups %}{% for p in g.points %}<span class=tag>{{ p.point }}</span>{% endfor %}{% endfor %}{% endfor %}
  </div>
</section>{% endif %}

{% if d.faqs %}<section><h2>자주 묻는 질문</h2>
  <dl class=faq>{% for f in d.faqs %}<dt>{{ f.q }}</dt><dd>{{ f.a }}</dd>{% endfor %}</dl>
</section>{% endif %}

{% if d.spec_highlights %}<section><h2>스펙 하이라이트</h2>
  {% for s in d.spec_highlights %}<span class=spec>{{ s }}</span>{% endfor %}
</section>{% endif %}

{% if v.price %}<section><h2>가격 포지션</h2>
  <span class=price-big>{{ "{:,}".format(v.price.min) }}원</span> 최저 · {{ v.price.low_mall }}
  {% if d.price_positioning %}<p style="color:#938d83;margin-top:6px">{{ d.price_positioning }}</p>{% endif %}
</section>{% endif %}

<section class=foot>실제 리뷰 <b>{{ v.analyzed_count }}건</b> 분석 기반 · 네이버 {{ v.source_counts.get('naver',0) }} / 유튜브 {{ v.source_counts.get('youtube',0) }} / 다나와 {{ v.source_counts.get('danawa',0) }}</section>
</body></html>
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `python3 -m pytest tests/test_detail_page.py -v`
Expected: PASS (4 passed)

- [ ] **Step 6: Commit**

```bash
git add app/detail_page.py app/templates/detail_page.html tests/test_detail_page.py
git commit -m "feat: detail_page.build_html self-contained 상세페이지 HTML (순수)"
```

---

## Task 2: render.py (Playwright HTML→PNG)

**Files:**
- Create: `app/render.py`
- Modify: `requirements.txt`, `pyproject.toml`
- Test: `tests/test_render.py`

**Interfaces:**
- Consumes: HTML 문자열 (Task 1 build_html 출력)
- Produces: `async render.html_to_png(html: str) -> bytes`, `render.RenderError(Exception)`

- [ ] **Step 1: requirements.txt 에 playwright 추가**

`requirements.txt` 끝에 추가:
```
playwright==1.48.*
```

- [ ] **Step 2: pyproject.toml 에 render 마커 등록**

`pyproject.toml` 의 `markers` 리스트에 한 줄 추가(기존 `live` 마커 아래):
```toml
[tool.pytest.ini_options]
markers = [
  "live: 실제 OpenAI 호출(기본 skip, 키 필요)",
  "render: 실제 Playwright 렌더(기본 skip, Chromium 필요)",
]
```

- [ ] **Step 3: 실패 테스트 작성** — `tests/test_render.py`

```python
import os
import shutil
import pytest
from app import render


def test_render_error_exists():
    assert issubclass(render.RenderError, Exception)


@pytest.mark.render
@pytest.mark.skipif(shutil.which("python3") is None or os.environ.get("RUN_RENDER") != "1",
                    reason="RUN_RENDER=1 + playwright install chromium 필요")
@pytest.mark.asyncio
async def test_html_to_png_produces_png():
    png = await render.html_to_png("<html><body><h1>hi</h1></body></html>")
    assert png[:8] == b"\x89PNG\r\n\x1a\n"   # PNG 매직바이트
    assert len(png) > 100
```

> 참고: `@pytest.mark.asyncio` 는 `pytest-asyncio` 가 필요하다. 단위로 도는 `test_render_error_exists` 만으로 RED→GREEN 을 검증하고, 렌더 통합 테스트는 기본 skip(수동). pytest-asyncio 미설치 시 통합 테스트는 수집 단계에서 skip 되도록 `RUN_RENDER != "1"` 가드가 먼저 막는다.

- [ ] **Step 4: 테스트 실패 확인**

Run: `python3 -m pytest tests/test_render.py::test_render_error_exists -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.render'`

- [ ] **Step 5: app/render.py 구현**

```python
"""상세페이지 HTML → PNG bytes (Playwright 헤드리스 Chromium). 유일한 렌더 I/O."""


class RenderError(Exception):
    pass


async def html_to_png(html):
    """self-contained HTML 을 풀페이지 PNG bytes 로. 실패는 RenderError 로 래핑."""
    try:
        from playwright.async_api import async_playwright
    except ImportError as e:
        raise RenderError("playwright 미설치: pip install playwright && playwright install chromium") from e
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            try:
                page = await browser.new_page(device_scale_factor=2)
                await page.set_content(html, wait_until="load")
                return await page.screenshot(full_page=True, type="png")
            finally:
                await browser.close()
    except RenderError:
        raise
    except Exception as e:
        raise RenderError(f"렌더 실패: {e}") from e
```

- [ ] **Step 6: 테스트 통과 확인**

Run: `python3 -m pip install -r requirements.txt && python3 -m pytest tests/test_render.py::test_render_error_exists -v`
Expected: PASS (1 passed). (렌더 통합 테스트는 skip — 정상)

- [ ] **Step 7: Commit**

```bash
git add app/render.py requirements.txt pyproject.toml tests/test_render.py
git commit -m "feat: render.py Playwright HTML→PNG + render 마커"
```

---

## Task 3: v1 라우트 (업로드 없음) + draft JSON 노출 + 내보내기 버튼

**Files:**
- Modify: `app/main.py`, `app/templates/_draft.html`, `app/static/app.js`, `requirements.txt`
- Test: `tests/test_detail_image_routes.py`

**Interfaces:**
- Consumes: `data.get_product`, `build_view`, `generate.draft`/`GenerateError`, `detail_page.build_html`, `render.html_to_png`
- Produces: `POST /product/{uid}/detail-image` (form `draft`) → `image/png` 다운로드. draft 라우트가 `_draft.html` 에 `uid` 전달.

- [ ] **Step 1: requirements.txt 에 python-multipart 추가**

`Form`/`File` 파싱에 필요. `requirements.txt` 에 추가:
```
python-multipart==0.0.12
```

- [ ] **Step 2: 실패 테스트 작성** — `tests/test_detail_image_routes.py`

```python
import json
import pathlib
from fastapi.testclient import TestClient
from app import main

FIX = pathlib.Path(__file__).parent / "fixtures"
DOC = json.loads((FIX / "product_full.json").read_text(encoding="utf-8"))
DRAFT = {"titles": ["A", "B", "C"], "selling_points": [{"text": "간편", "sources": ["naver"]}],
         "target_copy": "x", "faqs": [{"q": "q", "a": "a"}], "spec_highlights": ["s"], "price_positioning": "p"}
PNG = b"\x89PNG\r\n\x1a\n" + b"FAKE"


def _client(monkeypatch, *, doc=DOC, draft_fn=None, html_capture=None):
    monkeypatch.setattr(main.data, "get_product", lambda uid, **k: doc)
    if draft_fn:
        monkeypatch.setattr(main.generate, "draft", draft_fn)
    def _build(view, d, image_data_uri=None):
        if html_capture is not None:
            html_capture["image"] = image_data_uri
        return "<html></html>"
    monkeypatch.setattr(main.detail_page, "build_html", _build)
    async def _png(html):
        return PNG
    monkeypatch.setattr(main.render, "html_to_png", _png)
    return TestClient(main.app)


def test_detail_image_v1_returns_png(monkeypatch):
    cap = {}
    c = _client(monkeypatch, html_capture=cap)
    r = c.post("/product/P7863/detail-image", data={"draft": json.dumps(DRAFT)})
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert "attachment" in r.headers["content-disposition"]
    assert r.content[:8] == b"\x89PNG\r\n\x1a\n"
    assert cap["image"] is None                       # v1: 이미지 슬롯 None


def test_detail_image_unknown_uid_404(monkeypatch):
    c = _client(monkeypatch, doc=None)
    r = c.post("/product/NOPE/detail-image", data={"draft": json.dumps(DRAFT)})
    assert r.status_code == 404


def test_detail_image_malformed_draft_400(monkeypatch):
    c = _client(monkeypatch)
    r = c.post("/product/P7863/detail-image", data={"draft": "{not json"})
    assert r.status_code == 400


def test_detail_image_absent_draft_regenerates(monkeypatch):
    c = _client(monkeypatch, draft_fn=lambda view, **k: DRAFT)
    r = c.post("/product/P7863/detail-image", data={})   # draft 없음 → 재생성 폴백
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
```

- [ ] **Step 3: 테스트 실패 확인**

Run: `python3 -m pytest tests/test_detail_image_routes.py -v`
Expected: FAIL — `AttributeError: module 'app.main' has no attribute 'detail_page'` (또는 404 라우트 없음)

- [ ] **Step 4: app/main.py 수정 — import + draft 라우트 uid + 이미지 라우트**

main.py 상단 import 블록을 교체:
```python
"""FastAPI 앱: 검색 → 인사이트 → 생성 → 상세페이지 이미지."""
import json
import pathlib
from urllib.parse import quote
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import data, generate, render, detail_page
from app.insight import build_view
from app.generate import GenerateError
```

draft 라우트의 성공 응답에 `uid` 추가(내보내기 버튼이 uid 를 알아야 함):
```python
        d = generate.draft(build_view(doc))
        return templates.TemplateResponse(request, "_draft.html", {"d": d, "uid": uid, "error": None})
```
(에러 응답도 `"uid": uid` 포함하도록 동일 패턴으로 수정:)
```python
    except GenerateError:
        return templates.TemplateResponse(request, "_draft.html", {"d": None, "uid": uid, "error": True})
```

파일 끝에 이미지 라우트 추가:
```python
@app.post("/product/{uid}/detail-image")
async def detail_image(uid: str, draft: str = Form(None)):
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
    html = detail_page.build_html(view, d, None)
    try:
        png = await render.html_to_png(html)
    except render.RenderError:
        return Response("이미지 생성 실패", status_code=500)
    fname = quote(f"{view['keyword']}_상세.png")
    return Response(png, media_type="image/png",
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{fname}"})
```

- [ ] **Step 5: app/templates/_draft.html 수정 — draft JSON + 내보내기 버튼**

`{% if error %}` 분기는 그대로 두고, `{% else %}` 의 `<div class=draft>` 바로 위(또는 아래)에 draft JSON 스크립트와 내보내기 컨트롤을 추가. `_draft.html` 의 `{% else %}` 블록을 다음으로 교체:
```html
{% else %}
<script type="application/json" id="draft-json">{{ d|tojson }}</script>
<div class=draft>
  <h3>제목 후보</h3><ul>{% for t in d.titles %}<li>{{ t }}</li>{% endfor %}</ul>
  <h3>핵심 셀링포인트</h3><ul>{% for s in d.selling_points %}<li>{{ s.text }} <span class=src>[{{ s.sources|join(', ') }}]</span></li>{% endfor %}</ul>
  <h3>타깃·사용씬 카피</h3><p>{{ d.target_copy }}</p>
  <h3>선제 대응 FAQ</h3><dl>{% for f in d.faqs %}<dt>{{ f.q }}</dt><dd>{{ f.a }}</dd>{% endfor %}</dl>
  {% if d.spec_highlights %}<h3>스펙 하이라이트</h3><ul>{% for s in d.spec_highlights %}<li>{{ s }}</li>{% endfor %}</ul>{% endif %}
  {% if d.price_positioning %}<h3>가격 포지셔닝</h3><p>{{ d.price_positioning }}</p>{% endif %}
</div>
<div class=export>
  <button id=exportbtn data-uid="{{ uid }}">이미지로 내보내기</button>
</div>
{% endif %}
```

- [ ] **Step 6: app/static/app.js 수정 — 내보내기 핸들러 추가**

`app.js` 끝에 별도 이벤트 위임 핸들러 추가(기존 `#genbtn` 핸들러는 그대로):
```javascript
document.addEventListener("click", async (e) => {
  const btn = e.target.closest("#exportbtn");
  if (!btn) return;
  const uid = btn.dataset.uid;
  const draftEl = document.getElementById("draft-json");
  if (!draftEl) return;
  const orig = btn.textContent;
  btn.disabled = true;
  btn.textContent = "이미지 생성 중…";
  try {
    const fd = new FormData();
    fd.append("draft", draftEl.textContent);
    const r = await fetch(`/product/${encodeURIComponent(uid)}/detail-image`, { method: "POST", body: fd });
    if (!r.ok) throw new Error(r.status);
    const blob = await r.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "상세페이지.png";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    btn.textContent = "다시 내보내기";
  } catch {
    alert("이미지 생성 실패. 다시 시도해 주세요.");
    btn.textContent = orig;
  } finally {
    btn.disabled = false;
  }
});
```

- [ ] **Step 7: 테스트 통과 + 전체 스위트 확인**

Run: `python3 -m pip install -r requirements.txt && python3 -m pytest tests/test_detail_image_routes.py -v && python3 -m pytest -q`
Expected: 이미지 라우트 4 passed; 전체 스위트 PASS(+ live/render skip).

- [ ] **Step 8: Commit**

```bash
git add app/main.py app/templates/_draft.html app/static/app.js requirements.txt tests/test_detail_image_routes.py
git commit -m "feat: v1 상세페이지 이미지 라우트(업로드 없음) + draft JSON 노출 + 내보내기 버튼"
```

---

## Task 4: v2 — 상품 사진 업로드로 슬롯 채우기

**Files:**
- Modify: `app/main.py`, `app/templates/_draft.html`, `app/static/app.js`
- Test: `tests/test_detail_image_routes.py` (추가)

**Interfaces:**
- Consumes: Task 3 의 이미지 라우트
- Produces: 라우트가 `photo: UploadFile` 받아 검증 후 base64 data URI 로 `build_html` 에 전달.

- [ ] **Step 1: 실패 테스트 작성** — `tests/test_detail_image_routes.py` 에 추가

```python
import io


def test_detail_image_v2_embeds_uploaded_photo(monkeypatch):
    cap = {}
    c = _client(monkeypatch, html_capture=cap)
    files = {"photo": ("p.png", io.BytesIO(b"\x89PNG\r\n\x1a\nfake"), "image/png")}
    r = c.post("/product/P7863/detail-image", data={"draft": json.dumps(DRAFT)}, files=files)
    assert r.status_code == 200
    assert cap["image"].startswith("data:image/png;base64,")   # 업로드가 data URI 로 임베드


def test_detail_image_rejects_non_image(monkeypatch):
    c = _client(monkeypatch)
    files = {"photo": ("p.txt", io.BytesIO(b"hello"), "text/plain")}
    r = c.post("/product/P7863/detail-image", data={"draft": json.dumps(DRAFT)}, files=files)
    assert r.status_code == 400


def test_detail_image_rejects_oversize(monkeypatch):
    c = _client(monkeypatch)
    big = io.BytesIO(b"\x89PNG" + b"x" * (8 * 1024 * 1024 + 1))
    files = {"photo": ("big.png", big, "image/png")}
    r = c.post("/product/P7863/detail-image", data={"draft": json.dumps(DRAFT)}, files=files)
    assert r.status_code == 400
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python3 -m pytest tests/test_detail_image_routes.py -k v2_embeds_uploaded_photo -v`
Expected: FAIL — `photo` 파라미터 없어 무시됨 → `cap["image"]` 가 None (AssertionError)

- [ ] **Step 3: app/main.py 이미지 라우트 수정 — photo 파라미터 + 검증**

import 에 `File, UploadFile` 추가:
```python
from fastapi import FastAPI, Request, Form, File, UploadFile
```
모듈 상수 추가(라우트 정의 위):
```python
_MAX_IMG = 8 * 1024 * 1024  # 8MB
```
`detail_image` 시그니처와 본문을 교체(`photo` 추가, `None` 자리에 `image_data_uri`):
```python
@app.post("/product/{uid}/detail-image")
async def detail_image(uid: str, draft: str = Form(None), photo: UploadFile = File(None)):
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
    image_data_uri = None
    if photo is not None:
        ctype = photo.content_type or ""
        if not ctype.startswith("image/"):
            return Response("이미지 파일만 업로드", status_code=400)
        raw = await photo.read()
        if len(raw) > _MAX_IMG:
            return Response("8MB 이하 이미지", status_code=400)
        import base64
        image_data_uri = f"data:{ctype};base64,{base64.b64encode(raw).decode()}"
    html = detail_page.build_html(view, d, image_data_uri)
    try:
        png = await render.html_to_png(html)
    except render.RenderError:
        return Response("이미지 생성 실패", status_code=500)
    fname = quote(f"{view['keyword']}_상세.png")
    return Response(png, media_type="image/png",
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{fname}"})
```

- [ ] **Step 4: app/templates/_draft.html 수정 — 파일 입력 추가**

`<div class=export>` 를 다음으로 교체(파일 입력 추가):
```html
<div class=export>
  <input type=file id=photo accept="image/*">
  <button id=exportbtn data-uid="{{ uid }}">이미지로 내보내기</button>
</div>
```

- [ ] **Step 5: app/static/app.js 수정 — 파일을 FormData 에 포함**

내보내기 핸들러의 `fd.append("draft", draftEl.textContent);` 바로 아래에 추가:
```javascript
    const photo = document.getElementById("photo");
    if (photo && photo.files[0]) fd.append("photo", photo.files[0]);
```

- [ ] **Step 6: 테스트 통과 + 전체 스위트 확인**

Run: `python3 -m pytest tests/test_detail_image_routes.py -v && python3 -m pytest -q`
Expected: 이미지 라우트 7 passed; 전체 스위트 PASS(+ live/render skip).

- [ ] **Step 7: Commit**

```bash
git add app/main.py app/templates/_draft.html app/static/app.js tests/test_detail_image_routes.py
git commit -m "feat: v2 상품 사진 업로드 → data URI 슬롯 채움 + 검증(이미지/8MB)"
```

---

## Task 5: README + Playwright 설치 안내 + 수동 스모크

**Files:**
- Modify: `README.md`
- Test: 전체 자동 스위트 재실행 + 수동 렌더 스모크

**Interfaces:**
- Consumes: Task 1~4 전체
- Produces: 없음(마감)

- [ ] **Step 1: README.md 수정 — 상세페이지 이미지 + Playwright 설치**

`## 설정` 의 `pip install -r requirements.txt` 아래에 추가:
```markdown
playwright install chromium    # 상세페이지 이미지 렌더용 (1회)
```

`## 구조` 목록에 추가:
```markdown
- `app/detail_page.py` — view+draft → self-contained 상세페이지 HTML(순수)
- `app/render.py` — Playwright HTML→PNG
```

`## 테스트` 에 한 줄 추가:
```markdown
python3 -m pytest -m render   # 실제 Playwright 렌더 스모크 (RUN_RENDER=1 + chromium 필요)
```

`## 실행` 아래에 사용법 추가:
```markdown
## 상세페이지 이미지

상품 화면에서 "상세페이지 생성" → "이미지로 내보내기"(선택: 상품 사진 업로드) → 상세페이지 PNG 다운로드.
사진을 안 올리면 사진 영역은 플레이스홀더로 렌더된다(v1).
```

- [ ] **Step 2: 전체 자동 스위트 재실행**

Run: `python3 -m pytest -q`
Expected: 전체 PASS (live/render skip). 신규 테스트(detail_page 4 + render 1 + 이미지 라우트 7) 포함.

- [ ] **Step 3: 수동 렌더 스모크 (실 Chromium)**

Chromium 설치 가능 환경에서:
```bash
python3 -m pip install pytest-asyncio
playwright install chromium
RUN_RENDER=1 python3 -m pytest tests/test_render.py -m render -v
```
Expected: PNG 매직바이트 검증 통과. (CI/실키 없으면 수동 단계로 남김 — 라이브 OpenAI 스모크와 동일 패턴.)

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: README 상세페이지 이미지 + Playwright 설치 안내"
```

---

## Self-Review (작성자 점검 완료)

**1. 스펙 커버리지:**
- detail_page.build_html(사진 슬롯 이음새, v1 플레이스홀더/v2 이미지) → Task 1 ✓
- 7섹션 레이아웃(히어로/셀링포인트/타깃/FAQ/스펙/가격/근거푸터) → Task 1 detail_page.html ✓
- self-contained(CSS·이미지 인라인) → Task 1 + test_build_html_is_self_contained ✓
- Playwright full_page 캡처 + RenderError → Task 2 ✓
- draft 클라이언트 재전송(LLM 재호출 0) + 부재 시 재생성 폴백 → Task 3 라우트·_draft.html·app.js ✓
- v2 업로드 data URI + 검증(image/*, 8MB) → Task 4 ✓
- 에러표(404/400/502/500, 독립성) → Task 3·4 라우트 + 테스트 ✓
- 테스트(순수 단위/라우트 모킹/렌더 마커) → Task 1~4 + Task 5 스모크 ✓
- business-model 비의존, detail_page 순수/render만 I/O → Global Constraints ✓

**2. 플레이스홀더 스캔:** 모든 코드 스텝에 실제 코드·명령·기대출력. TBD/TODO 없음 ✓

**3. 타입 일관성:** `build_html(view, draft, image_data_uri=None)` 시그니처가 Task 1 정의 ↔ Task 3·4 라우트 호출 ↔ 라우트 테스트 스파이에서 동일. `html_to_png(html)->bytes`(async)가 Task 2 정의 ↔ Task 3 라우트 `await` ↔ 테스트 async 모킹 일치. draft dict 키(titles/selling_points/target_copy/faqs/spec_highlights/price_positioning)가 detail_page.html ↔ 픽스처 ↔ _draft.html 일치. view 키가 기존 build_view 계약과 일치 ✓

# 셀러 상세페이지 최적화 툴 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 셀러가 우주 내 상품을 검색해 리뷰 근거 기반 셀링 인사이트를 보고, 버튼 하나로 상세페이지 초안을 생성하는 내부 웹앱을 만든다.

**Architecture:** FastAPI + Jinja 서버렌더 + 최소 JS. `business-model`의 Mongo `insights_demo.products`를 읽기 전용으로 소비한다(코드 비의존). `insight.build_view`는 DB·LLM과 무관한 순수 변환이고, `data.py`(Mongo)와 `generate.py`(OpenAI gpt-4o-mini)만 외부 I/O를 한다.

**Tech Stack:** Python 3.11+, FastAPI, Uvicorn, Jinja2, PyMongo, OpenAI SDK, pytest, mongomock, python-dotenv.

## Global Constraints

- `business-model` 코드는 절대 import 하지 않는다. Mongo를 데이터 계약으로만 의존한다.
- 데이터 소스: Mongo, DB명 env `INSIGHTS_DB` (기본 `insights_demo`), 컬렉션 `products`, `_id = uid`.
- 기본 접속 문자열: `mongodb://localhost:47017/?directConnection=true` (env `MONGO_URI`).
- 생성 모델: OpenAI `gpt-4o-mini` (env `OPENAI_MODEL` 로 덮어쓰기 가능). 키 env `OPENAI_API_KEY`.
- 부분 데이터에도 화면이 깨지지 않는다 — 모든 블록은 데이터 없으면 우아하게 숨김/회색.
- 생성은 인사이트 뷰모델만 LLM에 투입한다(원본 리뷰 원문을 통째로 넣지 않는다). 뷰모델에 없는 사실 생성 금지.
- 비밀키는 `.env` 로만. 절대 커밋하지 않는다(`.gitignore`에 `.env` 이미 포함).
- 모든 외부 I/O(Mongo, OpenAI)는 테스트에서 모킹/mongomock 으로 격리한다. 라이브 호출 테스트는 `@pytest.mark.live` 로 기본 skip.
- **UI 디자인 방향:** Dribbble "Lumos – Energy Management Dashboard" 참고. 아래 "UI 디자인 방향" 섹션의 디자인 토큰을 그대로 따른다(따뜻한 오프화이트 배경 #f2f0ec, 화이트 라운드 카드, 선셋 액센트 오렌지 #ff5a1f / 앰버 #ffb020, 큰 볼드 숫자, 부드러운 그림자, 라운드 18px).

## UI 디자인 방향 (Lumos 참고)

Dribbble shot "Lumos – Energy Management Dashboard"(Stan D. / RonDesignLab)의 비주얼 언어를 차용한다. 우리 앱은 에너지 대시보드가 아니지만 시각 언어가 잘 맞는다:

| Lumos 요소 | 우리 매핑 |
|---|---|
| 따뜻한 오프화이트 배경, 화이트 라운드 카드 + 소프트 섀도 | 검색결과·인사이트 블록 = 화이트 라운드 카드 |
| 큰 볼드 헤딩 + 작은 뮤트 라벨 | 상품명 = 큰 볼드 h1, 메타 = 뮤트 |
| 큰 볼드 숫자 + 작은 서브라벨(스탯 카드) | 리뷰 수 = 스탯 칩, 가격 = 큰 숫자 |
| 선셋 그라데이션(오렌지→앰버) 차트/게이지 | 빈도 n = 오렌지 알약 배지, 액센트 = 오렌지 |
| 상단 로고(오렌지 사선 바) + 헤더 | 헤더 로고 = 오렌지 사선 바 (CSS `.logo::before`) |
| 크림 톤 보조 영역 | 근거(evidence) 인용 = 크림 블록 |

디자인 토큰(Task 7 CSS 에서 구현):
`--bg:#f2f0ec` `--card:#fff` `--cream:#faf6f0` `--fg:#1a1a1a` `--muted:#938d83` `--line:#ece7df` `--accent:#ff5a1f` `--accent-2:#ffb020` `--radius:18px`, 그림자 `0 1px 2px rgba(20,16,10,.04),0 10px 30px rgba(20,16,10,.06)`, 시스템 산세리프, 숫자 볼드.

### 데이터 계약 (실측 필드 경로)

product 도큐먼트(`db.products`, `_id=uid`)에서 읽는 경로:

- `doc["keyword"]` (str), `doc["category_l1"]` (str), `doc["type"]` (`package`|`variant`|`single`)
- `doc["analyzed_count"]` (int), `doc["sources"]` (`{"naver":int,"youtube":int,"danawa":int}`), `doc["ad_flagged"]` (int)
- `doc["taxonomy"]["verdict"]["strengths"]` / `["weaknesses"]` — 각 항목:
  `{"point": str, "cited_examples": int, "evidence": [{"source": str, "kind": str, "is_ad": bool, "author": str, "date": "YYYYMMDD", "url": str, "title": str, "quote": str}]}`
- `doc["taxonomy"]["context"]` — `{"who": {...}, "when": {...}, "where": {...}, "why": {...}, "gift": {...}, "how_compatibility": {...}}`
  - `who` = `{age, gender, occupation, household, body_type, health, taste_pref, lifestyle}`
  - `when` = `{scene, season, event, time_of_day, frequency}`
  - `where` = `{place}`
  - `why` = `{positive_goal, negative_concern, workload}`
  - `gift` = `{recipient}`
  - 각 말단 값은 point 항목 리스트(strengths와 동일 shape). 빈 배열일 수 있음(항상 존재).
- `doc["identity"]` (상품 레벨) = `{"brand": str, "status": "pending"|"done"|"empty"|"error", "n_facts": int}` (없을 수 있음)
- `doc["catalogs"]` (list, package/variant는 여럿, single은 1) — 각 항목:
  `{"ctlg_no": str|int, "disp": str, "price_summary": {"min": int, "median": int, "low_mall": str, "n_malls": int, "spread_pct": int}, "identity": {<카테고리 컬럼 passthrough>, "gosi": {...}, "source": str, "fetched_at": ...}}`
  - `price_summary`·`identity`는 백필 단계에 따라 없을 수 있음.

---

## File Structure

- `requirements.txt` — 런타임+개발 의존성
- `.env.example` — 키/접속 문자열 템플릿 (실제 `.env`는 비커밋)
- `config.py` — env 로딩 (단일 출처)
- `app/__init__.py`
- `app/data.py` — Mongo 조회: `find_products`, `get_product` (외부 I/O)
- `app/insight.py` — 순수 변환: `build_view(doc) -> dict` + 내부 헬퍼
- `app/generate.py` — OpenAI gpt-4o-mini 호출: `draft(view) -> dict` (외부 I/O)
- `app/main.py` — FastAPI 앱, 3개 라우트
- `app/templates/` — `base.html`, `search.html`, `product.html`, `_draft.html`
- `app/static/app.css`, `app/static/app.js`
- `tests/fixtures/` — 실측 도큐먼트 기반 픽스처(JSON)
- `tests/test_insight.py`, `tests/test_data.py`, `tests/test_generate.py`, `tests/test_routes.py`
- `README.md`

### 뷰모델 계약 (build_view 반환 dict — 모든 소비자가 의존)

```python
{
  "uid": str,
  "keyword": str,
  "category_l1": str | None,
  "type": str,                       # package|variant|single
  "analyzed_count": int,
  "source_counts": {"naver": int, "youtube": int, "danawa": int},
  "ad_flagged": int,
  "strengths": [PointItem, ...],     # cited_examples 내림차순
  "weaknesses": [PointItem, ...],    # cited_examples 내림차순
  "targets": {                       # 라벨 그룹. 빈 그룹은 제외하지 않고 points=[] 로 유지
      "who":  [LabeledGroup, ...],
      "when": [LabeledGroup, ...],
      "where":[LabeledGroup, ...],
      "why":  [LabeledGroup, ...],
  },
  "gift": [PointItem, ...],          # context.gift.recipient
  "specs": [{"ctlg_no": str, "disp": str, "facts": {str: str}}, ...],   # catalogs[].identity 비어있지 않은 것만
  "identity_status": str | None,     # 상품 레벨 identity.status
  "price": {"min": int, "median": int, "low_mall": str, "n_malls": int, "spread_pct": int} | None,
}
# PointItem    = {"point": str, "n": int, "evidence": [{"source": str, "date": str, "url": str, "quote": str}, ...]}  # evidence는 url 있는 것 상위 2개, quote 120자 절단
# LabeledGroup = {"label": str, "points": [PointItem, ...]}
```

### 초안 계약 (generate.draft 반환 dict)

```python
{
  "titles": [str, str, str],
  "selling_points": [{"text": str, "sources": [str, ...]}, ...],
  "target_copy": str,
  "faqs": [{"q": str, "a": str}, ...],
  "spec_highlights": [str, ...],
  "price_positioning": str,          # 가격 정보 없으면 "" 빈 문자열
}
```

---

## Task 1: 프로젝트 스캐폴드 + config

**Files:**
- Create: `requirements.txt`, `.env.example`, `config.py`, `app/__init__.py`, `tests/__init__.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: 없음
- Produces: `config.settings` — `SimpleNamespace(mongo_uri: str, insights_db: str, openai_api_key: str, openai_model: str)`. `config.load_settings(env: dict|None=None) -> SimpleNamespace`.

- [ ] **Step 1: requirements.txt 작성**

```
fastapi==0.115.*
uvicorn[standard]==0.32.*
jinja2==3.1.*
pymongo==4.10.*
openai==1.54.*
python-dotenv==1.0.*
pytest==8.3.*
mongomock==4.2.*
httpx==0.27.*
```

- [ ] **Step 2: .env.example 작성**

```
MONGO_URI=mongodb://localhost:47017/?directConnection=true
INSIGHTS_DB=insights_demo
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
```

- [ ] **Step 3: 빈 패키지 파일 생성**

`app/__init__.py` 와 `tests/__init__.py` 를 빈 파일로 생성.

- [ ] **Step 4: 실패 테스트 작성** — `tests/test_config.py`

```python
from config import load_settings


def test_load_settings_reads_env_with_defaults():
    s = load_settings({"OPENAI_API_KEY": "sk-test"})
    assert s.mongo_uri == "mongodb://localhost:47017/?directConnection=true"
    assert s.insights_db == "insights_demo"
    assert s.openai_api_key == "sk-test"
    assert s.openai_model == "gpt-4o-mini"


def test_load_settings_overrides_from_env():
    s = load_settings({
        "MONGO_URI": "mongodb://h:1/?directConnection=true",
        "INSIGHTS_DB": "insights",
        "OPENAI_API_KEY": "sk-x",
        "OPENAI_MODEL": "gpt-4o",
    })
    assert s.insights_db == "insights"
    assert s.openai_model == "gpt-4o"
```

- [ ] **Step 5: 테스트 실패 확인**

Run: `python -m pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'config'`

- [ ] **Step 6: config.py 구현**

```python
"""환경 설정 단일 출처. .env 는 python-dotenv 로 로드(선택), 없으면 os.environ."""
import os
from types import SimpleNamespace

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


def load_settings(env=None):
    env = os.environ if env is None else env
    return SimpleNamespace(
        mongo_uri=env.get("MONGO_URI", "mongodb://localhost:47017/?directConnection=true"),
        insights_db=env.get("INSIGHTS_DB", "insights_demo"),
        openai_api_key=env.get("OPENAI_API_KEY", ""),
        openai_model=env.get("OPENAI_MODEL", "gpt-4o-mini"),
    )


settings = load_settings()
```

- [ ] **Step 7: 의존성 설치 + 테스트 통과 확인**

Run: `python -m pip install -r requirements.txt && python -m pytest tests/test_config.py -v`
Expected: PASS (2 passed)

- [ ] **Step 8: Commit**

```bash
git add requirements.txt .env.example config.py app/__init__.py tests/__init__.py tests/test_config.py
git commit -m "feat: 프로젝트 스캐폴드 + config 로딩"
```

---

## Task 2: insight 헬퍼 (순수 함수)

PointItem 정규화와 정렬을 담당하는 작은 순수 함수들. 이후 `build_view`가 이걸 조합한다.

**Files:**
- Create: `app/insight.py` (헬퍼만)
- Test: `tests/test_insight.py` (헬퍼 부분)

**Interfaces:**
- Consumes: 없음
- Produces:
  - `_norm_point(raw: dict) -> dict` — `{point, cited_examples, evidence}` → PointItem `{point, n, evidence:[{source,date,url,quote}]}`. evidence는 `url` 있는 항목 상위 2개, `quote` 120자 절단.
  - `_points(items: list) -> list[dict]` — 리스트를 PointItem 리스트로 정규화하고 `n`(cited_examples) 내림차순 정렬. None/빈 입력 → `[]`.

- [ ] **Step 1: 실패 테스트 작성** — `tests/test_insight.py`

```python
from app.insight import _norm_point, _points


def test_norm_point_trims_evidence_and_quote():
    raw = {
        "point": "간편하게 조리할 수 있다.",
        "cited_examples": 2,
        "evidence": [
            {"source": "naver", "date": "20260604", "url": "http://a", "quote": "x" * 200},
            {"source": "danawa", "date": "20251229", "url": "http://b", "quote": "ok"},
            {"source": "naver", "date": "20260101", "url": None, "quote": "no url"},
        ],
    }
    p = _norm_point(raw)
    assert p["point"] == "간편하게 조리할 수 있다."
    assert p["n"] == 2
    assert len(p["evidence"]) == 2                      # url 없는 항목 제외 + 상위 2개
    assert len(p["evidence"][0]["quote"]) == 120        # 절단
    assert p["evidence"][0]["url"] == "http://a"


def test_norm_point_handles_missing_fields():
    p = _norm_point({"point": "x"})
    assert p == {"point": "x", "n": 0, "evidence": []}


def test_points_sorts_desc_by_n_and_handles_none():
    items = [{"point": "a", "cited_examples": 1}, {"point": "b", "cited_examples": 5}]
    out = _points(items)
    assert [p["point"] for p in out] == ["b", "a"]
    assert _points(None) == []
    assert _points([]) == []
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_insight.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.insight'`

- [ ] **Step 3: app/insight.py 헬퍼 구현**

```python
"""product 도큐먼트 → 셀링 인사이트 뷰모델. DB·LLM 무관 순수 변환."""

_QUOTE_MAX = 120


def _norm_point(raw):
    """taxonomy point 항목 → PointItem. evidence는 url 있는 것 상위 2개, quote 절단."""
    raw = raw or {}
    ev = []
    for e in (raw.get("evidence") or []):
        if not e or not e.get("url"):
            continue
        ev.append({
            "source": e.get("source") or "",
            "date": e.get("date") or "",
            "url": e.get("url"),
            "quote": (e.get("quote") or "")[:_QUOTE_MAX],
        })
        if len(ev) == 2:
            break
    return {"point": raw.get("point") or "", "n": raw.get("cited_examples") or 0, "evidence": ev}


def _points(items):
    """point 항목 리스트 → PointItem 리스트, n 내림차순 정렬."""
    out = [_norm_point(it) for it in (items or []) if it]
    out.sort(key=lambda p: p["n"], reverse=True)
    return out
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_insight.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add app/insight.py tests/test_insight.py
git commit -m "feat: insight PointItem 정규화/정렬 헬퍼"
```

---

## Task 3: insight.build_view (6블록 조립)

**Files:**
- Modify: `app/insight.py` (build_view + 라벨 상수 추가)
- Create: `tests/fixtures/product_full.json`, `tests/fixtures/product_degraded.json`
- Test: `tests/test_insight.py` (build_view 부분 추가)

**Interfaces:**
- Consumes: `_points` (Task 2)
- Produces: `build_view(doc: dict) -> dict` — 위 "뷰모델 계약" dict 반환.

- [ ] **Step 1: 풀데이터 픽스처 작성** — `tests/fixtures/product_full.json`

```json
{
  "_id": "P7863",
  "keyword": "쿡시 사골 미역국 쌀국수",
  "category_l1": "식품",
  "type": "package",
  "analyzed_count": 224,
  "sources": {"naver": 20, "youtube": 184, "danawa": 20},
  "ad_flagged": 1,
  "identity": {"brand": "쿡시", "status": "done", "n_facts": 6},
  "taxonomy": {
    "verdict": {
      "strengths": [
        {"point": "간편하게 조리할 수 있다.", "cited_examples": 5,
         "evidence": [{"source": "naver", "date": "20260604", "url": "http://a", "quote": "쉽게 준비"}]},
        {"point": "국물이 깊다.", "cited_examples": 2,
         "evidence": [{"source": "danawa", "date": "20251229", "url": "http://b", "quote": "사골 진함"}]}
      ],
      "weaknesses": [
        {"point": "면이 쉽게 분다.", "cited_examples": 3,
         "evidence": [{"source": "naver", "date": "20260101", "url": "http://c", "quote": "불음"}]}
      ]
    },
    "context": {
      "who": {"household": [{"point": "부모님과 함께", "cited_examples": 2, "evidence": [{"source":"naver","date":"20260101","url":"http://d","quote":"부모님"}]}],
              "age": [], "gender": [], "occupation": [], "body_type": [], "health": [], "taste_pref": [], "lifestyle": []},
      "when": {"scene": [{"point": "야식으로", "cited_examples": 1, "evidence": []}], "season": [], "event": [], "time_of_day": [], "frequency": []},
      "where": {"place": []},
      "why": {"positive_goal": [], "negative_concern": [], "workload": []},
      "gift": {"recipient": [{"point": "부모님댁 선물", "cited_examples": 1, "evidence": [{"source":"danawa","date":"20251229","url":"http://e","quote":"부모님댁에도 보냈다"}]}]}
    }
  },
  "catalogs": [
    {"ctlg_no": "1001", "disp": "96g 12개", "price_summary": {"min": 9900, "median": 11000, "low_mall": "쿠팡", "n_malls": 4, "spread_pct": 12},
     "identity": {"material": "쌀,사골농축액", "origin": "대한민국", "mfg_date": "20260101", "source": "official", "gosi": {}}},
    {"ctlg_no": "1002", "disp": "96g 24개", "price_summary": {"min": 18000, "median": 20000, "low_mall": "11번가", "n_malls": 3, "spread_pct": 8}, "identity": {}}
  ]
}
```

- [ ] **Step 2: 열화 픽스처 작성** — `tests/fixtures/product_degraded.json`

식품이 아닌, 백필 전 single 상품: taxonomy 일부 빈 셀, identity pending, price_summary 없음.

```json
{
  "_id": "S5500",
  "keyword": "무지 반팔티",
  "category_l1": "의류",
  "type": "single",
  "analyzed_count": 12,
  "sources": {"naver": 12, "youtube": 0, "danawa": 0},
  "ad_flagged": 0,
  "identity": {"brand": null, "status": "pending", "n_facts": 0},
  "taxonomy": {
    "verdict": {"strengths": [], "weaknesses": []},
    "context": {
      "who": {"age": [], "gender": [], "occupation": [], "household": [], "body_type": [], "health": [], "taste_pref": [], "lifestyle": []},
      "when": {"scene": [], "season": [], "event": [], "time_of_day": [], "frequency": []},
      "where": {"place": []},
      "why": {"positive_goal": [], "negative_concern": [], "workload": []},
      "gift": {"recipient": []}
    }
  },
  "catalogs": [{"ctlg_no": "5500", "disp": "단품", "identity": {}}]
}
```

- [ ] **Step 3: build_view 실패 테스트 작성** — `tests/test_insight.py` 에 추가

```python
import json
import pathlib
from app.insight import build_view

FIX = pathlib.Path(__file__).parent / "fixtures"


def _load(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def test_build_view_full_assembles_six_blocks():
    v = build_view(_load("product_full.json"))
    assert v["uid"] == "P7863"
    assert v["keyword"] == "쿡시 사골 미역국 쌀국수"
    assert v["type"] == "package"
    assert v["source_counts"]["youtube"] == 184
    # 강점/약점 빈도 정렬
    assert [s["point"] for s in v["strengths"]] == ["간편하게 조리할 수 있다.", "국물이 깊다."]
    assert v["weaknesses"][0]["point"] == "면이 쉽게 분다."
    # 타깃: who 그룹 라벨, 빈 그룹은 points=[] 로 유지
    who_labels = {g["label"]: g["points"] for g in v["targets"]["who"]}
    assert "가구" in who_labels and who_labels["가구"][0]["point"] == "부모님과 함께"
    assert who_labels["나이"] == []
    # 선물
    assert v["gift"][0]["point"] == "부모님댁 선물"
    # 정형 사실: identity 비어있지 않은 catalog만
    assert len(v["specs"]) == 1
    assert v["specs"][0]["facts"]["origin"] == "대한민국"
    assert "gosi" not in v["specs"][0]["facts"]      # gosi/source/fetched_at 메타 제외
    assert v["identity_status"] == "done"
    # 가격: catalog price_summary 집계(median 최저 기준 대표 1건)
    assert v["price"]["min"] == 9900
    assert v["price"]["low_mall"] == "쿠팡"


def test_build_view_degraded_hides_missing_blocks_without_crash():
    v = build_view(_load("product_degraded.json"))
    assert v["strengths"] == []
    assert v["weaknesses"] == []
    assert v["specs"] == []                           # identity 빈 dict → 제외
    assert v["identity_status"] == "pending"
    assert v["price"] is None                         # price_summary 없음
    # 모든 타깃 그룹 존재하되 points 빈 리스트
    assert all(g["points"] == [] for g in v["targets"]["who"])
```

- [ ] **Step 4: 테스트 실패 확인**

Run: `python -m pytest tests/test_insight.py -v`
Expected: FAIL — `ImportError: cannot import name 'build_view'`

- [ ] **Step 5: build_view 구현** — `app/insight.py` 에 추가

```python
# 컨텍스트 dim 라벨 (한국어 표시용). 키 순서 = 화면 표시 순서.
_WHO = [("age", "나이"), ("gender", "성별"), ("occupation", "직업"), ("household", "가구"),
        ("body_type", "체형"), ("health", "건강"), ("taste_pref", "취향"), ("lifestyle", "라이프스타일")]
_WHEN = [("scene", "상황"), ("season", "계절"), ("event", "이벤트"), ("time_of_day", "시간대"), ("frequency", "빈도")]
_WHERE = [("place", "장소")]
_WHY = [("positive_goal", "목표"), ("negative_concern", "우려"), ("workload", "수고")]

# catalog identity passthrough 시 facts 에서 제외할 메타 키
_IDENTITY_META = {"gosi", "source", "fetched_at", "insight_uid", "ctlg_no", "brand"}


def _groups(ctx_dim, spec):
    """context 하위 dim(dict) → LabeledGroup 리스트. 빈 그룹도 points=[] 로 유지."""
    ctx_dim = ctx_dim or {}
    return [{"label": label, "points": _points(ctx_dim.get(key))} for key, label in spec]


def _facts(identity):
    """catalog identity dict → 표시용 facts (메타 키 제외, 값 있는 것만)."""
    identity = identity or {}
    return {k: str(v) for k, v in identity.items() if k not in _IDENTITY_META and v not in (None, "", {}, [])}


def _price(catalogs):
    """catalogs price_summary 중 min 최저 1건을 대표로. 없으면 None."""
    prs = [c.get("price_summary") for c in (catalogs or []) if (c.get("price_summary") or {}).get("min")]
    if not prs:
        return None
    best = min(prs, key=lambda p: p["min"])
    return {"min": best.get("min"), "median": best.get("median"), "low_mall": best.get("low_mall"),
            "n_malls": best.get("n_malls") or 0, "spread_pct": best.get("spread_pct") or 0}


def build_view(doc):
    """product 도큐먼트 → 6블록 뷰모델 dict. 부분 데이터에도 안전."""
    doc = doc or {}
    tax = doc.get("taxonomy") or {}
    verdict = tax.get("verdict") or {}
    ctx = tax.get("context") or {}
    catalogs = doc.get("catalogs") or []
    specs = []
    for c in catalogs:
        facts = _facts(c.get("identity"))
        if facts:
            specs.append({"ctlg_no": str(c.get("ctlg_no") or ""), "disp": c.get("disp") or "", "facts": facts})
    return {
        "uid": doc.get("_id") or "",
        "keyword": doc.get("keyword") or "",
        "category_l1": doc.get("category_l1"),
        "type": doc.get("type") or "",
        "analyzed_count": doc.get("analyzed_count") or 0,
        "source_counts": doc.get("sources") or {},
        "ad_flagged": doc.get("ad_flagged") or 0,
        "strengths": _points(verdict.get("strengths")),
        "weaknesses": _points(verdict.get("weaknesses")),
        "targets": {
            "who": _groups(ctx.get("who"), _WHO),
            "when": _groups(ctx.get("when"), _WHEN),
            "where": _groups(ctx.get("where"), _WHERE),
            "why": _groups(ctx.get("why"), _WHY),
        },
        "gift": _points((ctx.get("gift") or {}).get("recipient")),
        "specs": specs,
        "identity_status": (doc.get("identity") or {}).get("status"),
        "price": _price(catalogs),
    }
```

- [ ] **Step 6: 테스트 통과 확인**

Run: `python -m pytest tests/test_insight.py -v`
Expected: PASS (5 passed)

- [ ] **Step 7: Commit**

```bash
git add app/insight.py tests/test_insight.py tests/fixtures/product_full.json tests/fixtures/product_degraded.json
git commit -m "feat: insight.build_view 6블록 조립 + 픽스처"
```

---

## Task 4: data.py (Mongo 조회)

**Files:**
- Create: `app/data.py`
- Test: `tests/test_data.py`

**Interfaces:**
- Consumes: `config.settings` (Task 1)
- Produces:
  - `find_products(q: str, limit: int = 30, db=None) -> list[dict]` — `keyword` 부분일치(대소문자 무시). 각 dict `{uid, keyword, category_l1, type, analyzed_count, source_counts}`. q 빈 문자열 → `[]`.
  - `get_product(uid: str, db=None) -> dict | None` — `_id=uid` 단일 도큐먼트 원본.
  - `get_db()` — 실 Mongo 핸들(런타임용). 테스트는 `db=` 주입으로 우회.

- [ ] **Step 1: 실패 테스트 작성** — `tests/test_data.py`

```python
import mongomock
from app import data


def _seed():
    db = mongomock.MongoClient().db
    db.products.insert_many([
        {"_id": "P1", "keyword": "쿡시 미역국", "category_l1": "식품", "type": "package",
         "analyzed_count": 100, "sources": {"naver": 20}},
        {"_id": "P2", "keyword": "신라면", "category_l1": "식품", "type": "single",
         "analyzed_count": 50, "sources": {"naver": 10}},
    ])
    return db


def test_find_products_partial_case_insensitive():
    db = _seed()
    out = data.find_products("미역", db=db)
    assert len(out) == 1
    assert out[0]["uid"] == "P1"
    assert out[0]["keyword"] == "쿡시 미역국"
    assert out[0]["source_counts"] == {"naver": 20}


def test_find_products_empty_query_returns_empty():
    db = _seed()
    assert data.find_products("", db=db) == []
    assert data.find_products("   ", db=db) == []


def test_find_products_no_keyword_match_returns_empty():
    db = _seed()
    # category_l1 에는 '식품' 이 있지만 keyword 매칭만 하므로 '식' 은 0건
    assert data.find_products("식", db=db) == []


def test_find_products_respects_limit():
    db = mongomock.MongoClient().db
    db.products.insert_many([
        {"_id": f"P{i}", "keyword": f"라면 {i}", "category_l1": "식품", "type": "single",
         "analyzed_count": i, "sources": {}} for i in range(5)
    ])
    out = data.find_products("라면", limit=2, db=db)
    assert len(out) == 2
    # analyzed_count 내림차순 → 가장 큰 두 개
    assert [p["uid"] for p in out] == ["P4", "P3"]


def test_get_product_returns_doc_or_none():
    db = _seed()
    assert data.get_product("P1", db=db)["keyword"] == "쿡시 미역국"
    assert data.get_product("nope", db=db) is None
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_data.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.data'`

- [ ] **Step 3: app/data.py 구현**

```python
"""Mongo insights_demo.products 읽기 전용 조회. business-model 비의존."""
import re
from pymongo import MongoClient
from config import settings

_client = None


def get_db():
    """런타임용 Mongo DB 핸들(싱글톤)."""
    global _client
    if _client is None:
        _client = MongoClient(settings.mongo_uri)
    return _client[settings.insights_db]


def _shape(doc):
    return {
        "uid": doc.get("_id"),
        "keyword": doc.get("keyword") or "",
        "category_l1": doc.get("category_l1"),
        "type": doc.get("type") or "",
        "analyzed_count": doc.get("analyzed_count") or 0,
        "source_counts": doc.get("sources") or {},
    }


def find_products(q, limit=30, db=None):
    """keyword 부분일치(대소문자 무시) 검색. q 비면 빈 리스트."""
    q = (q or "").strip()
    if not q:
        return []
    db = db if db is not None else get_db()
    rx = re.compile(re.escape(q), re.IGNORECASE)
    cur = db.products.find(
        {"keyword": rx},
        {"keyword": 1, "category_l1": 1, "type": 1, "analyzed_count": 1, "sources": 1},
    ).sort("analyzed_count", -1).limit(limit)
    return [_shape(d) for d in cur]


def get_product(uid, db=None):
    """_id=uid 단일 도큐먼트 원본 반환(없으면 None)."""
    db = db if db is not None else get_db()
    return db.products.find_one({"_id": uid})
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_data.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add app/data.py tests/test_data.py
git commit -m "feat: data.py Mongo 검색/조회 (mongomock 테스트)"
```

---

## Task 5: generate.py (OpenAI gpt-4o-mini)

**Files:**
- Create: `app/generate.py`
- Test: `tests/test_generate.py`

**Interfaces:**
- Consumes: 뷰모델 dict (Task 3 build_view 출력), `config.settings` (Task 1)
- Produces:
  - `build_prompt(view: dict) -> list[dict]` — OpenAI messages(system+user). system 에 "뷰모델에 없는 사실 생성 금지" 규칙 포함. user 에 뷰모델 요약.
  - `draft(view: dict, client=None) -> dict` — "초안 계약" dict. OpenAI 호출 → JSON 파싱. 파싱 실패 시 1회 재시도, 그래도 실패면 `GenerateError` 발생.
  - `GenerateError(Exception)`
  - `DRAFT_SCHEMA` — response_format json_schema dict.

- [ ] **Step 1: 실패 테스트 작성** — `tests/test_generate.py`

```python
import json
import pytest
from app import generate


SAMPLE_VIEW = {
    "keyword": "쿡시 미역국", "category_l1": "식품", "type": "package",
    "strengths": [{"point": "간편 조리", "n": 5, "evidence": [{"source": "naver", "url": "http://a", "quote": "쉽다"}]}],
    "weaknesses": [{"point": "면이 분다", "n": 3, "evidence": []}],
    "targets": {"who": [{"label": "가구", "points": [{"point": "부모님과", "n": 2, "evidence": []}]}], "when": [], "where": [], "why": []},
    "gift": [], "specs": [{"ctlg_no": "1", "disp": "12개", "facts": {"origin": "대한민국"}}],
    "price": {"min": 9900, "low_mall": "쿠팡", "n_malls": 4, "spread_pct": 12, "median": 11000},
}

VALID_DRAFT = {
    "titles": ["t1", "t2", "t3"],
    "selling_points": [{"text": "간편하게 조리", "sources": ["naver"]}],
    "target_copy": "부모님과 함께 드세요",
    "faqs": [{"q": "면이 붇나요?", "a": "조리 시간을 지키세요"}],
    "spec_highlights": ["원산지 대한민국"],
    "price_positioning": "쿠팡 최저 9900원",
}


class _FakeResp:
    def __init__(self, content):
        self.choices = [type("C", (), {"message": type("M", (), {"content": content})})]


class _FakeClient:
    """chat.completions.create 모킹. 미리 준 content 들을 순서대로 반환."""
    def __init__(self, contents):
        self._contents = list(contents)
        self.calls = []
        self.chat = type("Chat", (), {"completions": self})()

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeResp(self._contents.pop(0))


def test_build_prompt_includes_rule_and_view():
    msgs = generate.build_prompt(SAMPLE_VIEW)
    assert msgs[0]["role"] == "system"
    assert "없는 사실" in msgs[0]["content"]            # 환각 금지 규칙
    assert "간편 조리" in msgs[1]["content"]            # 뷰모델 강점 투입


def test_draft_parses_valid_json():
    client = _FakeClient([json.dumps(VALID_DRAFT, ensure_ascii=False)])
    out = generate.draft(SAMPLE_VIEW, client=client)
    assert out["titles"] == ["t1", "t2", "t3"]
    assert out["selling_points"][0]["sources"] == ["naver"]
    assert client.calls[0]["model"] == "gpt-4o-mini"


def test_draft_retries_once_on_bad_json_then_succeeds():
    client = _FakeClient(["not json{", json.dumps(VALID_DRAFT, ensure_ascii=False)])
    out = generate.draft(SAMPLE_VIEW, client=client)
    assert out["target_copy"] == "부모님과 함께 드세요"
    assert len(client.calls) == 2                        # 재시도 발생


def test_draft_raises_after_two_failures():
    client = _FakeClient(["bad1", "bad2"])
    with pytest.raises(generate.GenerateError):
        generate.draft(SAMPLE_VIEW, client=client)
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_generate.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.generate'`

- [ ] **Step 3: app/generate.py 구현**

```python
"""인사이트 뷰모델 → 상세페이지 초안 (OpenAI gpt-4o-mini). 뷰모델만 투입(원문 미투입)."""
import json
from config import settings


class GenerateError(Exception):
    pass


_SYSTEM = (
    "너는 한국 이커머스 상세페이지 카피라이터다. 주어진 '상품 인사이트'(실제 리뷰에서 검증·집계된 "
    "강점·약점·타깃·정형사실·가격)만 근거로 상세페이지 초안을 쓴다. "
    "인사이트에 없는 사실은 절대 지어내지 않는다. 각 셀링포인트에는 근거가 된 출처(naver/youtube/danawa)를 "
    "sources 필드에 단다. 약점은 숨기지 말고 '선제 대응 FAQ'로 전환한다. "
    "반드시 지정된 JSON 스키마로만 응답한다."
)

DRAFT_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "listing_draft",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["titles", "selling_points", "target_copy", "faqs", "spec_highlights", "price_positioning"],
            "properties": {
                "titles": {"type": "array", "items": {"type": "string"}, "minItems": 3, "maxItems": 3},
                "selling_points": {
                    "type": "array",
                    "items": {
                        "type": "object", "additionalProperties": False,
                        "required": ["text", "sources"],
                        "properties": {"text": {"type": "string"},
                                       "sources": {"type": "array", "items": {"type": "string"}}},
                    },
                },
                "target_copy": {"type": "string"},
                "faqs": {
                    "type": "array",
                    "items": {"type": "object", "additionalProperties": False,
                              "required": ["q", "a"],
                              "properties": {"q": {"type": "string"}, "a": {"type": "string"}}},
                },
                "spec_highlights": {"type": "array", "items": {"type": "string"}},
                "price_positioning": {"type": "string"},
            },
        },
    },
}


def _summarize(view):
    """뷰모델을 프롬프트용 간결 텍스트로. evidence 원문은 짧게만."""
    lines = [f"상품명: {view.get('keyword')}", f"카테고리: {view.get('category_l1')}", f"타입: {view.get('type')}"]
    if view.get("strengths"):
        lines.append("강점(빈도순):")
        for s in view["strengths"]:
            src = ",".join(sorted({e["source"] for e in s.get("evidence") or [] if e.get("source")})) or "리뷰"
            lines.append(f"  - {s['point']} (근거 {s['n']}건, 출처 {src})")
    if view.get("weaknesses"):
        lines.append("약점(빈도순, FAQ로 선제대응):")
        for w in view["weaknesses"]:
            lines.append(f"  - {w['point']} (근거 {w['n']}건)")
    tgt = []
    for dim in ("who", "when", "where", "why"):
        for g in view.get("targets", {}).get(dim, []):
            for p in g["points"]:
                tgt.append(f"{g['label']}:{p['point']}")
    if tgt:
        lines.append("타깃/사용맥락: " + "; ".join(tgt))
    if view.get("gift"):
        lines.append("선물수요: " + "; ".join(p["point"] for p in view["gift"]))
    if view.get("specs"):
        facts = []
        for sp in view["specs"]:
            facts += [f"{k}={v}" for k, v in sp["facts"].items()]
        lines.append("정형 사실: " + ", ".join(facts))
    pr = view.get("price")
    if pr:
        lines.append(f"가격: 최저 {pr['min']}원({pr.get('low_mall')}), 중앙 {pr.get('median')}원, "
                     f"{pr.get('n_malls')}개몰, 가격차 {pr.get('spread_pct')}%")
    return "\n".join(lines)


def build_prompt(view):
    return [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": "다음 인사이트로 상세페이지 초안을 작성하라.\n\n" + _summarize(view)},
    ]


def _get_client(client):
    if client is not None:
        return client
    from openai import OpenAI
    return OpenAI(api_key=settings.openai_api_key)


def draft(view, client=None):
    """뷰모델 → 초안 dict. 파싱 실패 시 1회 재시도, 그래도 실패면 GenerateError."""
    client = _get_client(client)
    messages = build_prompt(view)
    last = None
    for _ in range(2):
        resp = client.chat.completions.create(
            model=settings.openai_model,
            messages=messages,
            response_format=DRAFT_SCHEMA,
            temperature=0.5,
        )
        content = resp.choices[0].message.content
        try:
            return json.loads(content)
        except (ValueError, TypeError) as e:
            last = e
    raise GenerateError(f"초안 JSON 파싱 실패: {last}")
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_generate.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add app/generate.py tests/test_generate.py
git commit -m "feat: generate.py gpt-4o-mini 초안 생성(스키마 강제·재시도, 모킹 테스트)"
```

---

## Task 6: main.py FastAPI 라우트 + 템플릿

**Files:**
- Create: `app/main.py`, `app/templates/base.html`, `app/templates/search.html`, `app/templates/product.html`, `app/templates/_draft.html`
- Test: `tests/test_routes.py`

**Interfaces:**
- Consumes: `data.find_products`, `data.get_product` (Task 4), `insight.build_view` (Task 3), `generate.draft` (Task 5)
- Produces: `app.main.app` (FastAPI). 라우트: `GET /`, `GET /product/{uid}`, `POST /product/{uid}/draft`. 테스트 주입을 위해 `data`/`generate` 모듈을 모듈 속성으로 참조(monkeypatch 가능).

- [ ] **Step 1: 실패 테스트 작성** — `tests/test_routes.py`

```python
import json
import pathlib
from fastapi.testclient import TestClient
from app import main

FIX = pathlib.Path(__file__).parent / "fixtures"
DOC = json.loads((FIX / "product_full.json").read_text(encoding="utf-8"))


def _client(monkeypatch, *, products=None, doc=None, draft=None, draft_exc=None):
    monkeypatch.setattr(main.data, "find_products", lambda q, **k: products or [])
    monkeypatch.setattr(main.data, "get_product", lambda uid, **k: doc)
    def _draft(view, **k):
        if draft_exc:
            raise draft_exc
        return draft
    monkeypatch.setattr(main.generate, "draft", _draft)
    return TestClient(main.app)


def test_search_empty_shows_no_results(monkeypatch):
    c = _client(monkeypatch, products=[])
    r = c.get("/?q=없는상품")
    assert r.status_code == 200
    assert "결과 없음" in r.text


def test_search_lists_products(monkeypatch):
    c = _client(monkeypatch, products=[{"uid": "P7863", "keyword": "쿡시 미역국", "category_l1": "식품", "type": "package", "analyzed_count": 224, "source_counts": {"naver": 20}}])
    r = c.get("/?q=미역")
    assert "쿡시 미역국" in r.text
    assert "/product/P7863" in r.text


def test_product_renders_insight_blocks(monkeypatch):
    c = _client(monkeypatch, doc=DOC)
    r = c.get("/product/P7863")
    assert r.status_code == 200
    assert "간편하게 조리할 수 있다." in r.text          # 강점
    assert "면이 쉽게 분다." in r.text                   # 약점
    assert "상세페이지 생성" in r.text                   # 생성 버튼


def test_product_unknown_uid_404(monkeypatch):
    c = _client(monkeypatch, doc=None)
    assert c.get("/product/nope").status_code == 404


def test_draft_success_returns_fragment(monkeypatch):
    draft = {"titles": ["A", "B", "C"], "selling_points": [{"text": "간편", "sources": ["naver"]}],
             "target_copy": "부모님과", "faqs": [{"q": "Q1", "a": "A1"}], "spec_highlights": ["원산지"], "price_positioning": "최저 9900"}
    c = _client(monkeypatch, doc=DOC, draft=draft)
    r = c.post("/product/P7863/draft")
    assert r.status_code == 200
    assert "A1" in r.text and "간편" in r.text


def test_draft_failure_returns_error_fragment_not_500(monkeypatch):
    from app.generate import GenerateError
    c = _client(monkeypatch, doc=DOC, draft_exc=GenerateError("x"))
    r = c.post("/product/P7863/draft")
    assert r.status_code == 200
    assert "생성 실패" in r.text
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_routes.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.main'`

- [ ] **Step 3: 템플릿 작성** — `app/templates/base.html`

```html
<!doctype html><html lang=ko><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>{% block title %}셀러 툴{% endblock %}</title>
<link rel=stylesheet href="/static/app.css"></head>
<body><header><a href="/" class=logo>셀러 상세페이지 툴</a></header>
<main>{% block body %}{% endblock %}</main>
<script src="/static/app.js"></script></body></html>
```

- [ ] **Step 4: 템플릿 작성** — `app/templates/search.html`

```html
{% extends "base.html" %}
{% block body %}
<form method=get action="/" class=search>
  <input name=q value="{{ q|e }}" placeholder="상품 키워드 검색" autofocus>
  <button>검색</button>
</form>
{% if q %}
  {% if products %}
  <ul class=results>
    {% for p in products %}
    <li><a href="/product/{{ p.uid }}">
      <span class=kw>{{ p.keyword }}</span>
      <span class=meta>{{ p.category_l1 or '미분류' }} · {{ p.type }} · 리뷰 {{ p.analyzed_count }}</span>
    </a></li>
    {% endfor %}
  </ul>
  {% else %}
  <p class=empty>결과 없음. 다른 키워드를 시도해 보세요.</p>
  {% endif %}
{% endif %}
{% endblock %}
```

- [ ] **Step 5: 템플릿 작성** — `app/templates/product.html`

```html
{% extends "base.html" %}
{% block title %}{{ v.keyword }}{% endblock %}
{% block body %}
<a href="/" class=back>← 검색</a>
<h1>{{ v.keyword }}</h1>
<p class=hero>{{ v.category_l1 or '미분류' }} · {{ v.type }}</p>
<div class=stats>
  <div class=stat><span class=num>{{ v.analyzed_count }}</span><span class=lbl>분석 리뷰</span></div>
  <div class=stat><span class=num>{{ v.source_counts.get('naver',0) }}</span><span class=lbl>네이버</span></div>
  <div class=stat><span class=num>{{ v.source_counts.get('youtube',0) }}</span><span class=lbl>유튜브</span></div>
  <div class=stat><span class=num>{{ v.source_counts.get('danawa',0) }}</span><span class=lbl>다나와</span></div>
  {% if v.ad_flagged %}<div class=stat><span class=num>{{ v.ad_flagged }}</span><span class=lbl>광고글</span></div>{% endif %}
</div>

<section><h2>강점 — 셀링포인트 후보</h2>
{% if v.strengths %}<ul class=points>
  {% for s in v.strengths %}<li><b>{{ s.point }}</b> <span class=n>{{ s.n }}</span>
    {% if s.evidence %}<details><summary>근거</summary>
      {% for e in s.evidence %}<blockquote>“{{ e.quote }}” <a href="{{ e.url }}" target=_blank>{{ e.source }} {{ e.date }}</a></blockquote>{% endfor %}
    </details>{% endif %}</li>{% endfor %}
</ul>{% else %}<p class=muted>아직 강점 데이터 없음</p>{% endif %}</section>

<section><h2>약점 — 선제 대응 포인트</h2>
{% if v.weaknesses %}<ul class=points>
  {% for w in v.weaknesses %}<li><b>{{ w.point }}</b> <span class=n>{{ w.n }}</span></li>{% endfor %}
</ul>{% else %}<p class=muted>아직 약점 데이터 없음</p>{% endif %}</section>

<section><h2>타깃 고객</h2>
{% for dim, groups in v.targets.items() %}
  {% for g in groups %}{% if g.points %}
    <div class=tgt><span class=label>{{ g.label }}</span>
      {% for p in g.points %}<span class=tag>{{ p.point }} <span class=n>{{ p.n }}</span></span>{% endfor %}
    </div>
  {% endif %}{% endfor %}
{% endfor %}
{% if v.gift %}<div class=tgt><span class=label>선물</span>
  {% for p in v.gift %}<span class=tag>{{ p.point }}</span>{% endfor %}</div>{% endif %}
</section>

{% if v.specs %}<section><h2>정형 사실</h2>
  {% for sp in v.specs %}<div class=spec><b>{{ sp.disp }}</b>
    {% for k, val in sp.facts.items() %}<span class=fact>{{ k }}: {{ val }}</span>{% endfor %}</div>{% endfor %}
</section>{% elif v.identity_status in ('pending', 'empty') %}<p class=muted>정형 정보 준비 중</p>{% endif %}

{% if v.price %}<section><h2>가격 포지션</h2>
  <p class=price><span class=price-big>{{ "{:,}".format(v.price.min) }}원</span> 최저 · {{ v.price.low_mall }}</p>
  <p class=muted>중앙 {{ "{:,}".format(v.price.median) }}원 · {{ v.price.n_malls }}개 몰 · 가격차 {{ v.price.spread_pct }}%</p>
</section>{% endif %}

<section class=gen>
  <button id=genbtn data-uid="{{ v.uid }}">상세페이지 생성</button>
  <div id=draft></div>
</section>
{% endblock %}
```

- [ ] **Step 6: 템플릿 작성** — `app/templates/_draft.html`

```html
{% if error %}
<p class=err>생성 실패. 다시 시도해 주세요.</p>
{% else %}
<div class=draft>
  <h3>제목 후보</h3><ul>{% for t in d.titles %}<li>{{ t }}</li>{% endfor %}</ul>
  <h3>핵심 셀링포인트</h3><ul>{% for s in d.selling_points %}<li>{{ s.text }} <span class=src>[{{ s.sources|join(', ') }}]</span></li>{% endfor %}</ul>
  <h3>타깃·사용씬 카피</h3><p>{{ d.target_copy }}</p>
  <h3>선제 대응 FAQ</h3><dl>{% for f in d.faqs %}<dt>{{ f.q }}</dt><dd>{{ f.a }}</dd>{% endfor %}</dl>
  {% if d.spec_highlights %}<h3>스펙 하이라이트</h3><ul>{% for s in d.spec_highlights %}<li>{{ s }}</li>{% endfor %}</ul>{% endif %}
  {% if d.price_positioning %}<h3>가격 포지셔닝</h3><p>{{ d.price_positioning }}</p>{% endif %}
</div>
{% endif %}
```

- [ ] **Step 7: app/main.py 구현**

```python
"""FastAPI 앱: 검색 → 인사이트 → 생성. data/generate 는 테스트 주입 위해 모듈 참조."""
import pathlib
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import data, generate
from app.insight import build_view
from app.generate import GenerateError

_HERE = pathlib.Path(__file__).parent
templates = Jinja2Templates(directory=str(_HERE / "templates"))

app = FastAPI(title="셀러 상세페이지 툴")
app.mount("/static", StaticFiles(directory=str(_HERE / "static")), name="static")


@app.get("/", response_class=HTMLResponse)
def search(request: Request, q: str = ""):
    products = data.find_products(q) if q.strip() else []
    return templates.TemplateResponse("search.html", {"request": request, "q": q, "products": products})


@app.get("/product/{uid}", response_class=HTMLResponse)
def product(request: Request, uid: str):
    doc = data.get_product(uid)
    if doc is None:
        return HTMLResponse("<h1>404 · 상품을 찾을 수 없습니다</h1><a href=\"/\">검색으로</a>", status_code=404)
    return templates.TemplateResponse("product.html", {"request": request, "v": build_view(doc)})


@app.post("/product/{uid}/draft", response_class=HTMLResponse)
def draft(request: Request, uid: str):
    doc = data.get_product(uid)
    if doc is None:
        return HTMLResponse("<p class=err>상품을 찾을 수 없습니다.</p>", status_code=404)
    try:
        d = generate.draft(build_view(doc))
        return templates.TemplateResponse("_draft.html", {"request": request, "d": d, "error": None})
    except GenerateError:
        return templates.TemplateResponse("_draft.html", {"request": request, "d": None, "error": True})
```

- [ ] **Step 8: static 플레이스홀더 생성**

테스트 시 StaticFiles 마운트가 디렉토리를 요구하므로 빈 파일이라도 둔다.

```bash
mkdir -p app/static
printf '/* placeholder */\n' > app/static/app.css
printf '// placeholder\n' > app/static/app.js
```

- [ ] **Step 9: 테스트 통과 확인**

Run: `python -m pytest tests/test_routes.py -v`
Expected: PASS (6 passed)

- [ ] **Step 10: Commit**

```bash
git add app/main.py app/templates/ app/static/
git add tests/test_routes.py
git commit -m "feat: FastAPI 3라우트 + 템플릿 (검색/인사이트/생성)"
```

---

## Task 7: static 마감(CSS/JS) + README + 수동 스모크

**Files:**
- Modify: `app/static/app.css`, `app/static/app.js`
- Create: `README.md`
- Test: 수동 스모크 (자동 테스트 전체 재실행 포함)

**Interfaces:**
- Consumes: Task 6 의 `#genbtn[data-uid]`, `POST /product/{uid}/draft`, `#draft`
- Produces: 없음(최종 마감)

- [ ] **Step 1: app/static/app.js 작성 — 생성 버튼 비동기 호출**

```javascript
document.addEventListener("click", async (e) => {
  const btn = e.target.closest("#genbtn");
  if (!btn) return;
  const uid = btn.dataset.uid;
  const out = document.getElementById("draft");
  btn.disabled = true;
  out.innerHTML = "<p class=muted>생성 중…</p>";
  try {
    const r = await fetch(`/product/${encodeURIComponent(uid)}/draft`, { method: "POST" });
    out.innerHTML = await r.text();
    btn.textContent = "다시 생성";
  } catch {
    out.innerHTML = "<p class=err>생성 실패. 다시 시도해 주세요.</p>";
  } finally {
    btn.disabled = false;
  }
});
```

- [ ] **Step 2: app/static/app.css 작성 — Lumos 디자인 시스템**

Dribbble "Lumos – Energy Management Dashboard" 비주얼 언어(따뜻한 오프화이트 배경, 화이트 라운드 카드 + 소프트 섀도, 선셋 오렌지/앰버 액센트, 큰 볼드 숫자, 라운드 18px). "UI 디자인 방향" 섹션의 토큰을 구현한다.

```css
:root {
  --bg:#f2f0ec; --card:#fff; --cream:#faf6f0; --fg:#1a1a1a; --muted:#938d83;
  --line:#ece7df; --accent:#ff5a1f; --accent-2:#ffb020; --radius:18px;
  --shadow:0 1px 2px rgba(20,16,10,.04), 0 10px 30px rgba(20,16,10,.06);
}
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--fg);
  font:15px/1.6 -apple-system,"Segoe UI",system-ui,sans-serif; -webkit-font-smoothing:antialiased; }
header { display:flex; align-items:center; padding:16px 28px; }
.logo { display:flex; align-items:center; gap:9px; font-weight:800; font-size:17px; color:var(--fg); text-decoration:none; }
.logo::before { content:""; width:22px; height:16px;
  background:repeating-linear-gradient(115deg,var(--accent) 0 3px,transparent 3px 6px); border-radius:2px; }
main { max-width:880px; margin:0 auto; padding:8px 20px 64px; }
h1 { font-size:30px; font-weight:800; letter-spacing:-.02em; margin:.2em 0 .1em; }
h2 { font-size:15px; font-weight:700; margin:0 0 12px; }
.muted, .meta, .empty { color:var(--muted); }
.back { color:var(--accent); text-decoration:none; font-weight:600; font-size:14px; }
/* 검색 */
.search { display:flex; gap:10px; margin:18px 0; }
.search input { flex:1; padding:14px 16px; border:1px solid var(--line); border-radius:14px;
  background:var(--card); font-size:15px; box-shadow:var(--shadow); }
.search input:focus { outline:none; border-color:var(--accent); }
.search button, .gen button { border:0; border-radius:14px; padding:14px 22px; cursor:pointer;
  background:var(--accent); color:#fff; font-weight:700; font-size:15px; }
.search button:hover, .gen button:hover { background:#e94e16; }
.results { list-style:none; padding:0; margin:0; }
.results a { display:flex; justify-content:space-between; align-items:center; gap:12px;
  background:var(--card); border-radius:14px; box-shadow:var(--shadow);
  padding:16px 18px; margin-bottom:10px; text-decoration:none; color:inherit; }
.results a:hover { transform:translateY(-1px); transition:transform .1s; }
.kw { font-weight:700; }
.meta, .src { font-size:13px; }
.empty { text-align:center; padding:48px; }
/* hero + 스탯 칩 */
.hero { color:var(--muted); font-size:14px; margin:.1em 0 1em; }
.stats { display:flex; flex-wrap:wrap; gap:10px; margin-bottom:8px; }
.stat { background:var(--card); border-radius:14px; box-shadow:var(--shadow);
  padding:12px 18px; min-width:96px; }
.stat .num { display:block; font-size:22px; font-weight:800; letter-spacing:-.01em; }
.stat .lbl { font-size:12px; color:var(--muted); }
/* 카드 섹션 */
section { background:var(--card); border-radius:var(--radius); box-shadow:var(--shadow);
  padding:20px 22px; margin-top:16px; }
/* 강점/약점 포인트 */
.points { list-style:none; padding:0; margin:0; }
.points li { padding:10px 0; border-bottom:1px solid var(--line); }
.points li:last-child { border-bottom:0; }
.points b { font-weight:600; }
.n { display:inline-block; min-width:22px; text-align:center; padding:1px 9px; margin-left:6px;
  background:#fff2ea; color:var(--accent); border-radius:999px; font-size:12px; font-weight:700; }
details summary { cursor:pointer; color:var(--muted); font-size:13px; margin-top:6px; }
blockquote { margin:8px 0 0; padding:10px 14px; background:var(--cream); border-radius:12px;
  border-left:3px solid var(--accent-2); color:#5b554c; font-size:13px; }
blockquote a { color:var(--muted); text-decoration:none; }
/* 타깃 */
.tgt { display:flex; align-items:flex-start; gap:10px; margin:8px 0; flex-wrap:wrap; }
.label { min-width:68px; color:var(--muted); font-size:13px; padding-top:5px; }
.tag { display:inline-block; padding:5px 12px; background:#f6f3ee; border-radius:999px;
  margin:2px; font-size:13px; }
/* 정형 사실 */
.spec { padding:8px 0; border-bottom:1px solid var(--line); }
.spec:last-child { border-bottom:0; }
.fact { display:inline-block; margin:2px 14px 2px 0; color:#4a463f; font-size:13px; }
/* 가격 */
.price { margin:0; }
.price-big { font-size:28px; font-weight:800; letter-spacing:-.01em; margin-right:6px; }
/* 생성 */
.gen { background:transparent; box-shadow:none; text-align:center; padding:14px 0; }
.gen button { border-radius:999px; padding:14px 30px; }
#draft { margin-top:14px; text-align:left; }
.draft h3 { font-size:14px; font-weight:700; margin:16px 0 6px; }
.draft .src { color:var(--accent); font-weight:600; }
.draft dt { font-weight:600; margin-top:8px; }
.draft dd { margin:2px 0 0; color:#4a463f; }
.err { color:#c0392b; }
```

- [ ] **Step 3: README.md 작성**

````markdown
# sellering-tools — 셀러 상세페이지 최적화 툴

`business-model`이 만든 상품 인사이트(Mongo `insights_demo.products`)를 읽어,
셀러가 상품을 검색 → 리뷰 근거 기반 셀링 인사이트 열람 → 상세페이지 초안 생성(OpenAI gpt-4o-mini)하는 내부 웹앱.

## 설정

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # OPENAI_API_KEY 등 채우기
```

## 실행

```bash
uvicorn app.main:app --reload --port 8800
# http://localhost:8800
```

Mongo(`insights_demo`)가 포트 47017에 떠 있어야 인사이트가 보인다(읽기 전용).

## 테스트

```bash
python -m pytest -q            # 외부 서비스 없이 전부 통과(Mongo/OpenAI 모킹)
python -m pytest -m live       # OPENAI_API_KEY 있을 때만, 실제 생성 스모크
```

## 구조

- `app/data.py` — Mongo 조회(읽기 전용)
- `app/insight.py` — product 도큐먼트 → 6블록 뷰모델(순수 함수)
- `app/generate.py` — 뷰모델 → 초안(gpt-4o-mini, JSON 스키마 강제)
- `app/main.py` — FastAPI 3라우트
- `docs/superpowers/specs|plans/` — 설계·구현 문서

## 경계

`business-model` 코드는 import 하지 않는다. Mongo를 데이터 계약으로만 의존한다.
````

- [ ] **Step 4: pytest live 마커 등록 + 라이브 스모크 추가** — `pyproject.toml` 생성, `tests/test_generate.py` 에 추가

`pyproject.toml`:

```toml
[tool.pytest.ini_options]
markers = ["live: 실제 OpenAI 호출(기본 skip, 키 필요)"]
```

`tests/test_generate.py` 끝에 추가:

```python
import os
import pytest


@pytest.mark.live
@pytest.mark.skipif(not os.environ.get("OPENAI_API_KEY"), reason="OPENAI_API_KEY 없음")
def test_draft_live_smoke():
    out = generate.draft(SAMPLE_VIEW)
    assert len(out["titles"]) == 3
    assert isinstance(out["selling_points"], list)
```

- [ ] **Step 5: 전체 자동 테스트 재실행**

Run: `python -m pytest -q`
Expected: PASS (전체 통과, live 1건 skip)

- [ ] **Step 6: 수동 스모크 체크리스트**

Mongo `insights_demo` 가 떠 있는 환경에서:
1. `uvicorn app.main:app --port 8800` 실행, 에러 없이 부팅
2. `/` 에서 실제 키워드(예: "미역국") 검색 → 결과 카드 노출
3. 카드 클릭 → 인사이트 화면, 강점/약점/타깃 블록 렌더, 부분 데이터도 안 깨짐
4. (키 설정 시) "상세페이지 생성" 클릭 → 초안 6종 노출, 근거 출처 태그 표시
5. 빈 데이터 상품 1건 확인 → "준비 중"/회색 처리로 우아하게 표시

- [ ] **Step 7: Commit**

```bash
git add app/static/ README.md pyproject.toml tests/test_generate.py
git commit -m "feat: UI 마감(CSS/JS) + README + 라이브 스모크 마커"
```

---

## Self-Review (작성자 점검 완료)

**1. 스펙 커버리지:**
- 6블록 인사이트 표면 → Task 3 build_view + Task 6 product.html ✓
- 생성 6종(제목/셀링포인트/타깃카피/FAQ/스펙/가격) → Task 5 DRAFT_SCHEMA + _draft.html ✓
- 우주 내 검색만 → Task 4 find_products ✓
- gpt-4o-mini + JSON 스키마 + 근거강제 → Task 5 ✓
- 부분 데이터 비파괴 → Task 3 degraded 픽스처 + Task 6 라우트 테스트 + 템플릿 조건부 ✓
- 에러 처리(검색0건/404/생성실패/빈셀) → Task 4·6 테스트로 커버 ✓
- 테스트 전략(순수함수 단위/LLM 모킹/라우트/라이브 스모크) → Task 2~7 ✓
- business-model 비의존, Mongo 데이터 계약 → Global Constraints + data.py ✓

**2. 플레이스홀더 스캔:** 모든 코드 스텝에 실제 코드·명령·기대출력 명시. TBD/TODO 없음 ✓

**3. 타입 일관성:** 뷰모델/초안 dict 키가 build_view ↔ generate ↔ 템플릿 ↔ 테스트에서 동일(`strengths[].point/n/evidence`, `targets.{dim}[].label/points`, `price.{min,median,low_mall,n_malls,spread_pct}`, 초안 `titles/selling_points/target_copy/faqs/spec_highlights/price_positioning`). `find_products` 출력 키(`uid/keyword/category_l1/type/analyzed_count/source_counts`)가 search.html 과 일치 ✓

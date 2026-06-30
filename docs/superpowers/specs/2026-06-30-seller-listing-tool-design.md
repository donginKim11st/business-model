# 셀러 상세페이지 최적화 툴 — 설계 문서

작성일: 2026-06-30
상태: 설계 승인 (브레인스토밍 완료, 구현 플랜 대기)

## 한 줄 정의

셀러가 우주 내 상품을 검색해 **리뷰 근거 기반 셀링 인사이트**를 보고, 버튼 하나로
**상세페이지 초안**을 생성하는 내부 웹앱.

## 배경 — 데이터 토대

이 툴은 별도 프로젝트 `~/Work/business-model`이 만들어낸 상품 데이터를 **읽기 전용으로 소비**한다.

- 저장소: Mongo `insights_demo.products` (포트 47017, directConnection)
- 조인 키: `_id = uid`. 타입별 — package `P{bndl_grp}`, variant `P{bndl_grp}::{value}`, single `S{ctlg_no}`
- 각 도큐먼트 구성:
  - **정형(identity)** — 공식 페이지 추출 사실. per-SKU는 `catalogs[].identity`(소재·원산지·제조일·style_code 등, 카테고리 불가지 passthrough), 상품 레벨은 `products.identity = {brand, status, n_facts}` (status: pending|done|empty|error)
  - **비정형(insight)** — 네이버 리뷰/유튜브/다나와에서 추출한 **택소노미**. `tree.taxonomy.context.{who,when,where,why,gift}` + `verdict.strengths/weaknesses`. 각 항목은 `cited_examples`(빈도 proxy)와 `evidence[]`(원문 인용·출처·날짜·URL)를 가짐. 모든 dim 키는 빈 배열이어도 항상 존재(빈 셀 = 해당 관점 없음)
  - **가격** — `catalogs[].price_summary` (몰별 가격 정보)

**경계 원칙:** `business-model` 코드는 절대 import 하지 않는다. Mongo를 **데이터 계약**으로만 의존한다.

## 범위 (v1)

| 결정 | v1 |
|---|---|
| 두 제품(셀러 툴 / 사용자 툴) | **셀러 툴만**. 사용자 툴은 별도 스펙→플랜→구현 사이클 |
| 셀러 페르소나 | 미고정 — 데이터가 주는 가치로 타깃을 정한다. 입점·리셀러/브랜드사/종합몰 MD 모두 후보 |
| 히어로 의사결정 | **"어떻게 팔까" = 상세페이지 최적화** |
| 출력 형태 | **인사이트 표면(코어) → 생성(그 위 한 단계)**. 계층화 |
| 런타임 | **인터랙티브 웹앱** |
| 상품 범위 | **우주 내 검색만**. 온디맨드 추출·URL 가져오기 없음 |
| 생성 모델 | **OpenAI `gpt-4o-mini`** |

## 아키텍처 — FastAPI + Jinja + 최소 JS

```
sellering-tools/                  (새 repo, 읽기 전용 데이터 소비자)
├── app/
│   ├── main.py                   FastAPI 진입점, 3개 라우트
│   ├── data.py                   Mongo 조회 (insights_demo.products, 읽기 전용) — 외부 I/O
│   ├── insight.py                product 도큐먼트 → 셀링 인사이트 뷰모델 (순수 함수)
│   ├── generate.py               뷰모델 → 프롬프트 → gpt-4o-mini → 상세페이지 초안 — 외부 I/O
│   ├── templates/                search.html, product.html, _insight.html, _draft.html
│   └── static/                   최소 CSS, generate 버튼용 JS
├── tests/                        insight.py 순수함수 단위테스트 중심 + fixtures/
├── config.py / .env              MONGO_URI, OPENAI_API_KEY
└── README.md
```

**3개 라우트:**
- `GET /` — 검색창 + 결과 (키워드/카테고리로 `products` 조회)
- `GET /product/{uid}` — 인사이트 표면 렌더 (코어 화면)
- `POST /product/{uid}/draft` — 생성 호출 (비동기 fetch, 초안 HTML 조각 반환)

**경계/격리 원칙:**
- `business-model` 비의존 — Mongo만 읽음
- `insight.py`는 DB·LLM과 무관한 **순수 변환** (테스트 용이)
- `data.py`(Mongo), `generate.py`(OpenAI)만 외부 I/O — 격리

대안 검토: (B) FastAPI JSON API + React SPA → v1엔 오버엔지니어링(빌드체인·두 런타임, 페르소나 미정인데 UX 과투자). (C) Streamlit/Gradio → 프로토타입 최속이나 상세페이지 미리보기 레이아웃 자유도·프로덕션 외형 약함. **A 채택** — 팀의 Python·HTML 맥락 일치, 나중에 B로 갈 때 API 경계가 자연 발생.

## 인사이트 표면 (코어 화면) — 6블록

`insight.build_view(doc)`가 product 도큐먼트를 6블록 뷰모델로 변환. 모든 항목은 실제 리뷰 인용(evidence)과 빈도 proxy(cited_examples)를 단다.

1. **한눈에 (Hero)** — 상품명·카테고리·타입(단품/패키지/변형), 분석 리뷰 수(naver/youtube/danawa 출처별), 광고글 비율 플래그
2. **강점 — 셀링포인트 후보** ⭐ — `verdict.strengths` 빈도순. 요약 문장 + 인용 예시 수 + 대표 리뷰 1~2(출처·날짜·링크). 상세페이지 핵심 불릿의 원천
3. **약점 — 선제 대응 포인트** — `verdict.weaknesses` 빈도순. "상세페이지에서 미리 해소하라" 관점 → FAQ·반박 카피 원천
4. **타깃 고객** — `context.who`(나이/성별/직업/가구/체형/건강/취향/라이프스타일), `when`(상황/계절/이벤트/빈도), `where`(장소), `why`(긍정 목표/부정 우려). 빈 셀은 회색 처리
5. **선물 적합성** — `context.gift.recipient`. 선물 수요 있으면 "선물용 소구" 섹션 카피로 연결
6. **정형 사실 & 가격 포지션** — `catalogs[].identity`(소재·원산지·제조일 등) 스펙 신뢰 소구 + `catalogs[].price_summary` 몰별 분포로 포지션 한 줄

**핵심 결정:** 모든 인사이트 항목은 **클릭하면 evidence(원문 인용+링크) 펼침**. 셀러가 카피를 신뢰하고, 생성 초안도 "온주 근거"를 인용할 수 있게 함 — 이 데이터의 차별점.

## 생성 계층 — 인사이트 → 상세페이지 초안

`POST /product/{uid}/draft`. `generate.draft(view)`가 인사이트 뷰모델을 받아 gpt-4o-mini로 초안 생성.

**핵심:** 이미 계산된 **인사이트 뷰모델만** 프롬프트에 투입. 원본 리뷰 수천 건을 LLM에 넣지 않음(비용·환각 통제).

**입력:** 6블록 뷰모델(강점·약점·타깃·선물·정형·가격) + 각 항목 evidence 인용 텍스트.

**출력 (구조화 초안 6종, JSON 스키마로 강제):**
- 제목 후보 3종 — 강점·타깃 키워드 조합
- 핵심 셀링포인트 불릿 — 강점 상위 N, 각 불릿에 evidence 출처 태그 필드
- 타깃·사용씬 카피 — who/when/why 기반 한 문단
- 선제 대응 FAQ — 약점 상위 항목을 Q&A로 전환
- 스펙 하이라이트 — 정형 사실 중 소구 포인트
- 가격 포지셔닝 한 줄 — 몰별 분포 기반 (선택적)

**설계 결정:**
1. **모델:** OpenAI `gpt-4o-mini` (OpenAI SDK, JSON mode / structured outputs로 출력 6종을 JSON 스키마 강제 → 파싱 안정성)
2. **근거 강제:** 시스템 규칙 — "뷰모델에 없는 사실 금지, 각 셀링포인트에 evidence 출처 필드 필수". 환각 방지 = 신뢰의 핵심
3. **결정성:** 초안은 **편집 출발점**. 셀러가 화면에서 복사·수정. v1은 재생성 버튼만, 인라인 편집기는 범위 밖
4. **API 키:** 새 repo 자체 `.env`(`OPENAI_API_KEY`)로 독립. business-model 비의존

## 데이터 흐름

```
[검색] GET /?q=키워드
   → data.find_products(q)   (Mongo 텍스트/정규식 조회, 상위 N)
   → search.html 렌더 (상품 카드: 이름·카테고리·리뷰수)

[인사이트] GET /product/{uid}
   → data.get_product(uid)   (단일 도큐먼트)
   → insight.build_view(doc) (순수 변환 → 6블록 뷰모델)
   → product.html 렌더 (+ "상세페이지 생성" 버튼)

[생성] POST /product/{uid}/draft   (버튼 클릭, fetch)
   → insight.build_view(doc) 재사용
   → generate.draft(view)    (gpt-4o-mini, JSON 스키마)
   → _draft.html 조각 반환 → 버튼 아래 삽입
```

## 에러 처리

핵심 원칙: **부분 데이터에도 화면이 깨지지 않는다.** insight 데이터는 카테고리·백필 단계마다 채워짐이 다름 → 모든 블록이 "없으면 우아하게 숨김/회색". 생성 실패가 인사이트 열람을 막지 않음(독립).

| 코드패스 | 무엇이 잘못되나 | 사용자가 보는 것 |
|---|---|---|
| 검색 0건 | 키워드 매칭 없음 | "결과 없음" + 추천 키워드 |
| uid 없음/잘못됨 | 잘못된 링크·삭제 | 404 페이지, 검색으로 복귀 |
| 인사이트 빈 셀 | taxonomy dim이 빈 배열(정상) | 회색 "해당 관점 없음" — 빈 화면 아님 |
| identity status=empty/pending | 정형 추출 아직/불가 | "정형 정보 준비 중" 배지, 인사이트 정상 표시 |
| price_summary 부재 | 가격 백필 전 | 가격 블록 숨김 (깨지지 않음) |
| OpenAI 호출 실패/타임아웃 | API 4xx/5xx/네트워크 | 버튼 아래 "생성 실패, 다시 시도" — 인사이트 화면 유지 |
| OpenAI JSON 파싱 실패 | 스키마 어긋난 응답 | 1회 재시도 후 실패 메시지 |
| Mongo 연결 끊김 | DB 다운 | 503 + "데이터 연결 확인" (운영자 로그) |

## 테스트 전략

**① 단위 — `insight.build_view` (코어, 가장 두껍게)**
순수 함수. 픽스처는 실제 Mongo 도큐먼트 1~2건을 `tests/fixtures/*.json`으로 고정.
케이스: 정상 풀데이터 / 빈 taxonomy 셀 / identity status=empty / price_summary 부재 / package(다중 catalogs) vs single / 강점·약점 빈도 정렬 / evidence 인용 매핑.

**② 단위 — `generate.draft` (LLM 모킹)**
OpenAI 호출 모킹. 검증: (a) 프롬프트에 뷰모델이 올바로 들어가는지, (b) 스키마 응답을 6종 구조로 파싱하는지, (c) 파싱 실패 시 1회 재시도, (d) "뷰모델에 없는 사실 금지" 규칙 포함 여부.
별도 얇은 **라이브 스모크 1개**(`@pytest.mark.live`, 기본 skip) — 키 있을 때 실제 gpt-4o-mini가 유효 JSON 주는지 수동 확인.

**③ 라우트 — FastAPI `TestClient`**
`data.py` 모킹. 3개 라우트 HTTP 동작: 검색 0건 → "결과 없음", uid 없음 → 404, 정상 → 200 + 블록 렌더, 생성 실패 → 인사이트 유지 + 에러 조각.

**범위 밖 (v1):** E2E 브라우저 테스트, 부하 테스트. 내부용·소규모라 과함. 수동 체크리스트로 충분.

**의존성 격리 보상:** `data.py`/`generate.py`만 외부 I/O. 나머지 순수 → 테스트 대부분이 외부 서비스 없이 돈다.

## 범위 밖 (NOT in scope, v1)

- 사용자(소비자) 툴 — 별도 사이클
- URL 가져오기 / 온디맨드 추출 (우주 내 검색만)
- 인라인 상세페이지 편집기 (재생성 버튼까지만)
- React/SPA 프런트, JSON API 분리
- E2E·부하 테스트
- 셀러 인증·멀티테넌시·과금

## 향후 (확장 포인트)

- 사용자 툴 (다음 제품)
- URL 메칭 로드맵 (설계는 확장 가능하게, 구현은 검색 먼저)
- 인라인 편집기 + 저장
- 페르소나 확정 후 UX 심화 → 필요 시 B(SPA)로 전환 (API 경계 이미 존재)

# sellering-tools — 셀러 상세페이지 최적화 툴

`business-model`이 만든 상품 인사이트(Mongo `insights_demo.products`)를 읽어,
셀러가 상품을 검색 → 리뷰 근거 기반 셀링 인사이트 열람 → 상세페이지 초안 생성(OpenAI gpt-4o-mini)하는 내부 웹앱.

## 설정

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium    # 상세페이지 이미지 렌더용 (1회)
cp .env.example .env           # 아래 환경변수 채우기
```

### 환경변수 (`.env`)

| 변수 | 필수 | 설명 |
|------|:---:|------|
| `OPENAI_API_KEY` | ✅ | 초안 생성용 OpenAI 키. https://platform.openai.com/api-keys 에서 발급(`sk-...`) |
| `OPENAI_MODEL` | | 기본 `gpt-4o-mini` (초안 건당 ≈ 0.25원). `gpt-4o`로 올리면 비용 급증(건당 4~6원대) |
| `MONGO_URI` | | 기본 `mongodb://localhost:47017/?directConnection=true` |
| `INSIGHTS_DB` | | 기본 `insights_demo` |
| `NAVER_CLIENT_ID` / `NAVER_CLIENT_SECRET` | | 상품 사진 추천(네이버 이미지 검색)용. https://developers.naver.com 에서 발급. 없으면 추천 기능만 비활성 |

- **`.env`는 `.gitignore`로 커밋되지 않는다** — 키가 저장소에 올라가지 않는다.
- 키를 넣거나 바꾼 뒤 서버를 **재시작**한다. `--reload`는 `.py`만 감시하므로 `.env` 변경은 반영되지 않는다.
- 키가 없으면 "상세페이지 생성"이 `OPENAI_API_KEY가 설정되지 않았습니다`로 **명확히 실패**한다(초안 실패 사유는 화면·서버 로그에 표시된다).

## 실행

```bash
./run.sh          # 권장: 환경 점검(.env·의존성·Mongo) + 기존 인스턴스 정리 후 기동
# PORT=9000 ./run.sh 로 포트 변경
# http://localhost:8800
```

수동 실행:

```bash
uvicorn app.main:app --reload --port 8800
```

Mongo(`insights_demo`)가 포트 47017에 떠 있어야 인사이트가 보인다(읽기 전용).

## 테스트

```bash
python -m pytest -q            # 외부 서비스 없이 전부 통과(Mongo/OpenAI 모킹)
python -m pytest -m live       # OPENAI_API_KEY 있을 때만, 실제 생성 스모크
python3 -m pytest -m render   # 실제 Playwright 렌더 스모크 (RUN_RENDER=1 + chromium 필요)
```

## 구조

- `app/data.py` — Mongo 조회(읽기 전용)
- `app/insight.py` — product 도큐먼트 → 6블록 뷰모델(순수 함수)
- `app/generate.py` — 뷰모델 → 초안(gpt-4o-mini, JSON 스키마 강제)
- `app/detail_page.py` — view+draft → self-contained 상세페이지 HTML(순수)
- `app/render.py` — Playwright HTML→PNG
- `app/main.py` — FastAPI 3라우트
- `docs/superpowers/specs|plans/` — 설계·구현 문서

## 경계

`business-model` 코드는 import 하지 않는다. Mongo를 데이터 계약으로만 의존한다.

## 상세페이지 이미지

상품 화면에서 "상세페이지 생성" → 슬롯별(히어로/디테일/사용씬/보조)로 상품 사진을 배정 →
디자인 스타일 선택 → "이미지로 내보내기" → 적응형 에디토리얼 PDP PNG 다운로드.
- **스타일 2종**: `contrast`(톤 교차, 기본)·`airy`(밝은 에디토리얼). 타이포는 Pretendard(HTML에 임베딩).
- **사진 추천**: 슬롯별 "사진 추천" → 네이버 이미지 검색 결과를 클릭하면 해당 슬롯에 반영(`NAVER_CLIENT_ID/SECRET` 필요). 타인 저작권·상업이용은 셀러 책임.
- 히어로 사진 색에 맞춰 페이지 액센트가 자동 적용된다(없으면 카테고리 테마).
- 올린 슬롯만 채워지고, 빈 슬롯·없는 섹션은 우아하게 적응한다(사진 0장도 유효).
- 가격·시장최저가·데이터 출처 문구는 PDP 이미지에 넣지 않는다(셀러 자기 PDP 용도).

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

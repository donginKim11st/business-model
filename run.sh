#!/usr/bin/env bash
# 개발 서버 실행 스크립트. 기존 인스턴스 정리 → 환경 점검 → uvicorn --reload 기동.
#   ./run.sh              기본 127.0.0.1:8800
#   PORT=9000 ./run.sh    포트 변경
set -euo pipefail
cd "$(dirname "$0")"

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8800}"

# 1) 파이썬 선택 (.venv 우선, 없으면 시스템 python3)
if [ -x ".venv/bin/python" ]; then
  PY=".venv/bin/python"
else
  PY="$(command -v python3 || command -v python || true)"
fi
[ -n "$PY" ] || { echo "❌ python3 를 찾을 수 없습니다."; exit 1; }

# 2) 의존성 점검 (없으면 설치)
if ! "$PY" -c "import uvicorn, fastapi" >/dev/null 2>&1; then
  echo "📦 의존성 설치 중… (pip install -r requirements.txt)"
  "$PY" -m pip install -q -r requirements.txt
fi

# 3) .env 점검
if [ ! -f .env ]; then
  echo "⚠️  .env 없음 → .env.example 를 복사합니다. 키를 채워주세요."
  cp .env.example .env
fi
grep -qE '^OPENAI_API_KEY=.+' .env || echo "⚠️  OPENAI_API_KEY 미설정 — '상세페이지 생성'이 실패합니다 (.env 확인)."
grep -qE '^NAVER_CLIENT_ID=.+' .env || echo "ℹ️  NAVER_CLIENT_ID 미설정 — '사진 추천' 기능만 비활성 (선택)."

# 4) MongoDB(47017) 소프트 점검
if ! (exec 3<>/dev/tcp/127.0.0.1/47017) 2>/dev/null; then
  echo "⚠️  MongoDB(127.0.0.1:47017) 응답 없음 — 상품 데이터가 안 보일 수 있습니다."
fi

# 5) 기존 인스턴스 정리 (포트 충돌 방지)
if pkill -f "uvicorn app.main:app" 2>/dev/null; then
  echo "♻️  기존 서버 종료"; sleep 1
fi

echo "▶  http://$HOST:$PORT   (Ctrl+C 로 종료, 코드 변경 자동 반영)"
exec "$PY" -m uvicorn app.main:app --reload --host "$HOST" --port "$PORT"

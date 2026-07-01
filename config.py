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
        naver_client_id=env.get("NAVER_CLIENT_ID", ""),
        naver_client_secret=env.get("NAVER_CLIENT_SECRET", ""),
    )


settings = load_settings()

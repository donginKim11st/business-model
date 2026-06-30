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

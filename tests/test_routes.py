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

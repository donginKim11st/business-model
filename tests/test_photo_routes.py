import json
import pathlib
from fastapi.testclient import TestClient
from app import main, photo_search

FIX = pathlib.Path(__file__).parent / "fixtures"
DOC = json.loads((FIX / "product_full.json").read_text(encoding="utf-8"))


def _client(monkeypatch, *, doc=DOC):
    monkeypatch.setattr(main.data, "get_product", lambda uid, **k: doc)
    return TestClient(main.app)


# ---- photo-suggest ----
def test_suggest_returns_items(monkeypatch):
    monkeypatch.setattr(main.photo_search, "search",
                        lambda q, **k: [{"thumbnail": "https://t/1", "link": "https://i/1.jpg"}])
    c = _client(monkeypatch)
    r = c.get("/product/P7863/photo-suggest?slot=hero")
    assert r.status_code == 200
    body = r.json()
    assert body["slot"] == "hero"
    assert body["items"][0]["link"] == "https://i/1.jpg"
    assert body["query"]                                   # 상품명으로 검색


def test_suggest_uses_product_keyword(monkeypatch):
    seen = {}
    def _search(q, **k):
        seen["q"] = q
        return []
    monkeypatch.setattr(main.photo_search, "search", _search)
    c = _client(monkeypatch)
    c.get("/product/P7863/photo-suggest?slot=detail")
    assert seen["q"] == main.build_view(DOC).get("keyword")  # 슬롯 공통 상품명 쿼리


def test_suggest_missing_keys_error_surfaced(monkeypatch):
    def _boom(q, **k):
        raise photo_search.PhotoSearchError("네이버 API 키가 설정되지 않았습니다.")
    monkeypatch.setattr(main.photo_search, "search", _boom)
    c = _client(monkeypatch)
    r = c.get("/product/P7863/photo-suggest")
    assert r.status_code == 502
    assert "네이버 API 키" in r.json()["error"]              # 사유 명확 노출


def test_suggest_empty_keyword_400(monkeypatch):
    monkeypatch.setattr(main, "build_view", lambda doc: {"keyword": "  "})   # 검색어 없음
    c = _client(monkeypatch)
    r = c.get("/product/P7863/photo-suggest")
    assert r.status_code == 400
    assert "키워드" in r.json()["error"]


def test_suggest_unknown_uid_404(monkeypatch):
    c = _client(monkeypatch, doc=None)
    assert c.get("/product/NOPE/photo-suggest").status_code == 404


# ---- photo-fetch ----
def test_fetch_returns_data_uri(monkeypatch):
    monkeypatch.setattr(main.photo_search, "fetch_as_data_uri",
                        lambda url, **k: "data:image/jpeg;base64,QUJD")
    c = _client(monkeypatch)
    r = c.post("/product/P7863/photo-fetch", data={"url": "https://cdn/x.jpg"})
    assert r.status_code == 200
    assert r.json()["data_uri"].startswith("data:image/jpeg;base64,")


def test_fetch_rejects_bad_image_400_with_generic_message(monkeypatch):
    def _boom(url, **k):
        raise photo_search.PhotoSearchError("허용되지 않은 대상(내부 네트워크)입니다.")   # 내부 사유
    monkeypatch.setattr(main.photo_search, "fetch_as_data_uri", _boom)
    c = _client(monkeypatch)
    r = c.post("/product/P7863/photo-fetch", data={"url": "https://127.0.0.1/x"})
    assert r.status_code == 400
    assert r.json()["error"] == "이미지를 가져올 수 없습니다."       # 내부 사유 비노출(SSRF 오라클 방지)
    assert "내부 네트워크" not in r.json()["error"]


def test_fetch_unknown_uid_404(monkeypatch):
    c = _client(monkeypatch, doc=None)
    assert c.post("/product/NOPE/photo-fetch", data={"url": "https://cdn/x.jpg"}).status_code == 404

import io
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


def test_detail_image_render_error_500(monkeypatch):
    monkeypatch.setattr(main.data, "get_product", lambda uid, **k: DOC)
    monkeypatch.setattr(main.detail_page, "build_html", lambda v, d, image_data_uri=None: "<html></html>")
    async def _boom(html):
        raise main.render.RenderError("boom")
    monkeypatch.setattr(main.render, "html_to_png", _boom)
    c = TestClient(main.app)
    r = c.post("/product/P7863/detail-image", data={"draft": json.dumps(DRAFT)})
    assert r.status_code == 500


def test_detail_image_regenerate_fail_502(monkeypatch):
    from app.generate import GenerateError
    monkeypatch.setattr(main.data, "get_product", lambda uid, **k: DOC)
    def _boom(view, **k):
        raise GenerateError("x")
    monkeypatch.setattr(main.generate, "draft", _boom)
    c = TestClient(main.app)
    r = c.post("/product/P7863/detail-image", data={})
    assert r.status_code == 502

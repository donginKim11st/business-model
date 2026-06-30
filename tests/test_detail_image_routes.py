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


def _client(monkeypatch, *, doc=DOC, draft_fn=None, img_capture=None):
    monkeypatch.setattr(main.data, "get_product", lambda uid, **k: doc)
    if draft_fn:
        monkeypatch.setattr(main.generate, "draft", draft_fn)

    def _build(view, d, images=None, style="airy"):
        if img_capture is not None:
            img_capture["images"] = images
            img_capture["style"] = style
        return "<html></html>"
    monkeypatch.setattr(main.detail_page, "build_html", _build)

    async def _png(html):
        return PNG
    monkeypatch.setattr(main.render, "html_to_png", _png)
    return TestClient(main.app)


def _img(color_byte=b"\x89PNG"):
    return io.BytesIO(color_byte + b"data")


def test_no_files_renders_with_empty_images(monkeypatch):
    cap = {}
    c = _client(monkeypatch, img_capture=cap)
    r = c.post("/product/P7863/detail-image", data={"draft": json.dumps(DRAFT)})
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert cap["images"] == {}                        # 0장 → 빈 dict (전부 플레이스홀더)


def test_multiple_slots_embedded_by_key(monkeypatch):
    cap = {}
    c = _client(monkeypatch, img_capture=cap)
    files = {"hero": ("h.png", _img(), "image/png"), "usage": ("u.jpg", _img(), "image/jpeg")}
    r = c.post("/product/P7863/detail-image", data={"draft": json.dumps(DRAFT)}, files=files)
    assert r.status_code == 200
    assert set(cap["images"].keys()) == {"hero", "usage"}          # 채운 슬롯만
    assert cap["images"]["hero"].startswith("data:image/png;base64,")
    assert cap["images"]["usage"].startswith("data:image/jpeg;base64,")


def test_style_default_airy(monkeypatch):
    cap = {}
    c = _client(monkeypatch, img_capture=cap)
    c.post("/product/P7863/detail-image", data={"draft": json.dumps(DRAFT)})
    assert cap["style"] == "airy"                      # style 미지정 → 기본 airy


def test_style_passed_through(monkeypatch):
    cap = {}
    c = _client(monkeypatch, img_capture=cap)
    c.post("/product/P7863/detail-image", data={"draft": json.dumps(DRAFT), "style": "contrast"})
    assert cap["style"] == "contrast"                  # 선택한 스타일 전달


def test_unknown_style_falls_back_to_airy(monkeypatch):
    cap = {}
    c = _client(monkeypatch, img_capture=cap)
    c.post("/product/P7863/detail-image", data={"draft": json.dumps(DRAFT), "style": "bogus"})
    assert cap["style"] == "airy"                       # 잘못된 값 → 안전 폴백


def test_unknown_uid_404(monkeypatch):
    c = _client(monkeypatch, doc=None)
    assert c.post("/product/NOPE/detail-image", data={"draft": json.dumps(DRAFT)}).status_code == 404


def test_malformed_draft_400(monkeypatch):
    c = _client(monkeypatch)
    assert c.post("/product/P7863/detail-image", data={"draft": "{bad"}).status_code == 400


def test_absent_draft_regenerates(monkeypatch):
    c = _client(monkeypatch, draft_fn=lambda view, **k: DRAFT)
    r = c.post("/product/P7863/detail-image", data={})
    assert r.status_code == 200


def test_absent_draft_regen_fail_502(monkeypatch):
    from app.generate import GenerateError
    monkeypatch.setattr(main.data, "get_product", lambda uid, **k: DOC)
    def _boom(view, **k):
        raise GenerateError("x")
    monkeypatch.setattr(main.generate, "draft", _boom)
    c = TestClient(main.app)
    r = c.post("/product/P7863/detail-image", data={})
    assert r.status_code == 502


def test_non_image_slot_400(monkeypatch):
    c = _client(monkeypatch)
    files = {"hero": ("h.txt", io.BytesIO(b"hi"), "text/plain")}
    r = c.post("/product/P7863/detail-image", data={"draft": json.dumps(DRAFT)}, files=files)
    assert r.status_code == 400


def test_oversize_slot_400(monkeypatch):
    c = _client(monkeypatch)
    big = io.BytesIO(b"\x89PNG" + b"x" * (8 * 1024 * 1024 + 1))
    files = {"detail": ("big.png", big, "image/png")}
    r = c.post("/product/P7863/detail-image", data={"draft": json.dumps(DRAFT)}, files=files)
    assert r.status_code == 400


def test_render_error_500(monkeypatch):
    monkeypatch.setattr(main.data, "get_product", lambda uid, **k: DOC)
    monkeypatch.setattr(main.detail_page, "build_html", lambda v, d, images=None, style="airy": "<html></html>")
    async def _boom(html):
        raise main.render.RenderError("boom")
    monkeypatch.setattr(main.render, "html_to_png", _boom)
    c = TestClient(main.app)
    r = c.post("/product/P7863/detail-image", data={"draft": json.dumps(DRAFT)})
    assert r.status_code == 500

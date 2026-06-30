"""FastAPI 앱: 검색 → 인사이트 → 생성. data/generate 는 테스트 주입 위해 모듈 참조."""
import pathlib
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import data, generate
from app.insight import build_view
from app.generate import GenerateError

_HERE = pathlib.Path(__file__).parent
templates = Jinja2Templates(directory=str(_HERE / "templates"))

app = FastAPI(title="셀러 상세페이지 툴")
app.mount("/static", StaticFiles(directory=str(_HERE / "static")), name="static")


@app.get("/", response_class=HTMLResponse)
def search(request: Request, q: str = ""):
    products = data.find_products(q) if q.strip() else []
    return templates.TemplateResponse(request, "search.html", {"q": q, "products": products})


@app.get("/product/{uid}", response_class=HTMLResponse)
def product(request: Request, uid: str):
    doc = data.get_product(uid)
    if doc is None:
        return HTMLResponse("<h1>404 · 상품을 찾을 수 없습니다</h1><a href=\"/\">검색으로</a>", status_code=404)
    return templates.TemplateResponse(request, "product.html", {"v": build_view(doc)})


@app.post("/product/{uid}/draft", response_class=HTMLResponse)
def draft(request: Request, uid: str):
    doc = data.get_product(uid)
    if doc is None:
        return HTMLResponse("<p class=err>상품을 찾을 수 없습니다.</p>", status_code=404)
    try:
        d = generate.draft(build_view(doc))
        return templates.TemplateResponse(request, "_draft.html", {"d": d, "error": None})
    except GenerateError:
        return templates.TemplateResponse(request, "_draft.html", {"d": None, "error": True})

"""FastAPI 앱: 검색 → 인사이트 → 생성 → 상세페이지 이미지."""
import json
import pathlib
from urllib.parse import quote
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import data, generate, render, detail_page
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
        return templates.TemplateResponse(request, "_draft.html", {"d": d, "uid": uid, "error": None})
    except GenerateError:
        return templates.TemplateResponse(request, "_draft.html", {"d": None, "uid": uid, "error": True})


@app.post("/product/{uid}/detail-image")
async def detail_image(uid: str, draft: str = Form(None)):
    doc = data.get_product(uid)
    if doc is None:
        return Response("상품을 찾을 수 없습니다.", status_code=404)
    view = build_view(doc)
    if draft:
        try:
            d = json.loads(draft)
        except (ValueError, TypeError):
            return Response("초안 데이터 오류", status_code=400)
    else:
        try:
            d = generate.draft(view)
        except GenerateError:
            return Response("초안 생성 실패", status_code=502)
    html = detail_page.build_html(view, d, None)
    try:
        png = await render.html_to_png(html)
    except render.RenderError:
        return Response("이미지 생성 실패", status_code=500)
    fname = quote(f"{view['keyword']}_상세.png")
    return Response(png, media_type="image/png",
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{fname}"})

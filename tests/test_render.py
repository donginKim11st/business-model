import asyncio
import os
import shutil
import pytest
from app import render


def test_render_error_exists():
    assert issubclass(render.RenderError, Exception)


@pytest.mark.render
@pytest.mark.skipif(shutil.which("python3") is None or os.environ.get("RUN_RENDER") != "1",
                    reason="RUN_RENDER=1 + playwright install chromium 필요")
def test_html_to_png_produces_png():
    png = asyncio.run(render.html_to_png("<html><body><h1>hi</h1></body></html>"))
    assert png[:8] == b"\x89PNG\r\n\x1a\n"   # PNG 매직바이트
    assert len(png) > 100

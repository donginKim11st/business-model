"""상세페이지 HTML → PNG bytes (Playwright 헤드리스 Chromium). 유일한 렌더 I/O."""


class RenderError(Exception):
    pass


async def html_to_png(html):
    """self-contained HTML 을 풀페이지 PNG bytes 로. 실패는 RenderError 로 래핑."""
    try:
        from playwright.async_api import async_playwright
    except ImportError as e:
        raise RenderError("playwright 미설치: pip install playwright && playwright install chromium") from e
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            try:
                page = await browser.new_page(device_scale_factor=2)
                await page.set_content(html, wait_until="load")
                return await page.screenshot(full_page=True, type="png")
            finally:
                await browser.close()
    except RenderError:
        raise
    except Exception as e:
        raise RenderError(f"렌더 실패: {e}") from e

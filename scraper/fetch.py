from playwright.sync_api import sync_playwright

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

def fetch_html(url: str, wait_selector: str | None = None, delay_ms: int = 1500) -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=USER_AGENT)
        page.goto(url, timeout=30000)
        if wait_selector:
            page.wait_for_selector(wait_selector, timeout=15000)
        if delay_ms:
            page.wait_for_timeout(delay_ms)
        html = page.content()
        browser.close()
        return html

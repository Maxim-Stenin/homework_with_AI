from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page()
    print("browser.version:", b.version)
    print("UA:", pg.evaluate("() => navigator.userAgent"))
    b.close()

from playwright.sync_api import sync_playwright

def check():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://www.qdnd.vn/chinh-tri")
        
        # Find pagination links
        # Try generic selector for pagination
        links = page.locator("a[href*='/p/']").all()
        print(f"Found {len(links)} pagination links.")
        for link in links[:3]:
            print(f"Link: {link.get_attribute('href')}")
            
        browser.close()

if __name__ == "__main__":
    check()

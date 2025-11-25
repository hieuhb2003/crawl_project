from playwright.sync_api import sync_playwright

URL = "https://tapchiqptd.vn/vi/huong-toi-dai-hoi-xiv-cua-dang-169.html"

def inspect():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(URL)
        
        # Print the first 2000 characters of the main content area to see structure
        # Dump HTML
        print("Dumping HTML...")
        with open("page_dump.html", "w", encoding="utf-8") as f:
            f.write(page.content())
        print("HTML dumped to page_dump.html")
            
        browser.close()

if __name__ == "__main__":
    inspect()

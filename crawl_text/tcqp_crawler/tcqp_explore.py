from playwright.sync_api import sync_playwright

URL = "https://tapchiqptd.vn/vi/huong-toi-dai-hoi-xiv-cua-dang-169.html"

def explore():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        print(f"Navigating to {URL}")
        page.goto(URL)
        
        # 1. Article Links
        # Try generic selectors
        links = page.locator("h3 a, .title-news a, .story__title a").all()
        print(f"Found {len(links)} potential article links.")
        for link in links[:3]:
            print(f"Link: {link.get_attribute('href')}")
            
        # 2. Pagination
        # Try finding 'Next' or page numbers
        next_btn = page.locator("a:has-text('>'), a[title='Trang sau'], a.next, .pagination a").all()
        print(f"Found {len(next_btn)} pagination elements.")
        for btn in next_btn:
            print(f"Pagination Text: {btn.inner_text()} | Href: {btn.get_attribute('href')}")

        # 3. Detail Page
        if len(links) > 0:
            first_link = links[0].get_attribute("href")
            full_link = first_link if first_link.startswith("http") else "https://tapchiqptd.vn" + first_link
            print(f"Visiting detail page: {full_link}")
            page.goto(full_link)
            
            print(f"Title: {page.title()}")
            h1 = page.locator("h1").first
            if h1.is_visible():
                print(f"H1: {h1.inner_text()}")
                
            date = page.locator(".date, .time, .post-date, .article-meta").first
            if date.is_visible():
                print(f"Date: {date.inner_text()}")
                
            content = page.locator(".content, .post-content, .article-content, #content").first
            if content.is_visible():
                print("Content found.")
            else:
                print("Content NOT found with common selectors.")

        browser.close()

if __name__ == "__main__":
    explore()

import time
import os
import random
from playwright.sync_api import sync_playwright
from utils import save_article, ensure_dir

BASE_URL = "https://www.qdnd.vn/chinh-tri"
OUTPUT_DIR = "crawled_data"

class QDNDCrawler:
    def __init__(self):
        self.output_dir = os.path.join(os.getcwd(), OUTPUT_DIR)
        ensure_dir(self.output_dir)
        self.processed_file = "processed_urls.txt"
        self.state_file = "crawler_state.json"
        self.processed_urls = self.load_processed_urls()

    def load_processed_urls(self):
        if not os.path.exists(self.processed_file):
            return set()
        with open(self.processed_file, 'r') as f:
            return set(line.strip() for line in f)

    def mark_as_processed(self, url):
        with open(self.processed_file, 'a') as f:
            f.write(f"{url}\n")
        self.processed_urls.add(url)

    def save_state(self, page_num):
        import json
        with open(self.state_file, 'w') as f:
            json.dump({"last_page": page_num}, f)

    def load_state(self):
        import json
        if not os.path.exists(self.state_file):
            return 1
        try:
            with open(self.state_file, 'r') as f:
                data = json.load(f)
                return data.get("last_page", 1)
        except:
            return 1

    def run(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()

            # Load start page
            start_page = self.load_state()
            print(f"Resuming from Page {start_page}...")

            page_num = start_page
            while True:
                # Construct URL
                if page_num == 1:
                    current_url = BASE_URL
                else:
                    current_url = f"{BASE_URL}/p/{page_num}"
                
                print(f"Navigating to: {current_url}")
                try:
                    page.goto(current_url, timeout=60000)
                    page.wait_for_load_state("networkidle")
                except Exception as e:
                    print(f"Error loading page {current_url}: {e}")
                    # Retry once
                    time.sleep(5)
                    try:
                        page.goto(current_url, timeout=60000)
                    except:
                        print("Skipping page due to error.")
                        page_num += 1
                        continue

                self.save_state(page_num) # Save current page
                
                # Get article links
                # Selector: h3.post-title a OR .title-news a
                # Based on inspection, let's try a generic one that targets news links
                # Usually links inside 'div.list-news' or similar
                
                # Let's grab all links that look like articles
                potential_links = page.locator("h3 a, .title-news a, a.title-news").all()
                
                article_links = []
                for link in potential_links:
                    href = link.get_attribute("href")
                    if href and "/chinh-tri/" in href:
                        full_url = href if href.startswith("http") else "https://www.qdnd.vn" + href
                        if full_url not in article_links and full_url not in self.processed_urls:
                            article_links.append(full_url)
                
                print(f"  Found {len(article_links)} new articles on page {page_num}.")
                
                for url in article_links:
                    # Random delay
                    time.sleep(random.uniform(1, 3))
                    self.process_article(page, url)
                
                # Pagination Logic
                # Look for "Next" button or page numbers
                # QDND uses links like /p/2, /p/3 etc.
                # We can try to find a link to the NEXT page number.
                
                next_page_num = page_num + 1
                next_page_link = page.locator(f"a[href*='/p/{next_page_num}']").first
                
                # Also try generic "Next" buttons
                generic_next = page.locator("a:has-text('>'), a[title='Trang sau'], a.next").first
                
                if next_page_link.is_visible():
                    print(f"  Navigating to Page {next_page_num}...")
                    # We don't need to click if we construct URL in next loop, 
                    # BUT the loop expects us to increment page_num.
                    # Actually, the loop uses `page.goto(current_url)` at the START.
                    # So we just need to increment page_num and continue.
                    page_num += 1
                    time.sleep(2)
                    continue
                elif generic_next.is_visible():
                    print("  Navigating to next page (generic)...")
                    # If we click, we need to know the new URL to update page_num correctly?
                    # But our loop relies on `page_num` to construct URL.
                    # If we click, the URL changes.
                    # Let's just increment page_num and let the loop handle navigation via URL.
                    page_num += 1
                    time.sleep(2)
                    continue
                else:
                    # If we can't find a link to next page, and we are on page 1, maybe we are done?
                    # Or maybe the selector is wrong.
                    # Let's try to just increment blindly if we found articles? 
                    # No, that leads to 404s.
                    
                    if len(article_links) == 0 and len(potential_links) == 0:
                         print("  No articles and no next page found. Ending.")
                         break
                    
                    # If we found articles but no next link, maybe it's the last page.
                    print("  No next page link found. Assuming end of list.")
                    break

            browser.close()

    def clean_content(self, content):
        lines = content.split('\n')
        cleaned_lines = []
        stop_markers = [
            "Nguồn: qdnd.vn",
            "TAG",
            "Tin, ảnh:",
            "Tin liên quan",
            "Xem thêm",
            "Ý KIẾN BẠN ĐỌC",
            "CÁC TIN, BÀI ĐÃ ĐƯA"
        ]
        
        for line in lines:
            is_stop = False
            for marker in stop_markers:
                if marker in line:
                    if len(line.strip()) < 100:
                        is_stop = True
                        break
            if is_stop:
                break
            cleaned_lines.append(line)
            
        return '\n'.join(cleaned_lines)

    def process_article(self, main_page, url):
        context = main_page.context
        page = context.new_page()
        
        try:
            print(f"    Processing: {url}")
            page.goto(url, timeout=30000)
            page.wait_for_load_state("domcontentloaded")
            
            # Extract Content
            title = page.title()
            h1 = page.locator("h1").first
            if h1.is_visible():
                title = h1.inner_text().strip()
            
            date = "Unknown"
            date_el = page.locator(".post-time, .date, .time").first
            if date_el.is_visible():
                date = date_el.inner_text().strip()
            
            # Content
            # Try common content classes
            content_el = page.locator(".post-content, .detail-content, #content").first
            if content_el.is_visible():
                content = content_el.inner_text()
            else:
                content = page.locator("body").inner_text()
            
            # Clean content
            content = self.clean_content(content)
            
            metadata = {
                "title": title,
                "date": date,
                "url": url
            }
            
            if save_article(self.output_dir, metadata, content):
                self.mark_as_processed(url)
                
        except Exception as e:
            print(f"    Error processing {url}: {e}")
        finally:
            page.close()

if __name__ == "__main__":
    crawler = QDNDCrawler()
    crawler.run()

import time
import os
import random
from playwright.sync_api import sync_playwright
from utils import save_article, ensure_dir

BASE_URL = "https://tapchiqptd.vn/vi/nhung-chu-truong-cong-tac-lon-2.html"
OUTPUT_DIR = "crawled_data"

class TCQPCrawler:
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
                    current_url = f"{BASE_URL}?pageindex={page_num}"
                
                print(f"Navigating to: {current_url}")
                try:
                    page.goto(current_url, timeout=60000)
                    page.wait_for_load_state("networkidle")
                except Exception as e:
                    print(f"Error loading page {current_url}: {e}")
                    time.sleep(5)
                    try:
                        page.goto(current_url, timeout=60000)
                    except:
                        print("Skipping page due to error.")
                        page_num += 1
                        continue

                self.save_state(page_num)
                
                # Get article links
                # Selector: .news-other-list p a
                potential_links = page.locator(".news-other-list p a").all()
                
                article_links = []
                for link in potential_links:
                    href = link.get_attribute("href")
                    if href:
                        full_url = href if href.startswith("http") else "https://tapchiqptd.vn" + href
                        if full_url not in article_links and full_url not in self.processed_urls:
                            article_links.append(full_url)
                
                print(f"  Found {len(article_links)} new articles on page {page_num}.")
                
                for url in article_links:
                    time.sleep(random.uniform(1, 3))
                    self.process_article(page, url)
                
                # Pagination Logic
                # Check if "Next" button exists
                # Selector: #pagenav a:has-text('>')
                
                next_btn = page.locator("#pagenav a:has-text('>')").first
                
                if not next_btn.is_visible() and len(article_links) == 0:
                    print("  No articles and no next page found. Ending.")
                    break
                
                if not next_btn.is_visible():
                     print("  No next page button found. Ending.")
                     break
                
                page_num += 1
                time.sleep(2)

            browser.close()

    def clean_content(self, content):
        lines = content.split('\n')
        
        # 1. Remove Header Noise
        # The header block starts with "Tòa soạn:" and ends with "Tạp chí và Tòa soạn"
        # We'll look for "Tạp chí và Tòa soạn" in the first 30 lines and cut everything before it.
        start_index = 0
        for i, line in enumerate(lines[:30]):
            if "Tạp chí và Tòa soạn" in line:
                start_index = i + 1
                break
        
        # If we didn't find the exact end marker, but see "Tòa soạn:" at start, 
        # we might need a fallback, but let's stick to the user's observation.
        # If "Tạp chí và Tòa soạn" is found, we skip to the line after it.
        
        lines = lines[start_index:]
        
        cleaned_lines = []
        stop_markers = [
            "Nguồn: qdnd.vn",
            "TAG",
            "Ý KIẾN BẠN ĐỌC",
            "CÁC TIN, BÀI ĐÃ ĐƯA",
            "Tạp chí và Tòa soạn", # Also a stop marker if it appears again at bottom? 
            # Actually, "Tạp chí và Tòa soạn" is in the header list provided by user.
            # But it might also be in the footer? 
            # The user said "trở xuống thì xoá hết" for the footer part.
            # And for the header "trước khi save về, hãy xoá cái này đi".
            
            "TIÊU ĐIỂM",
            "TIN, BÀI XEM NHIỀU"
        ]
        
        for line in lines:
            is_stop = False
            for marker in stop_markers:
                if marker in line:
                    # Check if it's a standalone marker or significant enough
                    if len(line.strip()) < 100: # Markers are usually short headers
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
            date_el = page.locator(".date, .time, .post-date, .article-meta").first
            if date_el.is_visible():
                date = date_el.inner_text().strip()
            
            # Content
            content_el = page.locator(".content, .post-content, .article-content, #content").first
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
    crawler = TCQPCrawler()
    crawler.run()

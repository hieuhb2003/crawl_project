import time
import os
import random
import re
from playwright.sync_api import sync_playwright
from config import TARGET_AGENCIES, TARGET_DOC_TYPES, OUTPUT_DIR
from utils import save_document, ensure_dir

# URL for the search page
SEARCH_URL = "https://vbpl.vn/boquocphong/Pages/vbpq-timkiem.aspx?dvid=314"

class VBPLCrawlAll:
    def __init__(self):
        self.output_dir = OUTPUT_DIR
        ensure_dir(self.output_dir)
        self.processed_ids_file = os.path.join(self.output_dir, "processed_ids.txt")
        self.state_file = os.path.join(self.output_dir, "crawler_state.json")
        self.processed_ids = self.load_processed_ids()

    def load_processed_ids(self):
        if not os.path.exists(self.processed_ids_file):
            return set()
        with open(self.processed_ids_file, 'r') as f:
            return set(line.strip() for line in f)

    def mark_as_processed(self, item_id):
        with open(self.processed_ids_file, 'a') as f:
            f.write(f"{item_id}\n")
        self.processed_ids.add(item_id)

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

            print(f"Navigating to Search Page: {SEARCH_URL}")
            page.goto(SEARCH_URL, timeout=60000)
            page.wait_for_load_state("networkidle")

            # Click Search button to get all results
            print("Clicking Search button to list all documents...")
            search_btn = page.locator("input[type='submit'][value='Tìm kiếm'], a:has-text('Tìm kiếm')").first
            if search_btn.is_visible():
                search_btn.click()
                page.wait_for_load_state("networkidle")
                time.sleep(3) # Wait for results to populate
            else:
                print("Error: Search button not found!")
                return

            # Load start page
            start_page = self.load_state()
            if start_page > 1:
                print(f"Resuming from Page {start_page}...")
                # Execute JavaScript to jump to page
                try:
                    page.evaluate(f"LoadPage({start_page})")
                    page.wait_for_load_state("networkidle")
                    time.sleep(3)
                except Exception as e:
                    print(f"Error jumping to page {start_page}: {e}")
                    print("Falling back to Page 1")
                    start_page = 1

            # Pagination Loop
            page_num = start_page
            while True:
                print(f"  Crawling Page {page_num}...")
                self.save_state(page_num) # Save current page
                
                # Get all document links on current page
                # Selector: a[href*='ItemID=']
                potential_links = page.locator("a[href*='ItemID=']").all()
                
                doc_links = []
                for link in potential_links:
                    href = link.get_attribute("href")
                    # Filter for relevant detail pages
                    if href and ("toanvan.aspx" in href or "vanbanhopnhat.aspx" in href or "hethonghoa.aspx" in href):
                        full_url = href if href.startswith("http") else "https://vbpl.vn" + href
                        if full_url not in doc_links:
                            doc_links.append(full_url)
                
                print(f"    Found {len(doc_links)} documents on this page.")
                
                for doc_url in doc_links:
                    # Extract ItemID
                    item_id_match = re.search(r'ItemID=(\d+)', doc_url)
                    item_id = item_id_match.group(1) if item_id_match else None
                    
                    if item_id and item_id in self.processed_ids:
                        print(f"    Skipping {item_id} (Already processed)")
                        continue
                    
                    # Random delay
                    sleep_time = random.uniform(2, 5)
                    print(f"    Waiting {sleep_time:.2f}s...")
                    time.sleep(sleep_time)
                        
                    self.process_document(page, doc_url, item_id)
                
                # Next Page
                # Search page uses "Sau" for next page, or javascript:LoadPage()
                next_btn = page.locator("a:has-text('Sau'), a:has-text('Next'), a[title='Trang sau']").first
                
                if next_btn.is_visible():
                    print("    Navigating to next page...")
                    next_btn.click()
                    page.wait_for_load_state("networkidle")
                    time.sleep(3)
                    page_num += 1
                else:
                    print("    No more pages.")
                    break

            browser.close()

    def process_document(self, main_page, doc_url, item_id):
        context = main_page.context
        page = context.new_page()
        
        try:
            print(f"      Processing: {doc_url}")
            page.goto(doc_url, timeout=30000)
            page.wait_for_load_state("domcontentloaded")
            
            # 1. Switch to Properties Tab for Metadata
            properties_link = page.locator("a:has-text('Thuộc tính')").first
            if properties_link.is_visible():
                print("      Switching to Properties tab...")
                properties_link.click()
                page.wait_for_load_state("networkidle")
                time.sleep(1)

            # Metadata Extraction Helper
            def get_metadata_value(label):
                el = page.locator(f"td:has-text('{label}') + td").first
                if el.is_visible():
                    return el.inner_text().strip()
                return None

            # Title Extraction
            title = page.title().strip()
            title_candidate = page.locator(".title-vb, .vb-title, .title, strong").first
            if title_candidate.is_visible():
                 candidate_text = title_candidate.inner_text().strip()
                 if len(candidate_text) > 10:
                     title = candidate_text
            
            trich_yeu = get_metadata_value("Trích yếu")
            if trich_yeu:
                title = trich_yeu

            agency = get_metadata_value("Cơ quan ban hành")
            doc_type = get_metadata_value("Loại văn bản")
            date = get_metadata_value("Ngày ban hành") or "N/A"
            
            # 2. Switch back to Full Text Tab
            toanvan_link = page.locator("a:has-text('Toàn văn')").first
            if toanvan_link.is_visible():
                print("      Switching back to Full Text tab...")
                toanvan_link.click()
                page.wait_for_load_state("networkidle")
                time.sleep(1)

            metadata = {
                "url": doc_url,
                "title": title,
                "agency": agency if agency else "Unknown_Agency",
                "type": doc_type if doc_type else "Unknown_Type",
                "date": date
            }
            
            # 3. Content Extraction
            content_div = page.locator("#toanvancontent, .box-content, .content-detail").first
            if content_div.is_visible():
                content = content_div.inner_text()
            else:
                main_col = page.locator("#main, .main, .col-md-9").first
                if main_col.is_visible():
                    content = main_col.inner_text()
                else:
                    content = page.locator("body").inner_text()
            
            # Clean noise
            noise_phrases = ["Văn bản quy phạm pháp luật", "Văn bản hợp nhất", "Hệ thống hóa VBQPPL", "Mục lục văn bản"]
            lines = content.split('\n')
            cleaned_lines = [line for line in lines if line.strip() not in noise_phrases]
            content = '\n'.join(cleaned_lines)

            # 4. Save (Organizes into folders automatically via utils.save_document)
            # Note: We save ALL documents found in search, as requested.
            # If agency/type is unknown, it goes to Unknown folder.
            
            if save_document(self.output_dir, metadata, content):
                if item_id:
                    self.mark_as_processed(item_id)

        except Exception as e:
            print(f"      Error processing document: {e}")
        finally:
            page.close()

if __name__ == "__main__":
    crawler = VBPLCrawlAll()
    crawler.run()

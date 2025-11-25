import time
import os
from playwright.sync_api import sync_playwright
from config import CATEGORY_URLS, TARGET_AGENCIES, TARGET_DOC_TYPES, OUTPUT_DIR
from utils import save_document, ensure_dir

class VBPLCrawler:
    def __init__(self):
        self.output_dir = OUTPUT_DIR
        ensure_dir(self.output_dir)
        self.processed_ids_file = os.path.join(self.output_dir, "processed_ids.txt")
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

    def run(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True) # Headless=True for silent running
            context = browser.new_context()
            page = context.new_page()

            for category_name, url in CATEGORY_URLS.items():
                print(f"Processing Category: {category_name}")
                self.process_category(page, category_name, url)

            browser.close()

    def process_category(self, page, category_name, url):
        try:
            page.goto(url, timeout=60000)
            page.wait_for_load_state("networkidle")
            
            # If it's the Search page, we might need to click "Tìm kiếm" to get initial results
            if "timkiem" in url:
                search_btn = page.locator("input[type='submit'][value='Tìm kiếm'], a:has-text('Tìm kiếm')").first
                if search_btn.is_visible():
                    print("Clicking Search button...")
                    search_btn.click()
                    page.wait_for_load_state("networkidle")
                    time.sleep(2) # Extra wait for results

            # Pagination Loop
            page_num = 1
            while True:
                print(f"  Crawling Page {page_num}...")
                
                # Extract links from the current list
                # Selectors might vary, trying common ones for VBPL
                # Usually list items are in a div with class 'content' or similar, containing <a> tags
                # Let's look for specific document links. 
                # Common pattern: a.title-link, or just <a> inside a list item
                
                # Strategy: Get all potential document links, visit them one by one
                # To avoid stale elements, we collect URLs first
                doc_links = []
                
                # Try to find the list container
                # This is a guess based on common VBPL structure. 
                # We might need to adjust selectors if it fails.
                # Look for links that look like document details
                # potential_links = page.locator("ul.list-news li a, table.table-result tr td a").all()
                
                # Updated selector based on inspection
                potential_links = page.locator("a[href*='ItemID=']").all()
                
                for link in potential_links:
                    href = link.get_attribute("href")
                    # Filter for relevant detail pages
                    if href and ("toanvan.aspx" in href or "vanbanhopnhat.aspx" in href or "hethonghoa.aspx" in href):
                        full_url = href if href.startswith("http") else "https://vbpl.vn" + href
                        # Avoid duplicates
                        if full_url not in doc_links:
                            doc_links.append(full_url)
                
                print(f"    Found {len(doc_links)} documents on this page.")
                
                import random
                
                for doc_url in doc_links:
                    # Extract ItemID to check if processed
                    import re
                    item_id_match = re.search(r'ItemID=(\d+)', doc_url)
                    item_id = item_id_match.group(1) if item_id_match else None
                    
                    if item_id and item_id in self.processed_ids:
                        print(f"    Skipping {item_id} (Already processed)")
                        continue
                    
                    # Random delay to be polite and avoid ban
                    sleep_time = random.uniform(2, 5)
                    print(f"    Waiting {sleep_time:.2f}s...")
                    time.sleep(sleep_time)
                        
                    self.process_document(page, doc_url, item_id)
                    # Return to list page? No, process_document should open a new tab or go back.
                    # Easier: process_document uses the SAME page object, so we must go back.
                    # OR: Open in new tab.
                    # Let's use the same page and go back, but that's risky with state.
                    # Better: process_document creates a NEW page/tab.
                
                # Pagination: Find "Next" button
                # Look for ">" or "Trang sau" or class "next"
                next_btn = page.locator("a.next, a:has-text('>'), a[title='Trang sau']").first
                
                if next_btn.is_visible():
                    print("    Navigating to next page...")
                    next_btn.click()
                    page.wait_for_load_state("networkidle")
                    time.sleep(2)
                    page_num += 1
                else:
                    print("    No more pages.")
                    break
                
                # Safety break for testing
                if page_num > 5: # Limit to 5 pages for now
                    print("    Reached page limit (testing).")
                    break

        except Exception as e:
            print(f"Error processing category {category_name}: {e}")

    def process_document(self, main_page, doc_url, item_id):
        # Open a new page for the document to preserve the list page state
        context = main_page.context
        page = context.new_page()
        
        try:
            print(f"      Processing: {doc_url}")
            page.goto(doc_url, timeout=30000)
            page.wait_for_load_state("domcontentloaded")
            
            # ... (rest of extraction logic is same until save) ...
            
            # Extract Metadata
            # Usually in a table or div.info
            
            # Strategy: Go to "Thuộc tính" tab for metadata, then "Toàn văn" for content
            
            # Check for "Thuộc tính" link
            properties_link = page.locator("a:has-text('Thuộc tính')").first
            if properties_link.is_visible():
                print("      Switching to Properties tab...")
                properties_link.click()
                page.wait_for_load_state("networkidle")
                time.sleep(1) # Wait for update
            
            # Extract Metadata from Table (now likely visible)
            def get_metadata_value(label):
                # Try to find a row with the label
                # td containing label -> next sibling td
                # Use strict selector to avoid partial matches if possible, but loose is okay
                el = page.locator(f"td:has-text('{label}') + td").first
                if el.is_visible():
                    return el.inner_text().strip()
                return None

            # Title is often above the table in Thuộc tính tab
            # Look for a bold text or div.title-vb or similar
            # Based on observation, it might be just a p or div with strong text
            # Let's try to grab the first significant text in the content area
            
            title = page.title().strip() # Default
            
            # Try to find the title element specifically in the properties view
            # It's usually the largest text or specifically styled
            title_candidate = page.locator(".title-vb, .vb-title, .title, strong").first
            if title_candidate.is_visible():
                 candidate_text = title_candidate.inner_text().strip()
                 if len(candidate_text) > 10: # Avoid short labels
                     title = candidate_text

            # If we are in Thuộc tính, maybe there is a "Trích yếu" row?
            # Subagent didn't see it in the list, but let's check just in case
            trich_yeu = get_metadata_value("Trích yếu")
            if trich_yeu:
                title = trich_yeu

            agency = get_metadata_value("Cơ quan ban hành")
            doc_type = get_metadata_value("Loại văn bản")
            date = get_metadata_value("Ngày ban hành") or "N/A"
            
            # Go back to "Toàn văn"
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
            
            # Extract Content
            # Try to find the specific content container
            # Common IDs/Classes: #toanvancontent, .box-content, .content-detail
            
            content_div = page.locator("#toanvancontent, .box-content, .content-detail").first
            if content_div.is_visible():
                content = content_div.inner_text()
            else:
                # Fallback: Get body but try to exclude menu
                # This is hard with inner_text on body.
                # Let's try to get the main column
                main_col = page.locator("#main, .main, .col-md-9").first
                if main_col.is_visible():
                    content = main_col.inner_text()
                else:
                    content = page.locator("body").inner_text()
            
            # Clean up common noise if it leaked in
            noise_phrases = ["Văn bản quy phạm pháp luật", "Văn bản hợp nhất", "Hệ thống hóa VBQPPL", "Mục lục văn bản"]
            lines = content.split('\n')
            cleaned_lines = [line for line in lines if line.strip() not in noise_phrases]
            content = '\n'.join(cleaned_lines)

            # Filter Logic
            # If we found agency/type, use them. If not, check content.
            
            if metadata['agency'] == "Unknown_Agency":
                 for ag in TARGET_AGENCIES:
                    if ag in content[:1000]:
                        metadata['agency'] = ag
                        break
            
            if metadata['type'] == "Unknown_Type":
                for dt in TARGET_DOC_TYPES:
                    if dt in content[:1000]:
                        metadata['type'] = dt
                        break
            
            # Save if it matches or if we are permissive (user said "crawl into", implying all)
            # But user also listed specific Agencies/Types.
            # Let's save everything that looks like a document, categorized.
            
            if save_document(self.output_dir, metadata, content):
                if item_id:
                    self.mark_as_processed(item_id)

        except Exception as e:
            print(f"      Error processing document: {e}")
        finally:
            page.close()

if __name__ == "__main__":
    crawler = VBPLCrawler()
    crawler.run()

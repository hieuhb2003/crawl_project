"""
Step 1: Collect all URLs from ANTV Radio
Crawls multiple categories and collects podcast URLs.
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import json
import random
import os

# User-Agent pool
USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
]

# List of ANTV Radio categories
CATEGORIES = [
    "https://antv.gov.vn/radio/chinh-tri-xa-hoi-E3223AB43.html",
    "https://antv.gov.vn/radio/vi-nhan-dan-phuc-vu-0856C72A9.html",
    "https://antv.gov.vn/radio/thuc-thi-quyen-24h-9E73270CE.html",
    "https://antv.gov.vn/radio/-nhan-chung-su-kien-54C3125A7.html",
    "https://antv.gov.vn/radio/phia-sau-ban-an-6987DAA9F.html",
    "https://antv.gov.vn/radio/tieu-diem-antt-50895C5AC.html",
    "https://antv.gov.vn/radio/van-hoa-the-thao-F42DB6F14.html",
    "https://antv.gov.vn/radio/cau-chuyen-canh-giac-079E4AFA9.html",
    "https://antv.gov.vn/radio/ban-hoi-luat-su-tra-loi-C5670893E.html"
]

def get_random_user_agent():
    return random.choice(USER_AGENTS)

def setup_driver():
    """Setup Chrome WebDriver (Compatible with Jetson Orin/ARM64)"""
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(f"user-agent={get_random_user_agent()}")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    # Prioritize system-installed chromedriver for ARM64
    chromedriver_path = "/usr/bin/chromedriver" 
    if not os.path.exists(chromedriver_path):
        chromedriver_path = "/usr/lib/chromium-browser/chromedriver"
        
    if os.path.exists(chromedriver_path):
        print(f"Using system chromedriver at: {chromedriver_path}")
        service = Service(executable_path=chromedriver_path)
        driver = webdriver.Chrome(service=service, options=options)
    else:
        print("⚠️  System chromedriver not found, using default...")
        driver = webdriver.Chrome(options=options)
    
    driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
        'source': "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })
    return driver

def extract_urls_from_page(driver):
    """Extract detail page URLs from the current page"""
    urls = []
    # ANTV structure: links often contain the title and end with .html
    # We filter for links that look like detail pages (not category pages)
    # Detail pages usually have a long slug and ID at the end.
    
    try:
        elements = driver.find_elements(By.TAG_NAME, "a")
        for elem in elements:
            href = elem.get_attribute("href")
            if not href: continue
            
            # Filter logic:
            # 1. Must be in /radio/ path (implied by context, but check href)
            # 2. Must end with .html
            # 3. Exclude known category URLs (simple check)
            
            if "/radio/" in href and href.endswith(".html"):
                # Basic check to exclude category pages if possible, 
                # but usually detail pages are distinct. 
                # Let's assume all .html links in the content area are valid.
                # We can refine this if we get too many junk links.
                if href not in urls:
                    urls.append(href)
    except Exception as e:
        print(f"  Error extracting URLs: {e}")
        
    return urls

def save_urls(urls, filename="antv_urls.json"):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump({"total": len(urls), "urls": urls}, f, indent=2, ensure_ascii=False)
    print(f"  Saved {len(urls)} URLs to {filename}")

def main():
    print("="*60)
    print("STEP 1: COLLECT ALL URLs (ANTV RADIO)")
    print("="*60)
    
    driver = setup_driver()
    all_urls = set()
    
    try:
        for category_url in CATEGORIES:
            print(f"\nProcessing Category: {category_url}")
            driver.get(category_url)
            time.sleep(3)
            
            # 1. Extract from initial page
            urls = extract_urls_from_page(driver)
            initial_count = len(all_urls)
            for u in urls:
                all_urls.add(u)
            print(f"  Found {len(urls)} URLs on page 1")
            
            # 2. Try pagination (simple loop for a few pages)
            # We don't know the max pages, so let's try up to page 5 for now
            # or check if ?page=X works.
            for page in range(2, 6):
                page_url = f"{category_url}?page={page}"
                print(f"  Checking page {page}...")
                driver.get(page_url)
                time.sleep(2)
                
                new_urls = extract_urls_from_page(driver)
                if not new_urls:
                    print("  No URLs found, stopping pagination for this category.")
                    break
                    
                # Check if we are just seeing the same content (redirect to page 1)
                # Simple heuristic: if all new URLs are already in all_urls, stop.
                new_unique = [u for u in new_urls if u not in all_urls]
                if not new_unique:
                    print("  No new unique URLs found, stopping.")
                    break
                    
                for u in new_unique:
                    all_urls.add(u)
                print(f"  + Added {len(new_unique)} new URLs")
                
            save_urls(list(all_urls))
            
    finally:
        driver.quit()
        print("\n" + "="*60)
        print(f"✅ DONE! Collected total {len(all_urls)} URLs")

if __name__ == "__main__":
    main()

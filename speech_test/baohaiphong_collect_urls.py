"""
Step 1: Collect all URLs from baohaiphong.vn/podcast/diem-tin
Scrolls and clicks "Load More" until no more content, then saves all URLs.
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time
import json
import re
import random
import os

# User-Agent pool for rotation
USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0"
]

# List of podcast categories to crawl
CATEGORIES = [
    "https://baohaiphong.vn/podcast/diem-tin",
    "https://baohaiphong.vn/podcast/thoi-su",
    "https://baohaiphong.vn/podcast/doi-songgiai-tri",
    "https://baohaiphong.vn/podcast/checkin-hai-phong",
    "https://baohaiphong.vn/podcast/an-toan-giao-thong",
    "https://baohaiphong.vn/podcast/nghe-nguoi-tre-noi"
]

def get_random_user_agent():
    """Get a random user agent from pool"""
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
    
    # Additional anti-detection measures
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    # === JETSON ORIN / ARM64 COMPATIBILITY ===
    # Prioritize system-installed chromedriver
    chromedriver_path = "/usr/bin/chromedriver" 
    
    if not os.path.exists(chromedriver_path):
        chromedriver_path = "/usr/lib/chromium-browser/chromedriver"
        
    if os.path.exists(chromedriver_path):
        print(f"Using system chromedriver at: {chromedriver_path}")
        service = Service(executable_path=chromedriver_path)
        driver = webdriver.Chrome(service=service, options=options)
    else:
        print("⚠️  System chromedriver not found, using default (Selenium Manager)...")
        driver = webdriver.Chrome(options=options)
    
    # Mask webdriver property
    driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
        'source': '''
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            })
        '''
    })
    
    return driver

def scroll_and_load_all(driver, max_scrolls=1000):
    """Scroll and click 'Load More' until no more content"""
    print(f"Loading all items from page (Max scrolls: {max_scrolls})...")
    
    last_height = driver.execute_script("return document.body.scrollHeight")
    scrolls = 0
    no_change_count = 0
    clicks = 0
    
    while scrolls < max_scrolls:
        # Scroll to bottom
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(4) # Wait for content to load
        
        new_height = driver.execute_script("return document.body.scrollHeight")
        
        if new_height == last_height:
            no_change_count += 1
            print(f"  No new content loaded ({no_change_count}/3)...")
            
            if no_change_count >= 3:
                print("  Reached bottom or network slow. Stopping scroll.")
                break
            
            # Try clicking "Load More" button with multiple strategies
            try:
                # Strategy 1: The correct class found in source
                buttons = driver.find_elements(By.CSS_SELECTOR, ".onecms__loadmore")
                
                # Strategy 2: Text content "Xem thêm"
                if not buttons:
                    buttons = driver.find_elements(By.XPATH, "//a[contains(text(), 'Xem thêm')]")
                
                if buttons:
                    btn = buttons[0]
                    if btn.is_displayed():
                        print("  Found 'Load More' button (.onecms__loadmore), clicking...")
                        driver.execute_script("arguments[0].click();", btn)
                        time.sleep(5) # Wait longer for AJAX
                        no_change_count = 0 
                        clicks += 1
                        
                        # Extract and save URLs continuously (merging with existing)
                        current_urls = extract_all_urls(driver, silent=True)
                        # We need to pass the master list to save_urls to avoid overwriting with just current page
                        # But simpler: just return control to main loop or save purely local?
                        # Let's just print progress here. The main loop handles the master list.
                        print(f"  Found {len(current_urls)} URLs on this page so far...")
                        
                        continue
                    else:
                         print("  'Load More' button found but not visible.")
            except Exception as e:
                print(f"  Error clicking button: {e}")

            # Try scrolling up a bit and down again to trigger load
            driver.execute_script("window.scrollBy(0, -300);")
            time.sleep(1)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
        else:
            no_change_count = 0
            last_height = new_height
            scrolls += 1
            if scrolls % 5 == 0:
                print(f"  Scrolled {scrolls} times...")
        
    print(f"Finished loading. Total scrolls: {scrolls}, Total clicks: {clicks}")
    return scrolls

def extract_all_urls(driver, silent=False):
    """Extract all podcast item links from the page"""
    if not silent:
        print("\nExtracting all URLs...")
    
    urls = []
    
    # Find links to detail pages
    # Based on inspection: a[href*='diem-tin-podcast']
    elements = driver.find_elements(By.CSS_SELECTOR, "a[href*='diem-tin-podcast']")
    
    for elem in elements:
        href = elem.get_attribute("href")
        
        if not href:
            continue
            
        # Filter for detail pages
        # Must contain 'diem-tin-podcast' and end with .html
        # Exclude social share links
        if "diem-tin-podcast" in href and href.endswith(".html"):
            if "facebook.com" in href or "twitter.com" in href or "zalo" in href or "intent:" in href:
                continue
                
            if href not in urls:
                urls.append(href)
    
    print(f"Found {len(urls)} unique URLs")
    return urls

def save_urls(urls, filename="baohaiphong_urls.json"):
    """Save URLs to JSON file"""
    # print(f"\nSaving URLs to {filename}...")
    
    with open(filename, "w", encoding="utf-8") as f:
        json.dump({
            "total": len(urls),
            "urls": urls
        }, f, indent=2, ensure_ascii=False)
    
    # print(f"✅ Saved {len(urls)} URLs to {filename}")

def main():
    print("="*60)
    print("STEP 1: COLLECT ALL URLs (BAO HAI PHONG)")
    print("="*60)
    print("\nSetting up browser...")
    
    driver = setup_driver()
    all_urls = set()
    
    try:
        for url in CATEGORIES:
            print(f"\n\n>>> Processing Category: {url}")
            try:
                # 1. Load category page
                driver.get(url)
                time.sleep(3)
                
                # 2. Scroll and click "Load More" until no more content
                scroll_and_load_all(driver)
                
                # 3. Extract URLs from this category
                urls = extract_all_urls(driver)
                
                # 4. Add to master list
                initial_count = len(all_urls)
                for u in urls:
                    all_urls.add(u)
                new_count = len(all_urls)
                
                print(f"  + Added {new_count - initial_count} new URLs (Total: {new_count})")
                
                # 5. Save continuously
                save_urls(list(all_urls))
                
            except Exception as e:
                print(f"❌ Error processing {url}: {e}")
                continue
        
        print("\n" + "="*60)
        print(f"✅ DONE! Collected total {len(all_urls)} URLs from {len(CATEGORIES)} categories")
        print("="*60)
        print("\nNext step: Run baohaiphong_process_urls.py to download audio")
        
    finally:
        print("\nClosing browser...")
        driver.quit()

if __name__ == "__main__":
    main()

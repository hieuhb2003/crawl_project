"""
Step 1: Collect all URLs from media.chinhphu.vn/radio-news.htm
Scrolls and clicks "Xem thêm" until no more content, then saves all URLs
"""

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time
import json
import re
import os
import random

# User-Agent pool for rotation
USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0"
]

def get_random_user_agent():
    """Get a random user agent from pool"""
    return random.choice(USER_AGENTS)

def setup_driver():
    """Setup Chrome WebDriver with manual path for ARM64"""
    options = webdriver.ChromeOptions()
    
    options.add_argument("--headless")
    
    # Các option bắt buộc để chạy ổn định trên Linux/Docker/Jetson
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu") # Thường cần cho Chrome headless
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(f"user-agent={get_random_user_agent()}")
    
    # Additional anti-detection measures
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    # === PHẦN QUAN TRỌNG NHẤT: TRỎ ĐƯỜNG DẪN ===
    # Đường dẫn mặc định khi cài bằng apt-get
    chromedriver_path = "/usr/bin/chromedriver" 
    
    # Kiểm tra xem file có tồn tại không
    if not os.path.exists(chromedriver_path):
        # Thử tìm ở đường dẫn phụ (đôi khi nó nằm ở đây)
        chromedriver_path = "/usr/lib/chromium-browser/chromedriver"
        if not os.path.exists(chromedriver_path):
             raise FileNotFoundError("Không tìm thấy chromedriver! Hãy chạy: sudo apt install chromium-chromedriver")

    print(f"Using chromedriver at: {chromedriver_path}")
    service = Service(executable_path=chromedriver_path)
    
    # Khởi tạo driver với Service
    try:
        driver = webdriver.Chrome(service=service, options=options)
    except Exception as e:
        print(f"Lỗi khởi tạo Chrome: {e}")
        raise e
    
    # Mask webdriver property
    driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
        'source': '''
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            })
        '''
    })
    
    return driver

def scroll_and_load_all(driver):
    """Scroll and click 'Xem thêm' until no more content"""
    print("Loading all items from page...")
    
    clicks = 0
    last_height = driver.execute_script("return document.body.scrollHeight")
    no_change_count = 0
    
    while True:
        # Scroll to bottom
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        
        # Try to find and click "Xem thêm" button
        try:
            btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, ".btn-viewmor"))
            )
            
            # Scroll to button
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
            time.sleep(1)
            
            btn.click()
            clicks += 1
            print(f"  Clicked 'Xem thêm' button ({clicks} times)")
            
            # Wait for new content to load
            time.sleep(3)
            
            # Reset no change counter
            no_change_count = 0
            
        except (TimeoutException, NoSuchElementException):
            print("  No 'Xem thêm' button found")
            break
        
        # Check if page height changed
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            no_change_count += 1
            print(f"  Page height unchanged ({no_change_count}/3)")
            
            if no_change_count >= 3:
                print("  Page height not changing after 3 attempts, stopping")
                break
        else:
            no_change_count = 0
        
        last_height = new_height
    
    print(f"\nFinished loading (clicked {clicks} times)")
    return clicks

def extract_all_urls(driver):
    """Extract all radio news item links from the page"""
    print("\nExtracting all URLs...")
    
    urls = []
    
    # Find all links that look like detail pages
    elements = driver.find_elements(By.CSS_SELECTOR, "a[href*='.htm']")
    
    for elem in elements:
        href = elem.get_attribute("href")
        
        if not href or "radio-news.htm" in href:
            continue
        
        # Filter for detail pages (contains ID at end)
        # e.g., /ho-tro-1100-ty-dong-cho-4-tinh-thiet-hai-do-mua-lu-102251124162352928.htm
        if re.search(r'-\d{18,}\.htm$', href):
            if href not in urls:
                urls.append(href)
    
    print(f"Found {len(urls)} unique URLs")
    return urls

def save_urls(urls, filename="chinhphu_urls.json"):
    """Save URLs to JSON file"""
    print(f"\nSaving URLs to {filename}...")
    
    with open(filename, "w", encoding="utf-8") as f:
        json.dump({
            "total": len(urls),
            "urls": urls
        }, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Saved {len(urls)} URLs to {filename}")

def main():
    print("="*60)
    print("STEP 1: COLLECT ALL URLs")
    print("="*60)
    print("\nSetting up browser...")
    
    driver = setup_driver()
    
    try:
        # 1. Load main page
        print("\nLoading main page...")
        driver.get("https://media.chinhphu.vn/radio-news.htm")
        time.sleep(3)
        
        # 2. Scroll and click "Xem thêm" until no more content
        total_clicks = scroll_and_load_all(driver)
        
        # 3. Extract all URLs
        urls = extract_all_urls(driver)
        
        # 4. Save to file
        save_urls(urls)
        
        print("\n" + "="*60)
        print(f"✅ DONE! Clicked {total_clicks} times, found {len(urls)} URLs")
        print("="*60)
        print("\nNext step: Run chinhphu_process_urls.py to download audio")
        
    finally:
        print("\nClosing browser...")
        driver.quit()

if __name__ == "__main__":
    main()

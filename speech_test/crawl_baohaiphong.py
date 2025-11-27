"""
Crawler for baohaiphong.vn/podcast/diem-tin
Uses Selenium to handle infinite scroll and extract audio from detail pages.
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from tqdm import tqdm
import time
import random
import json
import os
import subprocess
import re
import hashlib

# Configuration
CONFIG = {
    "save_audio": True,
    "audio_format": "wav",
    "sample_rate": "16000",
    "channels": "1",
    "headless": True
}

# User-Agent pool for rotation
USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0"
]

# Load config if exists
if os.path.exists("pipeline_config.json"):
    with open("pipeline_config.json", "r") as f:
        CONFIG.update(json.load(f))

OUTPUT_DIR = "downloads_audio"
os.makedirs(OUTPUT_DIR, exist_ok=True)

PROCESSED_FILE = "processed_baohaiphong.json"
processed_items = set()

if os.path.exists(PROCESSED_FILE):
    with open(PROCESSED_FILE, "r") as f:
        processed_items = set(json.load(f))

def get_md5(string):
    return hashlib.md5(string.encode()).hexdigest()

def save_processed_items(processed_set):
    with open(PROCESSED_FILE, "w") as f:
        json.dump(list(processed_set), f, indent=2)

def get_random_user_agent():
    """Get a random user agent from pool"""
    return random.choice(USER_AGENTS)

def setup_driver():
    """Setup Chrome WebDriver (MacBook version)"""
    options = webdriver.ChromeOptions()
    
    if CONFIG.get("headless", True):
        options.add_argument("--headless")
    
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(f"user-agent={get_random_user_agent()}")
    
    # Additional anti-detection measures
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
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

def scroll_to_load_items(driver, max_scrolls=500):
    """Scroll down to load items via infinite scroll"""
    print(f"Scrolling to load items (Max: {max_scrolls})...")
    
    last_height = driver.execute_script("return document.body.scrollHeight")
    scrolls = 0
    no_change_count = 0
    
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
                # Strategy 1: Specific class
                buttons = driver.find_elements(By.CSS_SELECTOR, "div.c-view-more")
                
                # Strategy 2: Text content "Xem thêm"
                if not buttons:
                    buttons = driver.find_elements(By.XPATH, "//div[contains(text(), 'Xem thêm')]")
                
                # Strategy 3: Last div with an icon (<i> tag) inside main container
                if not buttons:
                    # Assuming the list is in a container, or just find all divs with i at the bottom
                    candidates = driver.find_elements(By.XPATH, "//div[.//i]")
                    if candidates:
                        # Filter for visible ones at the bottom
                        buttons = [candidates[-1]]

                if buttons:
                    btn = buttons[0]
                    if btn.is_displayed():
                        print("  Found 'Load More' button, clicking...")
                        driver.execute_script("arguments[0].click();", btn)
                        time.sleep(3)
                        no_change_count = 0 
                        continue
                    else:
                         print("  'Load More' button found but not visible.")
                else:
                    print("  No 'Load More' button found.")
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
        
    print(f"Finished scrolling. Total scrolls: {scrolls}")

def extract_item_links(driver):
    """Extract podcast item links from the list page"""
    links = []
    
    # Find links to detail pages
    # Based on inspection: a[href*='diem-tin-podcast-ngay-']
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
                
            if href not in links:
                links.append(href)
                
    print(f"Found {len(links)} items.")
    return links

def extract_audio_from_page(driver, url):
    """Visit detail page and extract audio source"""
    try:
        driver.get(url)
        # Random delay
        time.sleep(random.uniform(2, 4))
        
        # Try to find audio source via JavaScript (based on inspection findings)
        audio_url = driver.execute_script("""
            // Method 1: HTML5 audio/video element
            var audioElem = document.querySelector('audio');
            if (audioElem && audioElem.src) {
                return audioElem.src;
            }
            
            var videoElem = document.querySelector('video');
            if (videoElem && videoElem.src) {
                return videoElem.src;
            }
            
            // Method 2: Source tag inside audio/video
            var source = document.querySelector('audio source, video source');
            if (source && source.src) {
                return source.src;
            }
            
            // Method 3: Search script tags for mp3/m4a links (Found during inspection)
            const scripts = document.querySelectorAll('script');
            for (let script of scripts) {
                const match = script.innerHTML.match(/https?:\\/\\/[^\\'\\"\\s]+\\.(mp3|m4a)[^\\'\\"\\s]*/);
                if (match) {
                    return match[0];
                }
                const fileMatch = script.innerHTML.match(/file\\s*:\\s*['\\"](https?:\\/\\/[^\\'\\"\\s]+\\.(mp3|m4a)[^\\'\\"\\s]*)['\\"]/);
                if (fileMatch && fileMatch[1]) {
                    return fileMatch[1];
                }
            }
            
            return null;
        """)
        
        if audio_url:
            return audio_url
        
        # Fallback: Search page source for audio URLs via Python Regex
        page_source = driver.page_source
        
        match = re.search(r'(https?://[^\s\'"<>]+\.(?:mp3|m4a))', page_source)
        if match:
            return match.group(1)
            
        return None
        
    except Exception as e:
        print(f"  Error extracting audio: {e}")
        return None

def get_title_from_page(driver):
    """Extract title from current page"""
    try:
        title_elem = driver.find_element(By.TAG_NAME, "h1")
        return title_elem.text.strip()
    except:
        return "Unknown"

def download_audio_ffmpeg(audio_url, output_path):
    """Downloads audio using ffmpeg"""
    if os.path.exists(output_path):
        return True
    
    cmd = [
        "ffmpeg",
        "-y",
        "-i", audio_url,
        "-vn",
        "-acodec", "pcm_s16le" if CONFIG["audio_format"] == "wav" else "libmp3lame",
        "-ar", str(CONFIG["sample_rate"]),
        "-ac", str(CONFIG["channels"]),
        output_path
    ]
    
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Download failed: {output_path}")
        print(f"   Error: {e.stderr.decode()[:200]}")
        return False

def main():
    print("="*60)
    print("BAO HAI PHONG CRAWLER")
    print("="*60)
    
    print("Setting up browser...")
    driver = setup_driver()
    
    try:
        # 1. Load list page
        list_url = "https://baohaiphong.vn/podcast/diem-tin"
        print(f"Loading list page: {list_url}")
        driver.get(list_url)
        time.sleep(3)
        
        # 2. Scroll to load items
        # Set max_scrolls to a high number for full crawl
        scroll_to_load_items(driver, max_scrolls=1000)
        
        # 3. Extract links
        links = extract_item_links(driver)
        
        if not links:
            print("No items found. Stopping.")
            return
            
        # 4. Process items
        with tqdm(total=len(links), desc="Processing", unit="item") as pbar:
            for url in links:
                item_hash = get_md5(url)
                
                if item_hash in processed_items:
                    pbar.update(1)
                    continue
                    
                # Extract audio
                audio_url = extract_audio_from_page(driver, url)
                
                if audio_url:
                    title = get_title_from_page(driver)
                    safe_title = "".join([c for c in title if c.isalnum() or c in (' ', '-', '_')]).strip()
                    safe_title = safe_title.replace(" ", "_")[:50]
                    
                    if CONFIG["save_audio"]:
                        filename = f"BHP_{safe_title}.{CONFIG['audio_format']}"
                        output_path = os.path.join(OUTPUT_DIR, filename)
                        download_audio_ffmpeg(audio_url, output_path)
                    
                    processed_items.add(item_hash)
                    save_processed_items(processed_items)
                else:
                    print(f"\n⚠️  No audio found: {url}")
                    processed_items.add(item_hash) # Mark as processed to avoid retry
                    save_processed_items(processed_items)
                    
                pbar.update(1)
                
                # Random delay
                time.sleep(random.uniform(3, 6))
            
    finally:
        print("\nClosing browser...")
        driver.quit()

if __name__ == "__main__":
    main()

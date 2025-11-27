"""
Crawler for vov.vn/podcast/cau-chuyen-thoi-su
Uses Selenium to handle pagination and extract audio from detail pages.
"""

from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options as FirefoxOptions
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

PROCESSED_FILE = "processed_vov.json"
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
    """Setup Firefox WebDriver with random user-agent"""
    options = FirefoxOptions()
    
    if CONFIG.get("headless", True):
        options.add_argument("--headless")
    
    # Firefox specific options
    options.set_preference("general.useragent.override", get_random_user_agent())
    options.set_preference("dom.webdriver.enabled", False)
    options.set_preference('useAutomationExtension', False)
    
    # Try to find system installed geckodriver (common on Linux ARM64/Jetson)
    service = None
    system_paths = [
        "/usr/bin/geckodriver",
        "/usr/local/bin/geckodriver",
        "/snap/bin/geckodriver"
    ]
    
    executable_path = None
    for path in system_paths:
        if os.path.exists(path):
            executable_path = path
            break
            
    if executable_path:
        print(f"Using system geckodriver at: {executable_path}")
        service = Service(executable_path=executable_path)
        try:
            driver = webdriver.Firefox(options=options, service=service)
        except Exception as e:
            print(f"Failed to use system geckodriver: {e}")
            print("Falling back to Selenium Manager...")
            driver = webdriver.Firefox(options=options)
    else:
        driver = webdriver.Firefox(options=options)
    
    return driver

def extract_item_links(driver):
    """Extract podcast item links from the list page"""
    links = []
    
    # Find links to detail pages
    # Usually in h4 > a or similar structure
    elements = driver.find_elements(By.CSS_SELECTOR, "a[href*='.vov']")
    
    for elem in elements:
        href = elem.get_attribute("href")
        
        if not href:
            continue
            
        # Filter for detail pages (usually ends with .vov and has ID)
        # e.g. https://vov.vn/podcast/cau-chuyen-thoi-su/abc-xyz-post123.vov
        if "podcast/" in href and "-post" in href and href.endswith(".vov"):
            if href not in links:
                links.append(href)
                
    return links

def extract_audio_from_page(driver, url):
    """Visit detail page and extract audio source"""
    try:
        driver.get(url)
        # Random delay
        time.sleep(random.uniform(2, 4))
        
        # Try to find audio source via JavaScript
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
            
            // Method 3: Check for common player variables (e.g. if they use a custom player)
            // This part is speculative, adjust based on actual site inspection
            
            return null;
        """)
        
        if audio_url:
            return audio_url
        
        # Fallback: Search page source for audio URLs
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
    print("VOV PODCAST CRAWLER")
    print("="*60)
    
    print("Setting up browser...")
    driver = setup_driver()
    
    try:
        page = 0
        base_url = "https://vov.vn/podcast/cau-chuyen-thoi-su"
        
        while True:
            page_url = f"{base_url}?page={page}"
            print(f"\nCrawling Page {page}: {page_url}")
            
            driver.get(page_url)
            time.sleep(3)
            
            # Extract links
            links = extract_item_links(driver)
            
            if not links:
                print("No items found on this page. Stopping.")
                break
                
            print(f"Found {len(links)} items.")
            
            # Process items
            with tqdm(total=len(links), desc=f"Page {page}", unit="item") as pbar:
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
                            filename = f"VOV_{safe_title}.{CONFIG['audio_format']}"
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
            
            page += 1
            
            # Page delay
            time.sleep(random.uniform(2, 5))
            
    finally:
        print("\nClosing browser...")
        driver.quit()

if __name__ == "__main__":
    main()

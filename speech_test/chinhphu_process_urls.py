"""
Step 2: Process URLs from chinhphu_urls.json
Loads URLs and downloads audio for each one
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
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

PROCESSED_FILE = "processed_chinhphu_radio.json"
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
    """Setup Chrome WebDriver with random user-agent"""
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

def load_urls(filename="chinhphu_urls.json"):
    """Load URLs from JSON file"""
    if not os.path.exists(filename):
        print(f"❌ Error: {filename} not found!")
        print("Please run chinhphu_collect_urls.py first")
        return []
    
    with open(filename, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    urls = data.get("urls", [])
    return urls

def extract_audio_from_page(driver, url):
    """Visit detail page and extract audio source"""
    try:
        driver.get(url)
        # Random delay to mimic human behavior
        time.sleep(random.uniform(2, 4))
        
        # Try to find audio source via JavaScript
        audio_url = driver.execute_script("""
            // Method 1: JW Player
            if (typeof jwplayer !== 'undefined') {
                try {
                    var playlist = jwplayer().getPlaylist();
                    if (playlist && playlist[0] && playlist[0].sources && playlist[0].sources[0]) {
                        return playlist[0].sources[0].file;
                    }
                } catch(e) {}
            }
            
            // Method 2: HTML5 audio/video element
            var audioElem = document.querySelector('audio');
            if (audioElem && audioElem.src) {
                return audioElem.src;
            }
            
            var videoElem = document.querySelector('video');
            if (videoElem && videoElem.src) {
                return videoElem.src;
            }
            
            // Method 3: Source tag inside audio/video
            var source = document.querySelector('audio source, video source');
            if (source && source.src) {
                return source.src;
            }
            
            return null;
        """)
        
        if audio_url:
            return audio_url
        
        # Fallback: Search page source for audio URLs
        page_source = driver.page_source
        
        match = re.search(r'(https?://[^\s\'"<>]+\.(?:mp3|m4a))', page_source)
        if match:
            return match.group(1)
        
        match = re.search(r'file\s*:\s*["\']([^"\']+\.(?:mp3|m4a))["\']', page_source)
        if match:
            return match.group(1)
        
        return None
        
    except Exception as e:
        print(f"  Error: {e}")
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
        return True  # Already exists
    
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
    print("STEP 2: PROCESS URLs AND DOWNLOAD AUDIO")
    print("="*60)
    
    # 1. Load URLs
    urls = load_urls()
    
    if not urls:
        return
    
    print(f"✅ Loaded {len(urls)} URLs")
    
    # 2. Setup browser
    print("Setting up browser...")
    driver = setup_driver()
    
    try:
        # 3. Process each URL with tqdm progress bar
        skipped = 0
        downloaded = 0
        failed = 0
        
        with tqdm(total=len(urls), desc="Processing", unit="item") as pbar:
            for url in urls:
                item_hash = get_md5(url)
                
                # Skip if already processed
                if item_hash in processed_items:
                    skipped += 1
                    pbar.set_postfix({"skip": skipped, "ok": downloaded, "fail": failed})
                    pbar.update(1)
                    continue
                
                # Extract audio
                audio_url = extract_audio_from_page(driver, url)
                
                if audio_url:
                    # Get title
                    title = get_title_from_page(driver)
                    safe_title = "".join([c for c in title if c.isalnum() or c in (' ', '-', '_')]).strip()
                    safe_title = safe_title.replace(" ", "_")[:50]
                    
                    if CONFIG["save_audio"]:
                        filename = f"CHINHPHU_{safe_title}.{CONFIG['audio_format']}"
                        output_path = os.path.join(OUTPUT_DIR, filename)
                        
                        if download_audio_ffmpeg(audio_url, output_path):
                            downloaded += 1
                        else:
                            failed += 1
                    
                    # Mark as processed
                    processed_items.add(item_hash)
                    save_processed_items(processed_items)
                else:
                    # Log error
                    print(f"\n⚠️  No audio found: {url}")
                    failed += 1
                    # Still mark as processed to avoid retry
                    processed_items.add(item_hash)
                    save_processed_items(processed_items)
                
                # Update progress bar
                pbar.set_postfix({"skip": skipped, "ok": downloaded, "fail": failed})
                pbar.update(1)
                
                # Random delay between items
                delay = random.uniform(3, 7)
                time.sleep(delay)
        
        # Summary
        print("\n" + "="*60)
        print("✅ PROCESSING COMPLETE!")
        print("="*60)
        print(f"Total URLs: {len(urls)}")
        print(f"Skipped (already processed): {skipped}")
        print(f"Downloaded: {downloaded}")
        print(f"Failed (no audio): {failed}")
        print(f"Total processed in this run: {downloaded + failed}")
        print("="*60)
        
    finally:
        print("\nClosing browser...")
        driver.quit()

if __name__ == "__main__":
    main()

"""
Step 2: Process URLs from ANTV Radio
Loads URLs and downloads audio for each one.
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
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
    "audio_format": "mp3", # ANTV usually provides mp3
    "sample_rate": "16000",
    "channels": "1",
    "headless": True
}

# User-Agent pool
USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
]

OUTPUT_DIR = "downloads_audio"
os.makedirs(OUTPUT_DIR, exist_ok=True)

PROCESSED_FILE = "processed_antv.json"
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
    return random.choice(USER_AGENTS)

def setup_driver():
    """Setup Chrome WebDriver (Compatible with Jetson Orin/ARM64)"""
    options = webdriver.ChromeOptions()
    if CONFIG.get("headless", True):
        options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(f"user-agent={get_random_user_agent()}")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
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

def extract_audio_from_page(driver, url):
    """Visit detail page and extract audio source"""
    try:
        driver.get(url)
        time.sleep(random.uniform(2, 4))
        
        # ANTV audio is often in script tags
        audio_url = driver.execute_script("""
            // Method 1: Search script tags for mp3/m4a links
            const scripts = document.querySelectorAll('script');
            for (let script of scripts) {
                const match = script.innerHTML.match(/https?:\\/\\/[^\\'\\"\\s]+\\.(mp3|m4a|wav)[^\\'\\"\\s]*/);
                if (match) {
                    return match[0];
                }
                const fileMatch = script.innerHTML.match(/file\\s*:\\s*['\\"](https?:\\/\\/[^\\'\\"\\s]+\\.(mp3|m4a|wav)[^\\'\\"\\s]*)['\\"]/);
                if (fileMatch && fileMatch[1]) {
                    return fileMatch[1];
                }
            }
            
            // Method 2: HTML5 audio/video element
            var audioElem = document.querySelector('audio');
            if (audioElem && audioElem.src) return audioElem.src;
            
            return null;
        """)
        
        if audio_url:
            return audio_url
            
        return None
        
    except Exception as e:
        print(f"  Error extracting audio: {e}")
        return None

def get_title_from_page(driver):
    try:
        title_elem = driver.find_element(By.TAG_NAME, "h1")
        return title_elem.text.strip()
    except:
        return "Unknown"

def download_audio_ffmpeg(audio_url, output_path):
    if os.path.exists(output_path):
        return True
    
    cmd = [
        "ffmpeg", "-y", "-i", audio_url, "-vn",
        "-acodec", "libmp3lame" if output_path.endswith(".mp3") else "pcm_s16le",
        "-ar", str(CONFIG["sample_rate"]),
        "-ac", str(CONFIG["channels"]),
        output_path
    ]
    
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Download failed: {output_path}")
        return False

def main():
    print("="*60)
    print("STEP 2: PROCESS URLs (ANTV RADIO)")
    print("="*60)
    
    if not os.path.exists("antv_urls.json"):
        print("antv_urls.json not found. Run antv_collect_urls.py first.")
        return

    with open("antv_urls.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    urls = data.get("urls", [])
    print(f"Loaded {len(urls)} URLs")

    driver = setup_driver()
    
    try:
        with tqdm(total=len(urls), desc="Processing", unit="item") as pbar:
            for url in urls:
                item_hash = get_md5(url)
                if item_hash in processed_items:
                    pbar.update(1)
                    continue
                    
                audio_url = extract_audio_from_page(driver, url)
                
                if audio_url:
                    title = get_title_from_page(driver)
                    safe_title = "".join([c for c in title if c.isalnum() or c in (' ', '-', '_')]).strip()
                    safe_title = safe_title.replace(" ", "_")[:50]
                    
                    filename = f"ANTV_{safe_title}.mp3"
                    output_path = os.path.join(OUTPUT_DIR, filename)
                    
                    if download_audio_ffmpeg(audio_url, output_path):
                        processed_items.add(item_hash)
                        save_processed_items(processed_items)
                else:
                    # print(f"\n⚠️  No audio found: {url}")
                    processed_items.add(item_hash) # Mark processed to skip next time
                    save_processed_items(processed_items)
                    
                pbar.update(1)
                time.sleep(random.uniform(2, 5))
            
    finally:
        driver.quit()

if __name__ == "__main__":
    main()

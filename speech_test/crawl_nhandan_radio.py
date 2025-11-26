import requests
import re
import os
import time
import random
import hashlib
import json
import subprocess
from bs4 import BeautifulSoup

# Load Config
try:
    with open("pipeline_config.json", "r") as f:
        CONFIG = json.load(f)
except FileNotFoundError:
    CONFIG = {
        "save_video": False,
        "save_audio": True,
        "audio_format": "wav",
        "sample_rate": 16000,
        "channels": 1,
        "output_dir": "downloads_audio"
    }

OUTPUT_DIR = CONFIG["output_dir"]
PROCESSED_FILE = "processed_videos_nhandan.json"
STATE_FILE = "crawler_state_nhandan.json"

# List of common User-Agents for rotation
USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
]

def get_headers():
    """Returns headers with a random User-Agent."""
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,vi;q=0.8"
    }

def get_md5(text):
    return hashlib.md5(text.encode('utf-8')).hexdigest()

def load_processed_videos():
    if os.path.exists(PROCESSED_FILE):
        try:
            with open(PROCESSED_FILE, "r") as f:
                return set(json.load(f))
        except:
            return set()
    return set()

def save_processed_videos(processed_set):
    with open(PROCESSED_FILE, "w") as f:
        json.dump(list(processed_set), f)

def load_crawler_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_crawler_state(page):
    state = {"last_page": page}
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

def download_audio_ffmpeg(audio_url, output_path):
    """Extracts audio directly using ffmpeg."""
    if os.path.exists(output_path):
        print(f"File already exists: {output_path}")
        return

    print(f"Downloading Audio: {audio_url} -> {output_path}")
    
    # Prepare headers for ffmpeg
    headers = get_headers()
    headers_str = "".join([f"{k}: {v}\r\n" for k, v in headers.items()])
    
    cmd = [
        "ffmpeg",
        "-y",
        "-headers", headers_str,
        "-i", audio_url,
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", str(CONFIG["sample_rate"]),
        "-ac", str(CONFIG["channels"]),
        "-nostdin",
        "-loglevel", "error",
        output_path
    ]
    
    try:
        subprocess.run(cmd, check=True)
        print("Download complete.")
    except subprocess.CalledProcessError as e:
        print(f"Error downloading audio: {e}")

def get_audio_source(url):
    """Fetches the article page and extracts the audio URL from JSON data."""
    try:
        response = requests.get(url, headers=get_headers())
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract from <div class="item_media_json">["url"]</div>
        media_div = soup.find("div", class_="item_media_json")
        if media_div:
            try:
                # The content is a JSON string list: ["url"]
                media_list = json.loads(media_div.get_text(strip=True))
                if media_list and len(media_list) > 0:
                    audio_url = media_list[0]
                    # Fix escaped slashes if needed (json.loads handles it usually)
                    if not audio_url.startswith("http"):
                        audio_url = "https://" + audio_url # Should verify if needed, usually absolute
                    return audio_url
            except json.JSONDecodeError:
                print(f"Error decoding JSON from {url}")
                
        return None
    except Exception as e:
        print(f"Error fetching audio source {url}: {e}")
        return None

def main():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        
    processed_videos = load_processed_videos()
    print(f"Loaded {len(processed_videos)} processed items.")
    
    state = load_crawler_state()
    start_page = state.get("last_page", 1)
    print(f"Resuming from page {start_page}")
    
    base_url = "https://radio.nhandan.vn/ban-tin-thoi-su-c5"
    current_page = start_page
    
    while True:
        if current_page == 1:
            page_url = base_url
        else:
            page_url = f"{base_url}/page/{current_page}"
            
        print(f"\nCrawling Page {current_page}: {page_url}")
        
        try:
            response = requests.get(page_url, headers=get_headers())
            
            # Check for 404 or redirect to handle end of pagination
            if response.status_code == 404:
                print("Reached end of pages (404).")
                break
                
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find article links
            # Structure: <div class="box-title-main"> <a href="...">Title</a> </div>
            # Or generic search for links within article blocks
            
            article_links = []
            # Based on analysis, links are often in h2 or h3 tags or specific classes
            # Let's look for links that look like articles (contain ID like -iXXXX)
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if re.search(r'-i\d+$', href):
                    if not href.startswith("http"):
                        href = "https://radio.nhandan.vn" + href
                    
                    # Try to get title from title attribute, then text, then URL slug
                    title = a.get("title")
                    if not title:
                        title = a.get_text(strip=True)
                    if not title:
                        # Extract slug from URL: .../slug-i1234
                        match = re.search(r'/([^/]+)-i\d+$', href)
                        if match:
                            title = match.group(1).replace("-", " ")
                        else:
                            title = "Unknown Title"
                    
                    if not any(v['url'] == href for v in article_links):
                        article_links.append({"url": href, "title": title})
            
            if not article_links:
                print("No articles found on this page. Stopping.")
                break
                
            print(f"Found {len(article_links)} articles.")
            
            for article in article_links:
                article_url = article['url']
                article_hash = get_md5(article_url)
                
                if article_hash in processed_videos:
                    print(f"  Skipping (Processed): {article['title']}")
                    continue
                    
                print(f"  Processing: {article['title']}")
                audio_url = get_audio_source(article_url)
                
                if audio_url:
                    print(f"    Source: {audio_url}")
                    
                    safe_title = "".join([c for c in article['title'] if c.isalnum() or c in (' ', '-', '_')]).strip()
                    safe_title = safe_title.replace(" ", "_")[:50]
                    
                    if CONFIG["save_audio"]:
                        filename = f"NHANDAN_{safe_title}.{CONFIG['audio_format']}"
                        output_path = os.path.join(OUTPUT_DIR, filename)
                        download_audio_ffmpeg(audio_url, output_path)
                    
                    # Mark as processed
                    processed_videos.add(article_hash)
                    save_processed_videos(processed_videos)
                    
                    # Random delay
                    delay = random.uniform(1, 3)
                    print(f"    Sleeping for {delay:.2f}s...")
                    time.sleep(delay)
                else:
                    print("    Could not find Audio source.")
            
            # Save state
            save_crawler_state(current_page)
            
            # Next page
            current_page += 1
            
            # Page delay
            page_delay = random.uniform(2, 5)
            print(f"Page done. Sleeping for {page_delay:.2f}s before next page...")
            time.sleep(page_delay)
            
        except Exception as e:
            print(f"Error crawling page {current_page}: {e}")
            # If it's a connection error, maybe wait and retry, but for now we break or continue
            time.sleep(5)
            # break # Optional: stop on error

if __name__ == "__main__":
    main()

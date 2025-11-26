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
PROCESSED_FILE = "processed_videos_qdnd_podcast.json"
STATE_FILE = "crawler_state_qdnd_podcast.json"

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

def download_audio_ffmpeg(video_url, output_path):
    """Extracts audio directly from video URL using ffmpeg."""
    if os.path.exists(output_path):
        print(f"File already exists: {output_path}")
        return

    print(f"Extracting Audio: {video_url} -> {output_path}")
    
    cmd = [
        "ffmpeg",
        "-y",
        "-i", video_url,
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
        print("Extraction complete.")
    except subprocess.CalledProcessError as e:
        print(f"Error extracting audio: {e}")

def get_audio_source(url):
    """Fetches the page and extracts the direct audio link."""
    print(f"Fetching audio source from: {url}")
    try:
        response = requests.get(url, headers=get_headers())
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 1. Try to find audio in div.mediaurl[data-src]
        media_div = soup.find("div", class_="mediaurl")
        if media_div and media_div.get("data-src"):
            return media_div.get("data-src")
            
        # 2. Broad search for any element with data-src ending in .mp3
        for element in soup.find_all(attrs={"data-src": True}):
            src = element["data-src"]
            if ".mp3" in src:
                return src

        # 3. Regex for direct mp3 links in source
        match = re.search(r'https?://[^"\']+\.mp3', response.text)
        if match:
            return match.group(0)

        # 4. Fallback: Regex to find the video file (intVideo)
        match = re.search(r"intVideo\('[^']+',\s*'([^']+)'\)", response.text)
        if match:
            return match.group(1)
            
        print(f"Could not find audio source in {url}")
        return None
    except Exception as e:
        print(f"Error fetching audio source {url}: {e}")
        return None

def main():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        
    processed_videos = load_processed_videos()
    print(f"Loaded {len(processed_videos)} processed videos.")
    
    state = load_crawler_state()
    start_page = state.get("last_page", 1)
    print(f"Resuming from page {start_page}")
    
    base_api_url = "https://media.qdnd.vn/Ajaxloads/ServiceData.asmx/LoadMoreAudioList"
    current_page = start_page
    
    while True:
        print(f"\nCrawling Page {current_page}...")
        
        # API Payload
        # pageindex is 0-based
        payload = {
            "pageid": "vi",
            "theloai": 4,
            "pageindex": current_page - 1,
            "pagesize": 12,
            "mediaid": 0,
            "tenchuyenmuc": "podcast"
        }
        
        try:
            response = requests.post(base_api_url, headers={**get_headers(), "Content-Type": "application/json"}, json=payload)
            response.raise_for_status()
            
            # The API returns JSON with 'd' field containing HTML
            data = response.json()
            html_content = data.get("d", "")
            
            if not html_content:
                print("No content returned (end of pages).")
                break
            
            # DEBUG: Print content preview
            print(f"HTML Content Preview: {html_content[:500]}...")
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Find video links
            # Structure in API response: <article class="media-small-news ..."> <a href="..."> ... </a> </article>
            
            video_links = []
            for a in soup.find_all("a", href=True):
                href = a["href"]
                
                if not href.startswith("http"):
                    href = "https://media.qdnd.vn" + href
                
                # DEBUG: Print found link
                # print(f"Found link: {href}")
                
                # Filter: Must be media.qdnd.vn and look like a detail page
                if not href.startswith("https://media.qdnd.vn/"):
                    continue
                    
                if ("/video/" in href or "/audio-podcast/" in href or "/podcast/" in href) and re.search(r'-\d+$', href):
                     title = a.get("title") or a.get_text(strip=True)
                     
                     if not any(v['url'] == href for v in video_links):
                        video_links.append({"url": href, "title": title})
                     else:
                        pass # Duplicate
                else:
                     # DEBUG: Print rejected link
                     print(f"Rejected: {href}")
            
            if not video_links:
                print("No videos found on this page. Stopping.")
                break
                
            print(f"Found {len(video_links)} videos.")
            
            for video in video_links:
                video_url = video['url']
                video_hash = get_md5(video_url)
                
                if video_hash in processed_videos:
                    print(f"  Skipping (Processed): {video['title']}")
                    continue
                    
                print(f"  Processing: {video['title']}")
                audio_url = get_audio_source(video_url)
                
                if audio_url:
                    print(f"    Source: {audio_url}")
                    
                    safe_title = "".join([c for c in video['title'] if c.isalnum() or c in (' ', '-', '_')]).strip()
                    safe_title = safe_title.replace(" ", "_")[:50]
                    
                    if CONFIG["save_audio"]:
                        filename = f"QDND_PODCAST_{safe_title}.{CONFIG['audio_format']}"
                        output_path = os.path.join(OUTPUT_DIR, filename)
                        download_audio_ffmpeg(audio_url, output_path)
                    
                    # Mark as processed
                    processed_videos.add(video_hash)
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
            time.sleep(5)
            # break # Optional: stop on error

if __name__ == "__main__":
    main()

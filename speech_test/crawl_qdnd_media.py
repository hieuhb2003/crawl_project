import requests
import re
import os
import time
import random
from bs4 import BeautifulSoup
import json
import subprocess

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

BASE_URL = "https://media.qdnd.vn"
API_URL = "https://media.qdnd.vn/Ajaxloads/ServiceData.asmx/LoadMediaPageDetaileByPageIndex"

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
        "Content-Type": "application/json"
    }

CATEGORIES = {
    "THOI_SU": "https://media.qdnd.vn/thoi-su",
    "QUOC_PHONG_AN_NINH": "https://media.qdnd.vn/quoc-phong-an-ninh",
    "BAO_VE_NEN_TANG": "https://media.qdnd.vn/bao-ve-nen-tang-tu-tuong-cua-dang",
    "CAU_LAC_BO_CHIEN_SI": "https://media.qdnd.vn/cau-lac-bo-chien-si",
    "PHONG_SU_DIEU_TRA": "https://media.qdnd.vn/phong-su-dieu-tra"
}

def get_category_info(url):
    """Fetches the category page to extract _glvtheloai (ID) and _glvtieude (Slug)."""
    print(f"Fetching category info from: {url}")
    try:
        response = requests.get(url, headers=get_headers())
        response.raise_for_status()
        
        # Extract variables using regex
        theloai_match = re.search(r"var _glvtheloai = '(\d+)';", response.text)
        tieude_match = re.search(r"var _glvtieude = '([^']+)';", response.text)
        
        if theloai_match and tieude_match:
            return {
                "theloai": int(theloai_match.group(1)),
                "tieude": tieude_match.group(1)
            }
        else:
            print(f"Could not find category info in {url}")
            return None
    except Exception as e:
        print(f"Error fetching category {url}: {e}")
        return None

def get_video_list(cat_info, page_index):
    """Calls the AJAX API to get a list of videos for a specific page."""
    payload = {
        "pageid": "vi",
        "theloai": cat_info["theloai"],
        "chuyenmuc": cat_info["tieude"],
        "pageindex": page_index,
        "pagesize": 12,
        "mediaid": 0
    }
    
    try:
        response = requests.post(API_URL, headers=get_headers(), json=payload)
        response.raise_for_status()
        
        # The API returns HTML in the 'd' field of the JSON response
        html_content = response.json().get("d", "")
        if not html_content:
            return []
            
        soup = BeautifulSoup(html_content, 'html.parser')
        videos = []
        
        # Parse video items
        for article in soup.find_all("article", class_="media-small-news"):
            link_tag = article.find("a", href=True)
            if link_tag:
                video_url = link_tag["href"]
                if not video_url.startswith("http"):
                    video_url = BASE_URL + video_url
                
                title_tag = article.find("h4", class_="media-tt-news")
                title = title_tag.get_text(strip=True) if title_tag else "Unknown Title"
                
                videos.append({
                    "url": video_url,
                    "title": title
                })
        
        return videos

    except Exception as e:
        print(f"Error fetching video list for page {page_index}: {e}")
        return []

def get_video_source(video_url):
    """Fetches the video page and extracts the direct .mp4 link."""
    try:
        response = requests.get(video_url, headers=get_headers())
        response.raise_for_status()
        
        # Regex to find intVideo('avatar', 'video_file')
        match = re.search(r"intVideo\('[^']+',\s*'([^']+)'\)", response.text)
        if match:
            return match.group(1)
        
        return None
    except Exception as e:
        print(f"Error fetching video source {video_url}: {e}")
        return None

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

# ... imports ...

import hashlib

# ... imports ...

PROCESSED_FILE = "processed_videos.json"
STATE_FILE = "crawler_state.json"

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

def save_crawler_state(category, page):
    state = {
        "last_category": category,
        "last_page": page
    }
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

def main():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        
    processed_videos = load_processed_videos()
    print(f"Loaded {len(processed_videos)} processed videos.")
    
    state = load_crawler_state()
    last_category = state.get("last_category")
    last_page = state.get("last_page", 0)
    
    skip_categories = True if last_category else False

    for cat_name, cat_url in CATEGORIES.items():
        # Resume logic for categories
        if skip_categories:
            if cat_name == last_category:
                skip_categories = False # Found the last category, stop skipping
                print(f"Resuming from category: {cat_name}, page {last_page}")
            else:
                print(f"Skipping category: {cat_name}")
                continue
        
        print(f"\nProcessing Category: {cat_name}")
        cat_info = get_category_info(cat_url)
        if not cat_info:
            continue
            
        print(f"Category Info: {cat_info}")
        
        # Determine start page
        start_page = last_page if cat_name == last_category else 0
        current_page = start_page
        
        while True:
            print(f"  Fetching page {current_page}...")
            videos = get_video_list(cat_info, current_page)
            
            if not videos:
                print("  No more videos found. Moving to next category.")
                break
                
            print(f"  Found {len(videos)} videos.")
            
            for video in videos:
                video_url = video['url']
                video_hash = get_md5(video_url)
                
                # Check if processed
                if video_hash in processed_videos:
                    print(f"    Skipping (Processed): {video['title']}")
                    continue
                    
                # Check for broken links
                if "/old_media/" in video_url:
                    print(f"    Skipping (Old Media): {video['title']}")
                    processed_videos.add(video_hash)
                    continue

                print(f"    Processing: {video['title']}")
                mp4_url = get_video_source(video_url)
                
                if mp4_url:
                    print(f"      Source: {mp4_url}")
                    
                    safe_title = "".join([c for c in video['title'] if c.isalnum() or c in (' ', '-', '_')]).strip()
                    safe_title = safe_title.replace(" ", "_")[:50]
                    
                    if CONFIG["save_audio"]:
                        filename = f"{cat_name}_{safe_title}.{CONFIG['audio_format']}"
                        output_path = os.path.join(OUTPUT_DIR, filename)
                        download_audio_ffmpeg(mp4_url, output_path)
                    
                    # Mark as processed
                    processed_videos.add(video_hash)
                    save_processed_videos(processed_videos)
                    
                    # Random delay between 1 and 3 seconds
                    delay = random.uniform(1, 3)
                    print(f"      Sleeping for {delay:.2f}s...")
                    time.sleep(delay)
                else:
                    print("      Could not find MP4 source.")
            
            # Save state after finishing a page
            save_crawler_state(cat_name, current_page)
            
            # Random delay between pages
            page_delay = random.uniform(2, 5)
            print(f"  Sleeping for {page_delay:.2f}s before next page...")
            time.sleep(page_delay)
            
            current_page += 1
            
        # Reset last_page for next category
        last_page = 0

if __name__ == "__main__":
    main()

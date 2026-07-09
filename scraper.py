import yt_dlp
import time
import sys
import os
import re
import subprocess 

# --- 1. COMMAND-LINE ARGUMENT CHECK ---
if len(sys.argv) < 2:
    print("\n[ERROR] Missing channel URL argument!")
    print("Usage: python scraper.py <YOUTUBE_CHANNEL_URL>")
    print("Example: python scraper.py https://youtube.com/@ericmorris1920\n")
    sys.exit(1)

CHANNEL_URL = sys.argv[1]

# --- 2. DYNAMIC DIRECTORY GENERATION ---
# Extracts the channel handle and sanitizes it for Termux/Android paths
raw_name = CHANNEL_URL.rstrip('/').split('/')[-1].replace('@', '')
safe_channel_name = re.sub(r'[^a-zA-Z0-9_-]', '_', raw_name)

BASE_DIR = f"/storage/3065-3031/experiments/{safe_channel_name}"
ARCHIVE_FILE = f"{BASE_DIR}/archive_ledger.txt"
PLAYLIST_FILE = f"{BASE_DIR}/playlist.txt"

class RateLimitException(Exception):
    pass

class RateLimitLogger:
    def debug(self, msg):
        if not msg.startswith('[debug] '):
            print(msg)

    def warning(self, msg):
        print(msg)
        if 'HTTP Error 429' in msg or 'Too Many Requests' in msg:
            raise RateLimitException("YouTube 429 IP Ban triggered.")

    def error(self, msg):
        print(msg)

ydl_opts = {
    'skip_download': True,
    'writesubtitles': True,
    'writeautomaticsub': True,
    
    # Priority: 1) Original, 2) English, 3) Hindi
    'subtitleslangs': ['.*orig', 'en.*', 'hi.*'], 
    
    'subtitlesformat': 'srt',
    'writethumbnail': False,
    'ignoreerrors': True, 
    
    # --- ULTRA-CONSERVATIVE ANTI-RATE-LIMIT SETTINGS ---
    'sleep_interval': 45,             
    'max_sleep_interval': 120,         
    'sleep_interval_requests': 1,     
    
    'retries': 10,                    
    'fragment_retries': 10,
    'restrictfilenames': True, 
    'download_archive': ARCHIVE_FILE,
    'outtmpl': f'{BASE_DIR}/%(title).100s_[%(id)s].%(ext)s',
    'quiet': False,
    'logger': RateLimitLogger(),
}

def ensure_playlist():
    if os.path.exists(PLAYLIST_FILE) and os.path.getsize(PLAYLIST_FILE) > 0:
        print(f"\n[INIT] Using cached playlist: {PLAYLIST_FILE}")
        return

    print(f"\n[INIT] Fetching all video URLs for channel: {safe_channel_name}...")
    os.makedirs(BASE_DIR, exist_ok=True)
    
    try:
        result = subprocess.run(
            f'yt-dlp --flat-playlist --print "https://www.youtube.com/watch?v=%(id)s" "{CHANNEL_URL}" > "{PLAYLIST_FILE}"',
            shell=True
        )
        if result.returncode != 0:
            print("\n[ERROR] Playlist generation failed!")
            if os.path.exists(PLAYLIST_FILE): os.remove(PLAYLIST_FILE)
            sys.exit(1)
        print("[INIT] Playlist successfully cached!")
    except KeyboardInterrupt:
        if os.path.exists(PLAYLIST_FILE): os.remove(PLAYLIST_FILE)
        sys.exit(1)

def enforce_single_subtitle():
    """
    Scans the folder and groups files by their Video ID. 
    Keeps the highest priority file and permanently deletes the fallbacks.
    Priority: 1) Original, 2) English, 3) Hindi
    """
    print("\n[CLEANUP] Enforcing strict one-subtitle-per-video rule...")
    if not os.path.exists(BASE_DIR):
        return
        
    id_map = {}
    for filename in os.listdir(BASE_DIR):
        if filename.endswith(".srt"):
            match = re.search(r"\[([a-zA-Z0-9_-]{11})\]", filename)
            if match:
                vid_id = match.group(1)
                if vid_id not in id_map:
                    id_map[vid_id] = []
                id_map[vid_id].append(filename)
                
    cleanup_count = 0
    for vid_id, files in id_map.items():
        if len(files) > 1:
            def get_rank(fname):
                fname_lower = fname.lower()
                if 'orig' in fname_lower: return 1
                if '.en' in fname_lower: return 2
                if '.hi' in fname_lower: return 3
                return 4 
                
            files.sort(key=get_rank)
            
            for duplicate in files[1:]:
                try:
                    os.remove(os.path.join(BASE_DIR, duplicate))
                    cleanup_count += 1
                except:
                    pass
                    
    if cleanup_count > 0:
        print(f"[CLEANUP] Swept and deleted {cleanup_count} fallback subtitles.")
    else:
        print("[CLEANUP] No duplicates found.")

def strict_archive_sync():
    print("\n[VERIFICATION] Running strict filename-to-archive sync...")
    os.makedirs(BASE_DIR, exist_ok=True)
    actual_ids = set()
    
    if os.path.exists(BASE_DIR):
        for filename in os.listdir(BASE_DIR):
            if filename.endswith(".srt"):
                match = re.search(r"\[([a-zA-Z0-9_-]{11})\]", filename)
                if match:
                    actual_ids.add(match.group(1))
                    
    with open(ARCHIVE_FILE, 'w') as f:
        for vid_id in sorted(actual_ids):
            f.write(f"youtube {vid_id}\n")
            
    print(f"[VERIFICATION] Archive rebuilt. {len(actual_ids)} videos strictly verified on disk.\n")

def start_scraping():
    while True:
        ensure_playlist()
        enforce_single_subtitle() 
        strict_archive_sync()
        
        print(f"--- Starting Extraction Engine for {safe_channel_name} ---")
        
        with open(PLAYLIST_FILE, 'r') as f:
            video_urls = [line.strip() for line in f if line.strip()]
            
        print(f"[INIT] Loaded {len(video_urls)} URLs from the cache to process.")
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download(video_urls)
            
            enforce_single_subtitle()
            
            print("\n==========================================")
            print(f"SUCCESS: All available subtitles for {safe_channel_name} downloaded!")
            print("==========================================")
            break 

        except RateLimitException as e:
            print("\n==========================================")
            print(f"INTERCEPTOR TRIGGERED: {e}")
            print("Termux is now pausing for 15 minutes to let the ban clear...")
            print("==========================================")
            time.sleep(900) 
            
        except Exception as e:
            print(f"\nUNEXPECTED ERROR: {e}. Retrying in 60 seconds...")
            time.sleep(60)

if __name__ == "__main__":
    try:
        start_scraping()
    except KeyboardInterrupt:
        print("\nScript manually stopped by user.")
        sys.exit(0)
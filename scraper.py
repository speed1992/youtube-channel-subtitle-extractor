import yt_dlp
import time
import sys
import os
import re
import subprocess 

# Target channel and paths
CHANNEL_URL = "https://youtube.com/@theewerchillpill"
BASE_DIR = "/storage/3065-3031/experiments/chillpill_subtitles"
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
    'subtitleslangs': ['en'],
    'subtitlesformat': 'srt',
    'writethumbnail': False,
    'ignoreerrors': True, 
    
    # --- ULTRA-CONSERVATIVE ANTI-RATE-LIMIT SETTINGS ---
    'sleep_interval': 45,             
    'max_sleep_interval': 120,         
    'sleep_interval_requests': 1,     
    'sleep_interval_subtitles': 15,    
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

    print("\n[INIT] Local playlist not found or is empty. Fetching all video URLs...")
    os.makedirs(BASE_DIR, exist_ok=True)
    
    try:
        result = subprocess.run(
            f'yt-dlp --flat-playlist --print "https://www.youtube.com/watch?v=%(id)s" "{CHANNEL_URL}" > "{PLAYLIST_FILE}"',
            shell=True
        )
        
        if result.returncode != 0:
            print("\n[ERROR] Playlist generation was interrupted or failed!")
            if os.path.exists(PLAYLIST_FILE):
                os.remove(PLAYLIST_FILE)
            sys.exit(1)
            
        print("[INIT] Playlist successfully cached to disk!")
        
    except KeyboardInterrupt:
        print("\n[ERROR] Interrupted by user! Cleaning up...")
        if os.path.exists(PLAYLIST_FILE):
            os.remove(PLAYLIST_FILE)
        sys.exit(1)

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
            
    print(f"[VERIFICATION] Archive rebuilt. {len(actual_ids)} files strictly verified on disk.\n")

def start_scraping():
    while True:
        ensure_playlist()
        strict_archive_sync()
        
        print("--- Starting Extraction Engine ---")
        
        with open(PLAYLIST_FILE, 'r') as f:
            video_urls = [line.strip() for line in f if line.strip()]
            
        print(f"[INIT] Loaded {len(video_urls)} URLs from the cache to process.")
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download(video_urls)
            
            print("\n==========================================")
            print("SUCCESS: All available subtitles downloaded!")
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
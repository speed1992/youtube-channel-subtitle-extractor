import yt_dlp
import time
import sys
import os
import re
import subprocess 

if len(sys.argv) < 2:
    print("\n[ERROR] Missing channel URL arguments!")
    print("Usage: python scraper.py <URL1> <URL2> <URL3> ...")
    print("Example: python scraper.py https://youtube.com/@channel1 https://youtube.com/@channel2\n")
    sys.exit(1)

# Grabs all URLs passed in the command line
CHANNEL_URLS = sys.argv[1:]

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

def process_channel(channel_url, current_idx, total_channels):
    raw_name = channel_url.rstrip('/').split('/')[-1].replace('@', '')
    safe_channel_name = re.sub(r'[^a-zA-Z0-9_-]', '_', raw_name)

    # --- UPDATED PATHS ---
    BASE = "/storage/emulated/0/experiments/ytoutput"
    BASE_DIR = f"{BASE}/{safe_channel_name}"
    
    META = "metadata"
    ARCHIVE_FILE = f"{BASE}/{META}/{safe_channel_name}/archive_ledger.txt"
    PLAYLIST_FILE = f"{BASE}/{META}/{safe_channel_name}/playlist.txt"
    
    print(f"\n===========================================================")
    print(f" [QUEUE] Starting Channel {current_idx} of {total_channels}: {safe_channel_name}")
    print(f"===========================================================\n")

    ydl_opts = {
        'skip_download': True,
        'writesubtitles': True,
        'writeautomaticsub': True,
        
        # --- ANY ENGLISH & ORIGINAL CONFIG ---
        'subtitleslangs': ['.*orig', 'en.*'], 
        
        'subtitlesformat': 'srt',
        'writethumbnail': False,
        'ignoreerrors': True, 
        
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
        os.makedirs(os.path.dirname(PLAYLIST_FILE), exist_ok=True)
        
        try:
            result = subprocess.run(
                f'yt-dlp --flat-playlist --print "https://www.youtube.com/watch?v=%(id)s" "{channel_url}" > "{PLAYLIST_FILE}"',
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
        Keeps the subtitle with the largest file size. 
        If sizes are equal, falls back to the priority ranking system.
        """
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
                
                def get_sort_key(fname):
                    filepath = os.path.join(BASE_DIR, fname)
                    file_size = os.path.getsize(filepath) if os.path.exists(filepath) else 0
                    
                    fname_lower = fname.lower()
                    
                    if '.en-orig' in fname_lower: rank = 1
                    elif 'orig' in fname_lower: rank = 2
                    elif fname_lower.endswith('.en.srt'): rank = 3
                    elif '.en' in fname_lower: rank = 4
                    else: rank = 5
                    
                    return (-file_size, rank)
                    
                files.sort(key=get_sort_key)
                
                for duplicate in files[1:]:
                    try:
                        os.remove(os.path.join(BASE_DIR, duplicate))
                        cleanup_count += 1
                    except:
                        pass
                        
        if cleanup_count > 0:
            print(f"[CLEANUP] Swept and deleted {cleanup_count} fallback subtitles for {safe_channel_name}.")

    def strict_archive_sync():
        os.makedirs(BASE_DIR, exist_ok=True)
        os.makedirs(os.path.dirname(ARCHIVE_FILE), exist_ok=True)
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

    # The 429 Interceptor Loop strictly isolates each channel
    while True:
        ensure_playlist()
        enforce_single_subtitle() 
        strict_archive_sync()
        
        print(f"--- Starting Extraction Engine for {safe_channel_name} ---")
        
        with open(PLAYLIST_FILE, 'r') as f:
            video_urls = [line.strip() for line in f if line.strip()]
            
        total_videos = len(video_urls)
        print(f"[INIT] Loaded {total_videos} URLs from the cache to process.")
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                for idx, url in enumerate(video_urls, start=1):
                    ydl.download([url])
                    
                    percent = (idx / total_videos) * 100
                    print(f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                    print(f" [{safe_channel_name}] PROGRESS: {idx} / {total_videos} Videos ({percent:.2f}%) ")
                    print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
            
            enforce_single_subtitle()
            
            print("\n==========================================")
            print(f"SUCCESS: All available subtitles for {safe_channel_name} downloaded!")
            print("==========================================\n")
            break 

        except RateLimitException as e:
            print("\n==========================================")
            print(f"INTERCEPTOR TRIGGERED ON {safe_channel_name}: {e}")
            print("Termux is now pausing for 15 minutes to let the ban clear...")
            print("==========================================")
            time.sleep(900) 
            
        except Exception as e:
            print(f"\nUNEXPECTED ERROR ON {safe_channel_name}: {e}. Retrying in 60 seconds...")
            time.sleep(60)

if __name__ == "__main__":
    try:
        total_queued = len(CHANNEL_URLS)
        for i, url in enumerate(CHANNEL_URLS, start=1):
            process_channel(url, i, total_queued)
            
        print("\n==========================================")
        print("ALL CHANNELS IN QUEUE SUCCESSFULLY PROCESSED!")
        print("==========================================\n")
        
    except KeyboardInterrupt:
        print("\nScript manually stopped by user.")
        sys.exit(0)

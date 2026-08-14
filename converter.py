import os
import re
import sys
import logging
import argparse
from pathlib import Path

# Setup logging for clear feedback
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%H:%M:%S'
)

def clean_srt_text(text: str) -> str:
    """Removes timecodes, sequence numbers, and tags from SRT content."""
    cleaned_lines = []
    lines = text.splitlines()
    
    for line in lines:
        line = line.strip()
        if not line or line.isdigit():
            continue
        # Skip timecodes
        if re.match(r"^\d{1,2}:\d{2}:\d{2}[,.]\d{2,3}\s*-->\s*\d{1,2}:\d{2}:\d{2}[,.]\d{2,3}", line):
            continue
        # Strip HTML and ASS tags
        line = re.sub(r"<[^>]+>", "", line)
        line = re.sub(r"\{[^}]+\}", "", line)
        
        if line.strip():
            cleaned_lines.append(line)
            
    return "\n".join(cleaned_lines)

def process_file(srt_path: Path, output_dir: Path):
    """Processes a single SRT file with ultra-conservative read-only rules."""
    
    # 1. PARANOIA CHECK: Ensure we are only reading files, not symlinks or directories
    if not srt_path.is_file() or srt_path.is_symlink():
        logging.warning(f"Skipping {srt_path.name}: Not a standard file or is a symlink.")
        return None

    txt_path = output_dir / f"{srt_path.stem}.txt"
    temp_txt_path = output_dir / f"{srt_path.stem}.txt.tmp"
    
    content = None
    encodings = ['utf-8-sig', 'utf-8', 'latin-1', 'cp1252']
    
    # STRICT READ-ONLY MODE ('r'). 
    for enc in encodings:
        try:
            with open(srt_path, 'r', encoding=enc) as f:
                content = f.read()
            break
        except UnicodeDecodeError:
            continue
        except Exception as e:
            logging.error(f"Read access failed on {srt_path.name}: {e}")
            return None
            
    if content is None:
        logging.error(f"Failed to read {srt_path.name}: Unknown encoding.")
        return None

    cleaned_text = clean_srt_text(content)

    try:
        # Atomic Write Process strictly inside output_dir
        with open(temp_txt_path, 'w', encoding='utf-8') as f:
            f.write(cleaned_text)
            f.flush()
            os.fsync(f.fileno()) 
            
        temp_txt_path.replace(txt_path)
        return txt_path
        
    except Exception as e:
        logging.error(f"Failed to write output for {txt_path.name}: {e}")
        if temp_txt_path.exists():
            try:
                temp_txt_path.unlink()
            except:
                pass 
        return None

def resolve_input_target(input_arg: str, base_input_dir: Path) -> Path:
    """Determines if the input is a URL or a direct path and resolves the target folder."""
    if input_arg.startswith("http://") or input_arg.startswith("https://"):
        raw_name = input_arg.rstrip('/').split('/')[-1]
        clean_name = raw_name[1:] if raw_name.startswith('@') else raw_name
        
        dir_with_at = base_input_dir / f"@{clean_name}"
        dir_without_at = base_input_dir / clean_name
        
        if dir_with_at.is_dir():
            return dir_with_at.resolve()
        return dir_without_at.resolve()
    else:
        return Path(input_arg).resolve()

def process_channel(target_dir: Path, base_output_dir: Path, base_combined_dir: Path):
    """Handles the conversion and combining logic for a single channel. Returns combined file path if successful."""
    channel_name = target_dir.name
    
    if not target_dir.is_dir():
        logging.error(f"Skipping '{channel_name}': Input directory not found at {target_dir}")
        return None
        
    final_output_dir = base_output_dir / channel_name
    final_combined_dir = base_combined_dir / channel_name
    
    # 2. PARANOIA CHECK: Prevent Input/Output Directory Overlap
    if target_dir in [final_output_dir, final_combined_dir]:
        logging.critical(f"ABORTING {channel_name}: Output directory cannot be the same as production input directory.")
        return None
        
    try:
        final_output_dir.mkdir(parents=True, exist_ok=True)
        final_combined_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        logging.error(f"Permission denied creating directories for '{channel_name}'. Check Termux permissions.")
        return None
        
    srt_files = list(target_dir.glob('*.srt'))
    
    if not srt_files:
        logging.warning(f"Skipping '{channel_name}': No .srt files found.")
        return None
        
    logging.info(f"--- Processing {channel_name} ({len(srt_files)} files) ---")
    
    successful_txt_files = []
    
    for srt_file in srt_files:
        txt_path = process_file(srt_file, final_output_dir)
        if txt_path:
            successful_txt_files.append(txt_path)
            
    logging.info(f"Successfully extracted {len(successful_txt_files)} files for {channel_name}.")
    
    # Combine the processed files safely for this specific channel
    if successful_txt_files:
        combined_file_path = final_combined_dir / f"combined-{channel_name}.txt"
        temp_combined_path = final_combined_dir / f"combined-{channel_name}.txt.tmp"
        
        try:
            with open(temp_combined_path, 'w', encoding='utf-8') as outfile:
                for txt_path in successful_txt_files:
                    with open(txt_path, 'r', encoding='utf-8') as infile:
                        outfile.write(f"\n\n--- {txt_path.name} ---\n\n")
                        outfile.write(infile.read())
                        
            temp_combined_path.replace(combined_file_path)
            logging.info(f"Channel Master file created: {combined_file_path}\n")
            return combined_file_path # Return the path so we can stitch it later
            
        except Exception as e:
            logging.error(f"Failed to create combined file for {channel_name}: {e}\n")
            if temp_combined_path.exists():
                try:
                    temp_combined_path.unlink()
                except:
                    pass
    
    return None

def main():
    parser = argparse.ArgumentParser(description="Ultra-safe SRT extractor with Grand Master file creation.")
    parser.add_argument(
        "inputs", 
        nargs="+", 
        help="One or more folder paths OR YouTube channel URLs"
    )
    parser.add_argument(
        "-i", "--input-base", 
        default="/storage/emulated/0/experiments/ytoutput/", 
        help="Base folder where yt-dlp saves channel downloads"
    )
    parser.add_argument(
        "-o", "--output", 
        default="/storage/emulated/0/experiments/output/", 
        help="Base folder to save individual .txt files"
    )
    parser.add_argument(
        "-c", "--combined", 
        default="/storage/emulated/0/experiments/combined/", 
        help="Base folder to save the final combined .txt file"
    )
    
    args = parser.parse_args()
    
    base_input_dir = Path(args.input_base).resolve()
    base_output_dir = Path(args.output).resolve()
    base_combined_dir = Path(args.combined).resolve()
    
    # Keep a list of all successfully generated channel master files
    all_channel_master_files = []
    
    for input_arg in args.inputs:
        target_dir = resolve_input_target(input_arg, base_input_dir)
        channel_master_path = process_channel(target_dir, base_output_dir, base_combined_dir)
        
        if channel_master_path:
            all_channel_master_files.append(channel_master_path)
            
    # -------------------------------------------------------------
    # THE FINAL STEP: Combine all channel master files together
    # -------------------------------------------------------------
    if all_channel_master_files:
        logging.info(f"--- Generating Final Grand Master File ({len(all_channel_master_files)} channels) ---")
        
        grand_master_path = base_combined_dir / "final_master_combined.txt"
        temp_grand_master_path = base_combined_dir / "final_master_combined.txt.tmp"
        
        try:
            # Ensure the base combined directory exists just in case
            base_combined_dir.mkdir(parents=True, exist_ok=True)
            
            with open(temp_grand_master_path, 'w', encoding='utf-8') as outfile:
                for channel_file in all_channel_master_files:
                    
                    # Extract the channel name from the file path for a clean header
                    channel_name = channel_file.parent.name
                    
                    with open(channel_file, 'r', encoding='utf-8') as infile:
                        # Add a heavy visual divider between channels
                        outfile.write(f"\n\n{'='*60}\n")
                        outfile.write(f"CHANNEL: {channel_name}\n")
                        outfile.write(f"{'='*60}\n\n")
                        
                        outfile.write(infile.read())
                        
            # Atomic swap for the grand master file
            temp_grand_master_path.replace(grand_master_path)
            logging.info(f"SUCCESS! Grand Master file safely created at: {grand_master_path}")
            
        except Exception as e:
            logging.error(f"Failed to create Grand Master file: {e}")
            if temp_grand_master_path.exists():
                try:
                    temp_grand_master_path.unlink()
                except:
                    pass
    else:
        logging.warning("No channels were successfully converted. Grand Master file skipped.")
        
    logging.info("All tasks completed securely.")

if __name__ == '__main__':
    main()

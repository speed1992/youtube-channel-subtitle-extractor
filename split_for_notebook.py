import os
import sys
import glob

def split_text_file(filepath, output_dir, max_words=499995):
    base_name = os.path.splitext(os.path.basename(filepath))[0]
    part_num = 1
    current_words = 0
    
    print(f"\nProcessing: '{base_name}.txt'")

    try:
        # Create output file path in the new dedicated output directory
        out_filename = os.path.join(output_dir, f"{base_name}_part_{part_num:03d}.txt")
        out_file = open(out_filename, "w", encoding="utf-8", errors="replace")
        
        with open(filepath, "r", encoding="utf-8", errors="replace") as in_file:
            for line in in_file:
                words_in_line = len(line.split())
                
                # If the line pushes us over the limit, start a new file
                if current_words + words_in_line > max_words and current_words > 0:
                    out_file.close()
                    print(f"  ✓ Saved part {part_num:03d} ({current_words:,} words)")
                    
                    part_num += 1
                    current_words = 0
                    
                    out_filename = os.path.join(output_dir, f"{base_name}_part_{part_num:03d}.txt")
                    out_file = open(out_filename, "w", encoding="utf-8", errors="replace")
                
                out_file.write(line)
                current_words += words_in_line
                
        out_file.close()
        print(f"  ✓ Saved part {part_num:03d} ({current_words:,} words)")
        
    except Exception as e:
        print(f"  ! Critical Error processing {base_name}: {e}")
        if 'out_file' in locals() and not out_file.closed:
            out_file.close()

def process_directory(input_dir, output_dir):
    if not os.path.exists(input_dir):
        print(f"Error: The input directory '{input_dir}' does not exist.")
        print("Did you run 'termux-setup-storage'?")
        return

    # Ensure the explicit output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Find all .txt files in the input folder
    search_pattern = os.path.join(input_dir, "*.txt")
    txt_files = glob.glob(search_pattern)
    
    if not txt_files:
        print(f"No .txt files found in '{input_dir}'.")
        return

    print(f"Found {len(txt_files)} text file(s) in {input_dir}")
    print(f"Saving safely sized chunks to: {output_dir}")

    # Process each file
    for filepath in txt_files:
        split_text_file(filepath, output_dir)
        
    print("\nAll done! Files are perfectly sized and safely saved in the output folder.")

if __name__ == "__main__":
    # Hardcoded paths based on your requirement
    target_input_dir = "/storage/emulated/0/experiments/combined/"
    target_output_dir = "/storage/emulated/0/experiments/split-output/"
    
    process_directory(target_input_dir, target_output_dir)

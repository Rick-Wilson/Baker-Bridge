#!/usr/bin/env python3
import os
import re
import shutil
import glob

# Get the current working directory as the base path
base_dir = os.getcwd()

# Define the source directories and destination package directory relative to the base directory
pbn_dir = os.path.join(base_dir, "pbns")
pdf_dir = os.path.join(base_dir, "pdfs")
# Output dir: BB_PACKAGE_DIR (env) overrides the default orphaned ../Package so the build
# can target the new bridge-classroom/ contracted-files folder (issue #21, Phase B).
package_dir = os.environ.get("BB_PACKAGE_DIR") or os.path.join(base_dir, "../Package")

# Debug: show the directories being used
print(f"Base directory: {base_dir}")
print(f"PBN directory: {pbn_dir}")
print(f"PDF directory: {pdf_dir}")
print(f"Package directory: {package_dir}")

# Check if input directories exist
if not os.path.isdir(pbn_dir):
    print(f"Warning: Input directory {pbn_dir} does not exist. Please check the path.")
if not os.path.isdir(pdf_dir):
    print(f"Warning: Input directory {pdf_dir} does not exist. Please check the path.")

# Ensure the package directory exists
os.makedirs(package_dir, exist_ok=True)

# Function to copy files preserving the filename, with debug output
def copy_files(src_pattern, dest_dir):
    # Use recursive globbing by passing recursive=True
    files = glob.glob(src_pattern, recursive=True)
    print(f"Found {len(files)} files for pattern {src_pattern}")
    for filepath in files:
        filename = os.path.basename(filepath)
        dest_path = os.path.join(dest_dir, filename)
        print(f"Copying {filepath} to {dest_path}")
        shutil.copy2(filepath, dest_path)

# Function to copy PDF files with _Intro appended before the extension, with debug output
def copy_pdf_with_intro(src_pattern, dest_dir):
    files = glob.glob(src_pattern, recursive=True)
    print(f"Found {len(files)} files for pattern {src_pattern}")
    for filepath in files:
        basename, ext = os.path.splitext(os.path.basename(filepath))
        new_filename = f"{basename}_Intro{ext}"
        dest_path = os.path.join(dest_dir, new_filename)
        print(f"Copying {filepath} to {dest_path}")
        shutil.copy2(filepath, dest_path)

# Copy all .pbn files from the pbns directory (including subfolders) to the package directory.
# pbns/ holds no PDFs: the lesson-level analysis PDF used to be rendered here, from PBNs that
# still carried the bridge-classroom control tags, and nothing downstream consumed it. The
# clean whole-lesson PDF is the one package.sh renders into Rotations' All/ folder.
copy_files(os.path.join(pbn_dir, "**", "*.pbn"), package_dir)

# Copy all .pdf files from the pdfs directory (including subfolders) to the package directory, appending _Intro to the filename
copy_pdf_with_intro(os.path.join(pdf_dir, "**", "*.pdf"), package_dir)

# Overlay curated PBN files (board-by-board merge, curated wins on collisions)
def parse_pbn_boards(filepath):
    """Parse a PBN file into (preamble, {board_number: board_text}).

    The preamble is everything before the first [Event tag — e.g. the
    %Creator / %Created / %HRTitleEvent / %bridge-context comment block.
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    first_event = content.find('[Event "')
    preamble = content[:first_event] if first_event > 0 else ''
    boards = {}
    parts = re.split(r'(?=\[Event ")', content)
    for part in parts:
        part = part.strip()
        if not part:
            continue
        match = re.search(r'\[Board "(\d+)"\]', part)
        if match:
            boards[int(match.group(1))] = part
    return preamble, boards

curated_dir = os.path.join(base_dir, "../Curated")
if os.path.isdir(curated_dir):
    for curated_file in sorted(glob.glob(os.path.join(curated_dir, "*.pbn"))):
        filename = os.path.basename(curated_file)
        package_file = os.path.join(package_dir, filename)
        if os.path.exists(package_file):
            pkg_preamble, pkg_boards = parse_pbn_boards(package_file)
            _, cur_boards = parse_pbn_boards(curated_file)
            # Curated wins, but preserve filled Deal from generated PBN
            # when curated board has unfilled hands (...)
            for num, cur_text in cur_boards.items():
                if '...' in cur_text and num in pkg_boards:
                    deal_match = re.search(r'\[Deal "[^"]*"\]', pkg_boards[num])
                    if deal_match and '...' not in deal_match.group():
                        cur_text = re.sub(r'\[Deal "[^"]*"\]', deal_match.group(), cur_text)
                        cur_boards[num] = cur_text
            pkg_boards.update(cur_boards)  # Curated wins (with filled deals)
            with open(package_file, 'w', encoding='utf-8') as f:
                if pkg_preamble:
                    f.write(pkg_preamble)
                for num in sorted(pkg_boards.keys()):
                    f.write(pkg_boards[num] + '\n\n')
            print(f"Merged {len(cur_boards)} curated boards into {filename}"
                  f" ({len(pkg_boards)} total boards)")
        else:
            shutil.copy2(curated_file, package_file)
            print(f"Copied curated file {filename} to Package")
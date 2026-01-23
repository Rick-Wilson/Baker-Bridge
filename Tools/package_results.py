#!/usr/bin/env python3
import os
import shutil
import glob

# Get the current working directory as the base path
base_dir = os.getcwd()

# Define the source directories and destination package directory relative to the base directory
pbn_dir = os.path.join(base_dir, "pbns")
pdf_dir = os.path.join(base_dir, "pdfs")
package_dir = os.path.join(base_dir, "../Package")

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

# Copy all .pbn and .pdf files from the pbns directory (including subfolders) to the package directory
copy_files(os.path.join(pbn_dir, "**", "*.pbn"), package_dir)
copy_files(os.path.join(pbn_dir, "**", "*.pdf"), package_dir)

# Copy all .pdf files from the pdfs directory (including subfolders) to the package directory, appending _Intro to the filename
copy_pdf_with_intro(os.path.join(pdf_dir, "**", "*.pdf"), package_dir)
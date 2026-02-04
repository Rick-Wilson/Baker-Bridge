#!/usr/bin/env python3
import os

def process_file(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    new_lines = []
    i = 0
    removed_any = False

    while i < len(lines):
        # Check if there are at least three lines left
        if i <= len(lines) - 3:
            # Check pattern: blank line, then line starting with "<!-- Mirrored from", then line starting with "<!-- Added by HTTrack"
            if lines[i].strip() == "" and \
               lines[i+1].lstrip().startswith("<!-- Mirrored from") and \
               lines[i+2].lstrip().startswith("<!-- Added by HTTrack"):
                # Skip these three lines
                removed_any = True
                i += 3
                continue
        # Otherwise, keep the current line
        new_lines.append(lines[i])
        i += 1

    # Only write back if changes were made.
    if removed_any:
        with open(filepath, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        print(f"Updated: {filepath}")
    else:
        print(f"No changes: {filepath}")

def main():
    # Walk through current folder and subfolders
    for root, dirs, files in os.walk(os.getcwd()):
        for file in files:
            if file.lower().endswith(".html"):
                filepath = os.path.join(root, file)
                process_file(filepath)

if __name__ == "__main__":
    main()
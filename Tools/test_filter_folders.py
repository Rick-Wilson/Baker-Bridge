import os
import sys
import fnmatch

def find_leaf_folders(base_dir: str, filter_str: str) -> list:
    matching_folders = []

    is_exclusion = filter_str.startswith('-')
    pattern = filter_str[1:] if is_exclusion else filter_str

    # Normalize to match everything if pattern is empty or "*"
    if pattern.strip() == "":
        pattern = "*"
    elif '*' not in pattern:
        pattern = f'*{pattern}*'  # match as substring

    pattern = pattern.lower()

    for root, dirs, files in os.walk(base_dir):
        dirs.sort()
        if not dirs:  # it's a leaf
            folder_name = os.path.basename(root)
            match = fnmatch.fnmatch(folder_name.lower(), pattern)
            if (not is_exclusion and match) or (is_exclusion and not match):
                # Return path relative to base_dir
                relative_path = os.path.relpath(root, base_dir)
                matching_folders.append(relative_path)

    return matching_folders

def main():
    if len(sys.argv) != 2:
        print("Usage: python test_filter_folders.py \"<filter>\"")
        print("Tip: use quotes around '*' to prevent shell expansion.")
        sys.exit(1)

    base_dir = os.path.join(os.getcwd(), "Presentation")
    filter_str = sys.argv[1]
    if not os.path.isdir(base_dir):
        print(f"Error: {base_dir} not found.")
        sys.exit(2)

    results = find_leaf_folders(base_dir, filter_str)
    print("\n".join(results))

if __name__ == "__main__":
    main()
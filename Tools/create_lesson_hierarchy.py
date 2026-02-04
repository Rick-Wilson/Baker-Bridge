#!/usr/bin/env python3
import os
import csv
import shutil

def main():
    # Get the current folder
    current_dir = os.getcwd()
    
    # Path to the titles.csv file in /Original Material/Package
    csv_path = os.path.join(current_dir, "Original Material", "Package", "titles.csv")
    
    # Open and read the CSV file, and store rows with non-blank Titles
    rows = []
    with open(csv_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            title = (row.get("Title") or "").strip()
            if title:  # Only include rows with a non-blank Title
                rows.append(row)
    
    # Sort rows by Title
    rows.sort(key=lambda r: (r.get("Title") or "").strip())

    # Process each row in order of sorted Title
    for row in rows:
        subfolder_name = (row.get("Subfolder") or "").strip()
        title = (row.get("Title") or "").strip()
        
        # Create the main folder for this title in the current directory
        title_dir = os.path.join(current_dir, title)
        os.makedirs(title_dir, exist_ok=True)
        
        # Create subfolders: "All", "4-Board Sets", and "5-Board Sets" within the title folder
        all_dir = os.path.join(title_dir, "All")
        four_board_dir = os.path.join(title_dir, "4-Board Sets")
        five_board_dir = os.path.join(title_dir, "5-Board Sets")
        os.makedirs(all_dir, exist_ok=True)
        os.makedirs(four_board_dir, exist_ok=True)
        os.makedirs(five_board_dir, exist_ok=True)
        
        # Define the source directory for the original files
        source_dir = os.path.join(current_dir, "Original Material", "Package")
        
        # Copy {subfolder}_Intro.pdf to the title folder if it exists
        intro_filename = f"{subfolder_name}_Intro.pdf"
        src_intro = os.path.join(source_dir, intro_filename)
        dst_intro = os.path.join(title_dir, intro_filename)
        if os.path.exists(src_intro):
            shutil.copy(src_intro, dst_intro)
        else:
            print(f"Notice: {src_intro} does not exist. Skipping Intro file.")
        
        # Copy {subfolder}.pdf and {subfolder}.pbn to the "All" subfolder
        pdf_filename = f"{subfolder_name}.pdf"
        pbn_filename = f"{subfolder_name}.pbn"
        
        src_pdf = os.path.join(source_dir, pdf_filename)
        dst_pdf = os.path.join(all_dir, pdf_filename)
        if os.path.exists(src_pdf):
            shutil.copy(src_pdf, dst_pdf)
        else:
            print(f"Warning: {src_pdf} does not exist.")
        
        src_pbn = os.path.join(source_dir, pbn_filename)
        dst_pbn = os.path.join(all_dir, pbn_filename)
        if os.path.exists(src_pbn):
            shutil.copy(src_pbn, dst_pbn)
        else:
            print(f"Warning: {src_pbn} does not exist.")

if __name__ == "__main__":
    main()
import os
import csv
import sys
import datetime

VERSION = "1.00"

"""
CSV to PBN Converter Script

Requirements:
- The script converts a CSV file into multiple PBN files.
- Takes three parameters:
  1. CSV filename (required)
  2. Optional header filename
  3. Optional source filename
- PBN files are created in a '/pbns' subfolder.
- If the 'Subfolder' field contains slashes, they indicate further subfolders.
  - Example: 'Bidpractice/Set1' creates 'pbns/Bidpractice' and names the file 'Set1.pbn'.
- If a header file is provided, its contents are added at the start of each PBN file.
- Metadata comments are added to each PBN file:
  - "%Creator: CSVtoPBN Version X.XX"
  - "%Created <creation date and time>"
  - "%sourcefilename <input filename>"
- The 'Analysis' field is enclosed in {} and processed separately:
  - Converts '!S', '!H', '!D', '!C' to '\\S', '\\H', '\\D', '\\C'.
  - Splits on '\\n' occurrences for proper formatting.
- Multiple rows with the same subfolder should be written to the same PBN file.
  - A new PBN file is created only when the subfolder changes.
- The 'Dealer' and 'Declarer' fields are abbreviated to their first letters (e.g., 'North' → 'N').
- The 'DealNumber' field is renamed to 'Board'.
"""

# Function to load optional header
def load_header(header_filename):
    if header_filename and os.path.exists(header_filename):
        with open(header_filename, 'r', encoding='utf-8') as f:
            return f.read()
    return ""

# Function to process analysis field
def process_analysis(analysis):
    if analysis:
        analysis = analysis.replace('!S', '\\S').replace('!H', '\\H')\
                           .replace('!D', '\\D').replace('!C', '\\C')
        analysis = "\\n".join(analysis.split("\\n"))  # Ensure proper newline conversion
        return "{" + analysis + "}"
    return ""

# Function to abbreviate Dealer and Declarer fields
def abbreviate_position(value):
    position_map = {"North": "N", "East": "E", "South": "S", "West": "W"}
    return position_map.get(value, value)

# Function to write PBN file
def write_pbn(file_path, content):
    directory = os.path.dirname(file_path)
    os.makedirs(directory, exist_ok=True)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

# Main function to process CSV
def convert_csv_to_pbn(csv_filename, header_filename=None, source_filename=None):
    start_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    source_file = os.path.basename(csv_filename)
    header_content = load_header(header_filename)
    
    with open(csv_filename, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        
        current_subfolder = None
        pbn_content = []
        file_path = ""
        
        for row in reader:
            subfolder = row.get("Subfolder", "default").strip()
            analysis = process_analysis(row.get("Analysis", ""))
            
            if "/" in subfolder:
                subfolder_path, filename = os.path.split(subfolder)
            else:
                subfolder_path, filename = "", subfolder
            
            new_file_path = os.path.join("pbns", subfolder_path, f"{filename}.pbn")
            
            # If the subfolder changes, write the previous PBN file and start a new one
            if subfolder != current_subfolder:
                if current_subfolder is not None:
                    write_pbn(file_path, '\\n'.join(pbn_content))
                
                # Start a new PBN file
                pbn_content = []
                file_path = new_file_path
                current_subfolder = subfolder
                
                # Add optional header
                if header_content:
                    pbn_content.append(header_content.strip())
                    pbn_content.append("")  # Blank line after header
                
                # Add script metadata
                pbn_content.append(f"%Creator: CSVtoPBN Version {VERSION}")
                pbn_content.append(f"%Created {start_time}")
                pbn_content.append(f"%sourcefilename {source_file}")
                
            # Add row data
            for key, value in row.items():
                if key:
                    if key == "DealNumber":
                        key = "Board"  # Rename DealNumber to Board
                    if key in ["Dealer", "Declarer"]:
                        value = abbreviate_position(value)  # Abbreviate Dealer and Declarer
                    if key != "Analysis" and value:
                        pbn_content.append(f"[{key} \"{value.strip()}\"]")
            
            # Append analysis at the end
            if analysis:
                pbn_content.append(analysis)
            
        # Write the last PBN file
        if current_subfolder is not None:
            write_pbn(file_path, '\\n'.join(pbn_content))
    
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python script.py <csv_filename> [header_filename] [source_filename]")
        sys.exit(1)
    
    csv_filename = sys.argv[1]
    header_filename = sys.argv[2] if len(sys.argv) > 2 else None
    source_filename = sys.argv[3] if len(sys.argv) > 3 else None
    
    convert_csv_to_pbn(csv_filename, header_filename, source_filename)
    print("Conversion complete! PBN files are in the 'pbns' folder.")

import os
import csv
import sys
import datetime
import re

VERSION = "1.01"

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
- The 'Board', 'Dealer', 'Declarer', and 'Contract' fields are included in each PBN file.
- The 'Auction' row should be modified:
  - It starts with '[Auction "D"]', where 'D' is the dealer initial.
  - The auction follows after the closing bracket.
  - Vertical bars '|' are removed.
  - Whitespace is compressed to single spaces.
- The four hand fields (NorthHand, EastHand, SouthHand, WestHand) are combined into a single '[Deal]' field.
  - Format: '[Deal "W:westhand northhand easthand southhand"]'
  - Each hand is formatted as 'spades.hearts.diamonds.clubs'.
- A '[BCFlags "1f"]' tag is added after the analysis.
- A '[Result ""]' tag is added before the analysis.
- The 'Lead' field is converted to '[Play "P"]card', where 'P' is the position (N/S/E/W) of the opening leader, determined as declarer's left-hand opponent.
"""

# Function to load optional header
def load_header(header_filename):
    if header_filename and os.path.exists(header_filename):
        with open(header_filename, 'r', encoding='utf-8') as f:
            return f.read()
    return ""

# Function to determine initial [show] and [rotate] directives based on student seat
def get_visibility_directives(student, declarer, is_play_instruction=False):
    """
    Determine which hands to show and how to rotate based on lesson type.

    For declarer play (student=S, usually declarer):
        - Show NS (declarer + dummy)
        - Rotate S (South at bottom, default)
        - For play instruction mode: hide auction, show lead

    For opening lead (student=W):
        - Show W (only the leader's hand)
        - Rotate W (West at bottom)

    For third hand play (student=E):
        - Show E (only third hand)
        - Rotate E (East at bottom)

    Returns tuple of (show_directive, rotate_directive, auction_directive, lead_directive)
    """
    auction_directive = None
    lead_directive = None

    if student == "W":
        return "[show W]", "[rotate W]", auction_directive, lead_directive
    elif student == "E":
        return "[show E]", "[rotate E]", auction_directive, lead_directive
    elif student == "N":
        return "[show N]", "[rotate N]", auction_directive, lead_directive
    else:  # Default: student is South (declarer play)
        # For declarer play instruction mode, hide auction and show lead initially
        if is_play_instruction:
            auction_directive = "[AUCTION off]"
            lead_directive = "[SHOW_LEAD]"
        return "[show NS]", None, auction_directive, lead_directive

# Function to inject [show NESW] before final reveal
def inject_final_show(analysis):
    """
    Look for patterns indicating the full deal should be revealed, and inject [show NESW].
    Common patterns:
    - "see the complete deal"
    - "see the hands"
    - "see all four hands"
    """
    reveal_patterns = [
        (r'(Click.*?NEXT.*?to see the complete deal)', r'[show NESW]\n\1'),
        (r'(Click.*?NEXT.*?to see the hands)', r'[show NESW]\n\1'),
        (r'(Click.*?NEXT.*?to see all)', r'[show NESW]\n\1'),
    ]

    for pattern, replacement in reveal_patterns:
        if re.search(pattern, analysis, re.IGNORECASE):
            analysis = re.sub(pattern, replacement, analysis, flags=re.IGNORECASE)
            break

    return analysis

# Function to process analysis field
def process_analysis(analysis, student=None, declarer=None):
    if analysis:
        # Convert suit symbols only when followed by card rank, space, punctuation, 's' (plural), or end of string
        # This prevents "that!South" from becoming "that\South" (spade symbol)
        # Pattern: !S followed by card rank (AKQJT98765432), space, punctuation, 's', or end
        suit_pattern = r'!([SHDC])(?=[AKQJTakqjt98765432s\s\.,;:!\?\)\]\-]|$)'
        analysis = re.sub(suit_pattern, r'\\\1', analysis)
        # Fix lost spacing: add space after ! when followed by capital letter (start of sentence)
        # This handles cases like "that!South" -> "that! South"
        analysis = re.sub(r'!([A-Z])', r'! \1', analysis)
        analysis = analysis.replace('\\n', '\\n\\n')    # double the line breaks - somehow BridgeComposer doesn't handle single breaks well
        analysis = "\n".join(analysis.split("\\n"))  # Ensure proper newline conversion

        # Inject visibility directives
        if student:
            # Check if this is play instruction mode (has [NEXT] tags)
            is_play_instruction = "[NEXT]" in analysis
            show_directive, rotate_directive, auction_directive, lead_directive = get_visibility_directives(student, declarer, is_play_instruction)
            prefix = show_directive
            if rotate_directive:
                prefix += "\n" + rotate_directive
            prefix += "\n"
            analysis = prefix + analysis

            # For play instruction mode, inject [AUCTION off] and [SHOW_LEAD] AFTER the first [NEXT]
            # This shows auction initially, then hides it when user clicks Next
            if auction_directive and lead_directive:
                # Find the first [NEXT] and insert directives after it
                first_next_match = re.search(r'\[NEXT\]', analysis, re.IGNORECASE)
                if first_next_match:
                    insert_pos = first_next_match.end()
                    directives_to_insert = f"\n{auction_directive}\n{lead_directive}"
                    analysis = analysis[:insert_pos] + directives_to_insert + analysis[insert_pos:]

        # Inject final [show NESW] if there's a reveal trigger
        analysis = inject_final_show(analysis)

        return "{" + analysis + "}"
    return ""

# Function to abbreviate Dealer and Declarer fields
def abbreviate_position(value):
    position_map = {"North": "N", "East": "E", "South": "S", "West": "W"}
    return position_map.get(value, value)

# Function to determine opening leader
def determine_lead_position(declarer):
    lead_map = {"N": "E", "E": "S", "S": "W", "W": "N"}  # LHO of declarer
    return lead_map.get(declarer, "")

# Function to process lead field
def process_lead(lead, declarer):
    lead_position = determine_lead_position(declarer)
    if lead_position and lead:
        return f"[Play \"{lead_position}\"]{lead}"
    return ""

# Function to clean and format auction
def process_auction(auction, dealer):
    if auction:
        auction = re.sub(r'\s*\|\s*', ' ', auction)  # Remove vertical bars and extra spaces
        auction = re.sub(r'\s+', ' ', auction).strip()  # Compress whitespace
        return auction
    return ""

# Function to format hand data
def format_hand(hand):
    return hand.replace(" ", "").replace("S:", "").replace("H:", ".").replace("D:", ".").replace("C:", ".")

# Function to create Deal field
def create_deal_field(north, east, south, west):
    return f"[Deal \"W:{format_hand(west)} {format_hand(north)} {format_hand(east)} {format_hand(south)}\"]"

# Function to write PBN file
def write_pbn(file_path, content):
    directory = os.path.dirname(file_path)
    os.makedirs(directory, exist_ok=True)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(content) + "\n")

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
            board = row.get("DealNumber", "")
            dealer = abbreviate_position(row.get("Dealer", ""))
            declarer = abbreviate_position(row.get("Declarer", ""))
            contract = row.get("Contract", "")
            student = abbreviate_position(row.get("Student", ""))
            analysis = process_analysis(row.get("Analysis", ""), student, declarer)
            lead = process_lead(row.get("Lead", ""), declarer)
            
            if "/" in subfolder:
                subfolder_path, filename = os.path.split(subfolder)
            else:
                subfolder_path, filename = "", subfolder
            
            new_file_path = os.path.join("pbns", subfolder_path, f"{filename}.pbn")
            
            if subfolder != current_subfolder:
                if current_subfolder is not None:
                    write_pbn(file_path, pbn_content)
                pbn_content = []
                file_path = new_file_path
                current_subfolder = subfolder
                if header_content:
                    pbn_content.append(header_content.strip())
                    # pbn_content.append("") # Blank lines mess up the import into Shark Bridge
                pbn_content.append(f"%Creator: CSVtoPBN Version {VERSION}")
                pbn_content.append(f"%Created: {start_time}")
                pbn_content.append(f"%sourcefilename {source_file}")
                pbn_content.append(f"%HRTitleEvent {subfolder}")
            pbn_content.append(f"[Board \"{board}\"]")
            # pbn_content.append(f"[Event \"Baker Bridge - {subfolder}\"]")
            pbn_content.append(f"[Event \"\"]")
            pbn_content.append(f"{{Baker {subfolder} {board}}}")
            pbn_content.append(f"[Dealer \"{dealer}\"]")
            pbn_content.append(f"[Declarer \"{declarer}\"]")
            pbn_content.append(f"[Contract \"{contract}\"]")
            pbn_content.append(f"[Vulnerable \"None\"]")
            if student != "":
                pbn_content.append(f"[Student \"{student}\"]")
            pbn_content.append(create_deal_field(row.get("NorthHand", ""), row.get("EastHand", ""), row.get("SouthHand", ""), row.get("WestHand", "")))
            pbn_content.append(f"[Auction \"{dealer}\"]")
            pbn_content.append(process_auction(row.get("Auction", ""), dealer))
            pbn_content.append("[Result \"\"]")
            pbn_content.append(analysis)
            pbn_content.append("[BCFlags \"1f\"]")
            pbn_content.append(lead)
            pbn_content.append("")
        if current_subfolder is not None:
            write_pbn(file_path, pbn_content)
    
if __name__ == "__main__":
    convert_csv_to_pbn(*sys.argv[1:])

import os
import csv
import sys
import datetime
import re
import json

VERSION = "1.04"

# =============================================================================
# BAKER BRIDGE TAXONOMY
# Maps subfolders to skill paths, categories, and descriptions
# This data is embedded in PBN files so consuming apps don't need separate config
# =============================================================================

BAKER_BRIDGE_TAXONOMY = {
    # BASIC BIDDING
    'Major': {
        'path': 'basic_bidding/major_suit_openings',
        'name': 'Major Suit Openings',
        'category': 'Basic Bidding',
        'difficulty': 'beginner',
        'description': 'Opening 1H and 1S, responses and rebids'
    },
    'Minor': {
        'path': 'basic_bidding/minor_suit_openings',
        'name': 'Minor Suit Openings',
        'category': 'Basic Bidding',
        'difficulty': 'beginner',
        'description': 'Opening 1C and 1D, responses and rebids'
    },
    'Notrump': {
        'path': 'basic_bidding/notrump_openings',
        'name': 'Notrump Openings',
        'category': 'Basic Bidding',
        'difficulty': 'beginner',
        'description': 'Opening 1NT, 2NT, responses'
    },

    # BIDDING CONVENTIONS
    '2over1': {
        'path': 'bidding_conventions/two_over_one',
        'name': '2-Over-1 Game Force',
        'category': 'Bidding Conventions',
        'difficulty': 'intermediate',
        'description': '2/1 game forcing responses'
    },
    '2Club': {
        'path': 'bidding_conventions/strong_2c',
        'name': 'Strong 2C Bids',
        'category': 'Bidding Conventions',
        'difficulty': 'intermediate',
        'description': 'Strong artificial 2C opening and responses'
    },
    'Blackwood': {
        'path': 'bidding_conventions/blackwood',
        'name': 'Blackwood',
        'category': 'Bidding Conventions',
        'difficulty': 'intermediate',
        'description': '4NT ace-asking convention'
    },
    'Drury': {
        'path': 'bidding_conventions/reverse_drury',
        'name': 'Reverse Drury',
        'category': 'Bidding Conventions',
        'difficulty': 'intermediate',
        'description': '2C response to third/fourth seat major opening'
    },
    'FSF': {
        'path': 'bidding_conventions/fourth_suit_forcing',
        'name': 'Fourth Suit Forcing',
        'category': 'Bidding Conventions',
        'difficulty': 'intermediate',
        'description': 'Bidding the fourth suit to create a force'
    },
    'Help': {
        'path': 'bidding_conventions/help_suit_game_try',
        'name': 'Help Suit Game Try',
        'category': 'Bidding Conventions',
        'difficulty': 'intermediate',
        'description': 'Game tries after major suit agreement'
    },
    'Jacoby': {
        'path': 'bidding_conventions/jacoby_2nt_splinters',
        'name': 'Jacoby 2NT / Splinters',
        'category': 'Bidding Conventions',
        'difficulty': 'intermediate',
        'description': 'Forcing major raises and splinter bids'
    },
    'NMF': {
        'path': 'bidding_conventions/new_minor_forcing',
        'name': 'New Minor Forcing',
        'category': 'Bidding Conventions',
        'difficulty': 'intermediate',
        'description': 'Checkback after 1NT rebid'
    },
    'Ogust': {
        'path': 'bidding_conventions/ogust',
        'name': 'Ogust',
        'category': 'Bidding Conventions',
        'difficulty': 'intermediate',
        'description': '2NT inquiry after weak two opening'
    },
    'Preempt': {
        'path': 'bidding_conventions/preemptive_bids',
        'name': 'Preemptive Bids',
        'category': 'Bidding Conventions',
        'difficulty': 'intermediate',
        'description': 'Three-level and four-level preempts'
    },
    'Reverse': {
        'path': 'bidding_conventions/reverse_bids',
        'name': 'Reverse Bids',
        'category': 'Bidding Conventions',
        'difficulty': 'intermediate',
        'description': "Opener's reverse showing extra values"
    },
    'Roman': {
        'path': 'bidding_conventions/roman_keycard',
        'name': 'Roman Key Card Blackwood',
        'category': 'Bidding Conventions',
        'difficulty': 'advanced',
        'description': 'RKCB 1430 or 0314'
    },
    'Stayman': {
        'path': 'bidding_conventions/stayman',
        'name': 'Stayman',
        'category': 'Bidding Conventions',
        'difficulty': 'beginner',
        'description': '2C asking for majors over 1NT'
    },
    'Transfers': {
        'path': 'bidding_conventions/jacoby_transfers',
        'name': 'Jacoby Transfers',
        'category': 'Bidding Conventions',
        'difficulty': 'beginner',
        'description': 'Transfer bids over 1NT/2NT'
    },
    'Weak2': {
        'path': 'bidding_conventions/weak_2s',
        'name': 'Weak 2-Bids',
        'category': 'Bidding Conventions',
        'difficulty': 'beginner',
        'description': 'Weak two openings and responses'
    },

    # COMPETITIVE BIDDING
    'Cue-bid': {
        'path': 'competitive_bidding/support_cuebids',
        'name': 'Support Cue-bids',
        'category': 'Competitive Bidding',
        'difficulty': 'intermediate',
        'description': "Cue-bidding opponent's suit to show support"
    },
    'DONT': {
        'path': 'competitive_bidding/dont',
        'name': 'DONT',
        'category': 'Competitive Bidding',
        'difficulty': 'intermediate',
        'description': "Disturbing Opponent's Notrump"
    },
    'Leben': {
        'path': 'competitive_bidding/lebensohl',
        'name': 'Lebensohl',
        'category': 'Competitive Bidding',
        'difficulty': 'advanced',
        'description': 'Lebensohl convention after interference'
    },
    'Michaels': {
        'path': 'competitive_bidding/michaels_unusual',
        'name': 'Michaels / Unusual NT',
        'category': 'Competitive Bidding',
        'difficulty': 'intermediate',
        'description': 'Two-suited overcalls'
    },
    'Negative': {
        'path': 'competitive_bidding/negative_doubles',
        'name': 'Negative Doubles',
        'category': 'Competitive Bidding',
        'difficulty': 'intermediate',
        'description': 'Doubles after opponent overcalls'
    },
    'Overcalls': {
        'path': 'competitive_bidding/overcalls',
        'name': 'Overcalls',
        'category': 'Competitive Bidding',
        'difficulty': 'beginner',
        'description': 'Simple and jump overcalls'
    },
    'Takeout': {
        'path': 'competitive_bidding/takeout_doubles',
        'name': 'Takeout Doubles',
        'category': 'Competitive Bidding',
        'difficulty': 'beginner',
        'description': 'Takeout doubles and responses'
    },

    # DECLARER PLAY
    'Eliminations': {
        'path': 'declarer_play/elimination_plays',
        'name': 'Elimination Plays',
        'category': 'Declarer Play',
        'difficulty': 'advanced',
        'description': 'Strip and endplay techniques'
    },
    'Entries': {
        'path': 'declarer_play/entry_management',
        'name': 'Entry Management',
        'category': 'Declarer Play',
        'difficulty': 'intermediate',
        'description': 'Preserving and creating entries'
    },
    'Establishment': {
        'path': 'declarer_play/suit_establishment',
        'name': 'Suit Establishment',
        'category': 'Declarer Play',
        'difficulty': 'intermediate',
        'description': 'Setting up long suits'
    },
    'Finesse': {
        'path': 'declarer_play/finessing',
        'name': 'Finessing',
        'category': 'Declarer Play',
        'difficulty': 'beginner',
        'description': 'Finesse techniques and combinations'
    },
    'Holdup': {
        'path': 'declarer_play/holdup_plays',
        'name': 'Holdup Plays',
        'category': 'Declarer Play',
        'difficulty': 'intermediate',
        'description': 'Holding up winners to break communication'
    },
    'Squeeze': {
        'path': 'declarer_play/squeeze_plays',
        'name': 'Squeeze Plays',
        'category': 'Declarer Play',
        'difficulty': 'advanced',
        'description': 'Simple and compound squeezes'
    },
    'Trumpmgmt': {
        'path': 'declarer_play/trump_management',
        'name': 'Trump Management',
        'category': 'Declarer Play',
        'difficulty': 'intermediate',
        'description': 'Drawing trumps, ruffs, and trump control'
    },

    # DEFENSE
    'OLead': {
        'path': 'defense/opening_leads',
        'name': 'Opening Leads',
        'category': 'Defense',
        'difficulty': 'beginner',
        'description': 'Choosing and making opening leads'
    },
    'SecondHand': {
        'path': 'defense/second_hand_play',
        'name': 'Second Hand Play',
        'category': 'Defense',
        'difficulty': 'intermediate',
        'description': 'Second hand low and exceptions'
    },
    'Signals': {
        'path': 'defense/defensive_signals',
        'name': 'Defensive Signals',
        'category': 'Defense',
        'difficulty': 'intermediate',
        'description': 'Attitude, count, and suit preference'
    },
    'ThirdHand': {
        'path': 'defense/third_hand_play',
        'name': 'Third Hand Play',
        'category': 'Defense',
        'difficulty': 'beginner',
        'description': 'Third hand high and exceptions'
    },

    # PRACTICE DEALS
    '100Deals': {
        'path': 'practice_deals/100_miscellaneous',
        'name': '100 Miscellaneous Deals',
        'category': 'Practice Deals',
        'difficulty': 'mixed',
        'description': 'Mixed practice deals covering various topics'
    },
    '100NT': {
        'path': 'practice_deals/100_notrump',
        'name': '100 Notrump Deals',
        'category': 'Practice Deals',
        'difficulty': 'mixed',
        'description': 'Notrump bidding and play practice'
    },

    # PARTNERSHIP BIDDING
    'Bidpractice/Set1': {
        'path': 'partnership_bidding/set_01',
        'name': 'Partnership Bidding Set 1',
        'category': 'Partnership Bidding',
        'difficulty': 'intermediate',
        'description': 'Partnership bidding practice set 1'
    },
    'Bidpractice/Set2': {
        'path': 'partnership_bidding/set_02',
        'name': 'Partnership Bidding Set 2',
        'category': 'Partnership Bidding',
        'difficulty': 'intermediate',
        'description': 'Partnership bidding practice set 2'
    },
    'Bidpractice/Set3': {
        'path': 'partnership_bidding/set_03',
        'name': 'Partnership Bidding Set 3',
        'category': 'Partnership Bidding',
        'difficulty': 'intermediate',
        'description': 'Partnership bidding practice set 3'
    },
    'Bidpractice/Set4': {
        'path': 'partnership_bidding/set_04',
        'name': 'Partnership Bidding Set 4',
        'category': 'Partnership Bidding',
        'difficulty': 'intermediate',
        'description': 'Partnership bidding practice set 4'
    },
    'Bidpractice/Set5': {
        'path': 'partnership_bidding/set_05',
        'name': 'Partnership Bidding Set 5',
        'category': 'Partnership Bidding',
        'difficulty': 'intermediate',
        'description': 'Partnership bidding practice set 5'
    },
    'Bidpractice/Set6': {
        'path': 'partnership_bidding/set_06',
        'name': 'Partnership Bidding Set 6',
        'category': 'Partnership Bidding',
        'difficulty': 'intermediate',
        'description': 'Partnership bidding practice set 6'
    },
    'Bidpractice/Set7': {
        'path': 'partnership_bidding/set_07',
        'name': 'Partnership Bidding Set 7',
        'category': 'Partnership Bidding',
        'difficulty': 'intermediate',
        'description': 'Partnership bidding practice set 7'
    },
    'Bidpractice/Set8': {
        'path': 'partnership_bidding/set_08',
        'name': 'Partnership Bidding Set 8',
        'category': 'Partnership Bidding',
        'difficulty': 'intermediate',
        'description': 'Partnership bidding practice set 8'
    },
    'Bidpractice/Set9': {
        'path': 'partnership_bidding/set_09',
        'name': 'Partnership Bidding Set 9',
        'category': 'Partnership Bidding',
        'difficulty': 'intermediate',
        'description': 'Partnership bidding practice set 9'
    },
    'Bidpractice/Set10': {
        'path': 'partnership_bidding/set_10',
        'name': 'Partnership Bidding Set 10',
        'category': 'Partnership Bidding',
        'difficulty': 'intermediate',
        'description': 'Partnership bidding practice set 10'
    },
    'Bidpractice/Set11': {
        'path': 'partnership_bidding/set_11',
        'name': 'Partnership Bidding Set 11',
        'category': 'Partnership Bidding',
        'difficulty': 'intermediate',
        'description': 'Partnership bidding practice set 11'
    },
    'Bidpractice/Set12': {
        'path': 'partnership_bidding/set_12',
        'name': 'Partnership Bidding Set 12',
        'category': 'Partnership Bidding',
        'difficulty': 'intermediate',
        'description': 'Partnership bidding practice set 12'
    },
}


# Category display order for toc.json
CATEGORY_ORDER = [
    'Basic Bidding',
    'Bidding Conventions',
    'Competitive Bidding',
    'Declarer Play',
    'Defense',
    'Practice Deals',
    'Partnership Bidding'
]

def generate_toc_json(output_dir="../Package"):
    """
    Generate toc.json from BAKER_BRIDGE_TAXONOMY.
    This file is consumed by Bridge-Classroom for lesson navigation.
    """
    # Group lessons by category
    categories_dict = {}
    for lesson_id, info in BAKER_BRIDGE_TAXONOMY.items():
        category = info['category']
        if category not in categories_dict:
            categories_dict[category] = []
        categories_dict[category].append({
            'id': lesson_id,
            'name': info['name'],
            'description': info['description'],
            'difficulty': info['difficulty']
        })

    # Build categories array in display order
    categories = []
    for cat_name in CATEGORY_ORDER:
        if cat_name in categories_dict:
            # Sort lessons within category by name
            lessons = sorted(categories_dict[cat_name], key=lambda x: x['name'])
            categories.append({
                'id': cat_name.lower().replace(' ', '_'),
                'name': cat_name,
                'lessons': lessons
            })

    # Add any categories not in CATEGORY_ORDER (shouldn't happen, but just in case)
    for cat_name, lessons in categories_dict.items():
        if cat_name not in CATEGORY_ORDER:
            lessons = sorted(lessons, key=lambda x: x['name'])
            categories.append({
                'id': cat_name.lower().replace(' ', '_'),
                'name': cat_name,
                'lessons': lessons
            })

    toc = {
        'name': 'Baker Bridge',
        'description': 'Classic bridge lessons covering bidding conventions and play',
        'icon': '\u2660',  # ♠
        'version': VERSION,
        'generatedAt': datetime.datetime.now().isoformat(),
        'categories': categories
    }

    # Write toc.json
    os.makedirs(output_dir, exist_ok=True)
    toc_path = os.path.join(output_dir, 'toc.json')
    with open(toc_path, 'w', encoding='utf-8') as f:
        json.dump(toc, f, indent=2, ensure_ascii=False)

    print(f"Generated {toc_path}")
    return toc_path


def get_taxonomy_info(subfolder):
    """
    Get taxonomy info for a subfolder.
    Returns dict with path, name, category, difficulty, description.
    Falls back to generated values for unknown subfolders.
    """
    if subfolder in BAKER_BRIDGE_TAXONOMY:
        return BAKER_BRIDGE_TAXONOMY[subfolder]

    # Fallback for unknown subfolders
    return {
        'path': f'unknown/{subfolder.lower().replace("/", "_")}',
        'name': subfolder,
        'category': 'Unknown',
        'difficulty': 'intermediate',
        'description': ''
    }

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

        # Inject visibility directives only if not already present from bbparse
        # bbparse.py now generates initial [show ...] based on actual HTML visibility
        if student and "[show " not in analysis:
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
            # Hand visibility is controlled separately by [show ...] directives in the content
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
            # Get taxonomy info for this lesson
            taxonomy = get_taxonomy_info(subfolder)

            # PBN tags ordered per specification:
            # Standard tags first (in MTS order), then optional tags alphabetically

            # Standard tags (MTS order: Event, Site, Date, Board, West, North, East, South,
            #                Dealer, Vulnerable, Deal, Scoring, Declarer, Contract, Result)
            pbn_content.append(f"[Event \"Baker Bridge - {taxonomy['name']}\"]")
            pbn_content.append(f"[Board \"{board}\"]")
            pbn_content.append(f"[Dealer \"{dealer}\"]")
            pbn_content.append(f"[Vulnerable \"None\"]")
            pbn_content.append(create_deal_field(row.get("NorthHand", ""), row.get("EastHand", ""), row.get("SouthHand", ""), row.get("WestHand", "")))
            pbn_content.append(f"[Declarer \"{declarer}\"]")
            pbn_content.append(f"[Contract \"{contract}\"]")
            pbn_content.append("[Result \"\"]")

            # Optional tags (alphabetical order)
            pbn_content.append(f"[Auction \"{dealer}\"]")
            pbn_content.append(process_auction(row.get("Auction", ""), dealer))
            pbn_content.append("[BCFlags \"1f\"]")
            pbn_content.append(f"[Category \"{taxonomy['category']}\"]")
            pbn_content.append(f"[Difficulty \"{taxonomy['difficulty']}\"]")
            pbn_content.append(f"[SkillPath \"{taxonomy['path']}\"]")
            if student != "":
                pbn_content.append(f"[Student \"{student}\"]")

            # Commentary and play
            pbn_content.append(f"{{Baker {subfolder} {board}}}")
            pbn_content.append(analysis)
            pbn_content.append(lead)
            pbn_content.append("")
        if current_subfolder is not None:
            write_pbn(file_path, pbn_content)
    
if __name__ == "__main__":
    # Convert CSV to PBN files
    convert_csv_to_pbn(*sys.argv[1:])

    # Generate toc.json for Bridge-Classroom
    # Output to Package folder (sibling of Tools)
    generate_toc_json("../Package")

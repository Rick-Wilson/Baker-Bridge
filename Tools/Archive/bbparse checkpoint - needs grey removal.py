import os
import re
import csv
from bs4 import BeautifulSoup

def extract_hands(soup):
    hands = {"North": None, "East": None, "West": None, "South": None}
    
    # Find all <td> elements for standard deals
    td_elements = soup.find_all("td")

    # Extract North hand (standard deal format)
    north_hands = [td for td in td_elements if "♠" in td.get_text() and ("width:6em" in td.get("style", "") or "width:7em" in td.get("style", "") or "width:8em" in td.get("style", ""))]
    if north_hands:
        hands["North"] = parse_hand(north_hands[-1].get_text())
        # print("Got a North hand:",north_hands,"parsed:",hands["North"])

    # Extract South hand (standard deal format)
    south_hands = [td for td in td_elements if "♠" in td.get_text() and "800px" in td.get("height", "")]
    if south_hands:
        hands["South"] = parse_hand(south_hands[-1].get_text())

    # Extract East and West hands
    for tr in soup.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) >= 3:
            if tds[1].find("img", {"src": "../t1.gif"}):  # Check for t1.gif in the second <td>
                west_td = tds[0]
                east_td = tds[2]

                if "♠" in west_td.get_text():
                    hands["West"] = parse_hand(west_td.get_text())
                if "♠" in east_td.get_text():
                    hands["East"] = parse_hand(east_td.get_text())

    # Look for Bidpractice format
    bidhands_div = soup.find("div", class_="bidhands")
    if bidhands_div:
        text = bidhands_div.get_text("\n", strip=True).split("\n")
        # print("bidhand:", text)
        current_seat = None
        parsed_hands = {"North": [], "South": []}
        
        for line in text:
            if "NORTH" in line:
                current_seat = "North"
            elif "SOUTH" in line:
                current_seat = "South"
            elif current_seat and any(s in line for s in "♠♥♦♣AKQJ0123456789"):
                parsed_hands[current_seat].append(line)
        
        hands["North"] = parse_hand(" ".join(parsed_hands["North"]))
        hands["South"] = parse_hand(" ".join(parsed_hands["South"]))
    
    return hands
    
def replace_suits(text,use_colon):
    if not text:
        return text
    if use_colon:
        suits = {"♠": "S:", "♥": " H:", "♦": " D:", "♣": " C:"}
    else:
        suits = {"♠": "!S", "♥": "!H", "♦": "!D", "♣": "!C"}
    
    for suit_symbol, suit_initial in suits.items():
        text = text.replace(suit_symbol, suit_initial)

    text = text.replace("10","T").replace("--","")
    
    return text

def clean_up_suits(text,use_colon):

    if use_colon:
        text = text.replace(" ","")
        
    text = replace_suits(text,use_colon)
    
    if use_colon:
        text = text.replace("  "," ")
    
    return text
    
def rotate_hand_180_degrees(hands):
    temp = hands["North"]
    hands["North"] = hands["South"]
    hands["South"] = temp
    temp = hands["East"]
    hands["East"] = hands["West"]
    hands["West"] = temp
    
def rotate_seat_180_degrees(seat):
    partners = {
        'N': 'S',
        'S': 'N',
        'E': 'W',
        'W': 'E',
        'North': 'South',
        'South': 'North',
        'East': 'West',
        'West': 'East'
    }
    return partners.get(seat)    

def parse_hand(hand_text):
    hand = []
    # print("Parsing hand", hand_text)
    for line in hand_text.splitlines():
        line = line.strip()
        if line:
            hand.append(clean_up_suits(line,True))
    return " ".join(hand).replace("  ", " ")
    
def extract_analysis_text(td_text):
    # Regular expression to capture text between the first <br/> and the first </td>
    match = re.search(r'<br/>(.*?)</td>', td_text, re.DOTALL)
    return match.group(1).strip() if match else ""
    
def clean_up_analysis(analysis,td_str,last_bid):
#     if "partner's minor suit opening you should have" in analysis:
#         print("-----",analysis,"-----")
#     if "But even with this type of hand you should" in analysis:
#         print("-----",analysis,"-----")
    analysis = analysis.replace("\t", "")               # remove tabs (used for indentation in original)
    analysis = analysis.replace("\xa0.",".").replace("\xa0"," ")    # remove non-blank spaces
    
    analysis = analysis.replace("\n  ", "")               # remove hard line breaks
    analysis = analysis.replace("\n ", "")               # remove hard line breaks
    analysis = analysis.replace("\n", "")               # remove hard line breaks
    analysis = analysis.replace("<br/><br/>",r"\n")     # convert double line breaks to \n (will separate lines)
    analysis = analysis.replace("<br/>","")             # remove single line breaks
    analysis = replace_suits(analysis,False)
    analysis = analysis.replace("T point","10 point")   # undo 10 to T conversion when talking about points
    analysis = re.sub(r'<font.*?>.*?</font>', "", analysis, flags=re.DOTALL)
    analysis = analysis.replace("</font>","")           # remove trailing font tags
    # Remove <span> tags but keep the text inside
    analysis = re.sub(r'</?span.*?>', '', analysis, flags=re.DOTALL)
    # Remove <a>...</a> tags and their contents
    analysis = re.sub(r'<a.*?>.*?</a>', '', analysis, flags=re.DOTALL)
    analysis = analysis.replace("<b>","").replace("</b>","")
    analysis = re.sub(r'\.([A-Za-z])', r'. \1', analysis)   # Add space after periods, when text is following
    analysis = re.sub(r'\?([A-Za-z])', r'? \1', analysis)   # Add space after periods, when text is following
    analysis = analysis.strip()
    analysis = analysis.rstrip("\\n")                # remove trailing new lines (sometimes separating anchors which are already gone)
#    analysis = analysis.replace("\n", r"\n")
    if "NEXT" in td_str:
        analysis = analysis + " [NEXT]"
        analysis = analysis.replace("lickto", "lick NEXT to")
        analysis = analysis.replace("lick.", "lick NEXT.")
    elif "ROTATE" in td_str:
        analysis = analysis + " [ROTATE]"
        analysis = analysis.replace("lickto", "lick ROTATE to")
        analysis = analysis.replace("lick.", "lick ROTATE.")
    elif not 'href="deal' in td_str:
        analysis = analysis + " [BID " + replace_suits(last_bid,False) + "]"
        
#     if "partner's minor suit opening you should have" in analysis:
#         print("*****",analysis,"*****")
#     if "But even with this type of hand you should" in analysis:
#         print("*****",analysis,"*****")

    return analysis


########## E X T R A C T   P R O G R E S S I V E   A N A L Y S I S #################
#
#   Takes a table with the HTML auction.  Returns the auction in
#   table format, as well as Dealer, Declarer and Contract.
#
####################################################################################

def extract_progressive_analysis(soup,filepath):

# Standard layout:
#
#   Each step has an anchor <a>:
#       Each contains a table:
#           Sub-table: Auction so far
#       Analysis for this step
#
# General approach:
# 
#   1. get full auction as a simple list
#   2. Iterate through tables (Steps)
#       - find auction-so-far as a simple list.  This auction will end with "BID"
#           - Look into the full auction to see what BID will become
#               - This will be the label for this step
#       - Pull the text from the outer table, following the inner table.  Also
#               exclude the <font> enclosed text (prior steps in grey).
#       - Save the analysis as a new list element, with [BID] prepended.

    analysis_lines = []

    final_auction_table = extract_final_auction_table(soup)
    
    dealer, auction_str, contract, declarer, analysis_str = extract_auction_info(final_auction_table,filepath)

#   Remove the vertical bars, and parse into a list
    auction_str = auction_str.replace(" |", "")
    
#   all_bids = ["pass", "1♠", "pass", "2♠", "pass", "4♠"]
    all_bids = auction_str.split()
    
#     print("auction_str:", auction_str)
#     print("")
    # print("all_bids:", all_bids)
    # print("")
    
    all_tds = soup.find_all('td')


#   Iterate all tables which contain subtables.  These will normally have the auction
#   in the inner table, then analysis following in the outer table:

    table_tds = [td for td in all_tds if td.find('table')]
    for td in table_tds:
        partial_dealer, partial_auction_str, partial_contract, partial_declarer, partial_analysis_str = extract_auction_info(td,filepath)
        partial_auction_str = partial_auction_str.replace(" |", "")
        partial_auction_list = partial_auction_str.split()
        last_bid = partial_auction_list[-1]
        if last_bid == "BID":
            if len(partial_auction_list) > len(all_bids):
                print("***")
                print("problem with " + filepath)
                print("all_bids:            ", all_bids)
                print("partial_auction_list:", partial_auction_list)
            else:
                last_bid = all_bids[len(partial_auction_list)-1]
        
        analysis = extract_analysis_text(str(td))
        analysis = clean_up_analysis(analysis,str(td),last_bid)
        analysis_lines.append(analysis)
#   Now iterate TDs which do not contain an inner table, but do contain the text "NEXT"
        
    non_table_tds = [td for td in all_tds if not td.find('table')]
    for td in non_table_tds:
#        print("td:", str(td))
        if "3" in td.get("rowspan",""):
            analysis = extract_analysis_text(str(td))
            analysis = clean_up_analysis(analysis,str(td),"")
            analysis_lines.append(analysis)
            
#         print(analysis)
#         print()

    return "\\n".join(analysis_lines)

########## E X T R A C T   A U C T I O N   I N F O ##################
#
#   Takes a table with the HTML auction.  Returns the auction in
#   table format, as well as Dealer, Declarer and Contract.
#
#####################################################################

def extract_auction_info(auction_table,filepath):

    positions = ["West", "North", "East", "South"]

#         Converts an HTML table like this:
#         WEST   NORTH   EAST    SOUTH
#         pass   1♠      pass    2♠
#         pass   4♠      pass    pass
#         
#         Into "auction" a list like this:
#         [
#             ["pass", "1♠", "pass", "2♠"],
#             ["pass", "4♠", "pass", "pass"]
#         ]

    rows = auction_table.find_all("tr")
    auction = [[td.get_text(strip=True) or "" for td in row.find_all("td")] for row in rows[1:]]
    
#   Flatten the auction into a single list:
#   all_bids = ["pass", "1♠", "pass", "2♠", "pass", "4♠", "pass", "pass", "pass"]

    all_bids = [bid for round_bids in auction for bid in round_bids]
    
    while all_bids and all_bids[-1].strip() == "":
        all_bids.pop()

#   dealer is first non-blank:
    dealer = next((positions[i % 4] for i, bid in enumerate(all_bids) if bid.lower() not in [""]), None)
    
#   contract is final bid, excluding pass, double, or redouble.
#   challenge is "", double or redouble.
#   strain is the final bid, less the level.
#   declarer is either the auction winner or their partner - whichever first bid the strain.

    # Initialize variables
    strain, contract, declarer, challenge = None, None, None, None
    
    suffix = ""
    
    # Identify the contract (excluding pass, double, redouble)
    for i in range(len(all_bids) - 1, -1, -1):
        bid = all_bids[i].lower()
        if bid not in ["", "pass", "all pass", "double", "redouble"]:
            contract = all_bids[i]  # The final contract bid
            strain = contract[1:]  # Strain is the contract without the level
            break
    
    # Identify the challenge (double, redouble, or blank)
    if i < len(all_bids) - 1:
        next_bid = all_bids[i + 1].lower()
        if next_bid == "double":
            challenge = "double"
            suffix = "X"
        elif next_bid == "redouble":
            challenge = "redouble"
            suffix = "XX"
        else:
            challenge = ""
            suffix = ""
    
    # Determine the declarer
    positions = ["West", "North", "East", "South"]
    contract_seat = i % 4  # The position of the final contract bid

    # Find who first bid the strain (either the contract winner or their partner)
    for j in range(i):
        bid = all_bids[j]
        if j % 2 == contract_seat % 2:  # only consider bids by the winning pair:
            if bid and bid[1:] == strain:  # A bid matching the strain
                declarer = positions[j % 4]
                break
                
    # for some reason, the above loop doesn't find the declarer if the final bid set the
    # strain, so we'll cover that case here:
    if declarer == None:
        declarer = positions[contract_seat]

    analysis_start = False
    analysis_lines = []
    pass_count = 0

    analysis_str = "\\n".join(analysis_lines)
    auction_str = " | ".join([" ".join(bid_row) for bid_row in auction])
    auction_str = ' '.join(auction_str.split())

    contract = contract + suffix
    
    if "double pass pass pass" in auction_str:
        contract = contract + "X"
#    print (filepath, ", Dealer", dealer, ", contract", contract, ", declarer", declarer, ", auction", auction_str)

    return dealer, auction_str, contract, declarer, analysis_str

def extract_final_auction_table(soup):

    # Find all tables
    tables = soup.find_all('table')

    # Filter tables that contain the auction (WEST NORTH EAST SOUTH row)
    auction_tables = [
        table for table in tables
        if any("WEST" in cell.get_text(strip=True) for cell in table.find_all("td")) and
           any("NORTH" in cell.get_text(strip=True) for cell in table.find_all("td"))
    ]
    if not auction_tables:
        return None

    # Select the last auction table
    return auction_tables[-1]

def extract_bidding_info(soup,filepath):
    # Check for the standard bidding div first
    bidding_div = soup.find("div", class_="bidding")
    if bidding_div:
        table = bidding_div.find("table")
        if not table:
            return None, None, None, None, None
            
        dealer, auction_str, contract, declarer, analysis_str = extract_auction_info(table,filepath)

        analysis_start = False
        analysis_lines = []
        pass_count = 0

        all_text = bidding_div.get_text(separator="\n").strip().split("\n")
        for line in all_text:
            stripped = line.strip()
            if analysis_start:
                if stripped:
                    analysis_lines.append(stripped)
            elif stripped and stripped != "pass":
                pass_count = 0
            elif stripped == "pass":
                pass_count += 1
                if pass_count >= 3:
                    analysis_start = True

        analysis_str = "\\n".join(analysis_lines)
        
        return dealer, auction_str, contract, declarer, analysis_str

    # Handle the alternative format

    auction_table = extract_final_auction_table(soup)

#    print("auction_table:", auction_table)

    dealer, auction_str, contract, declarer, analysis_str = extract_auction_info(auction_table,filepath)

    analysis_str = extract_progressive_analysis(soup,filepath)

    return dealer, auction_str, contract, declarer, analysis_str

def extract_lesson_kind(soup):
    # Extract all anchor tags
    anchors = soup.find_all("a")

    # Collect unique non-blank text
    kind_texts = set()

    for anchor in anchors:
        text = anchor.get_text(strip=True)
        if text and ( not text.startswith("Deal")
                    and "summary" not in text.lower()
                    and "lesson" not in text.lower()
                    and "back" not in text.lower()
                    and "introduction" not in text.lower()
                    # and "rotate" not in text.lower()
                    and "home" not in text.lower()
                    and "review" not in text.lower()):
            kind_texts.add(text)

    return "+".join(sorted(kind_texts)) if kind_texts else None

def extract_opening_lead(soup,filepath):
    # Find all text nodes that contain the phrase "leads the"
    lead_text = soup.find(string=lambda text: text and ( "leads" in text or "OL:" in text or "Partner led" in text or "Lead the" in text or "probably the" in text))
    
    if not lead_text:
        return None
    # print(filepath + ":")
    # print("lead_text", lead_text)
    # Move up to the parent <td> element to access the HTML structure
    lead_td = lead_text.find_parent("td")
    if not lead_td:
        return None
    # print(str(lead_td))
    
    # Regular expression to match "leads the" followed by a rank and suit, with optional <span> in between
    pattern_1 = r'leads (?:the )?\s*(?:<span.*?>)?([♠♥♦♣])(?:<\/span.*?>)?\s*(\d+|[AKQJT0123456789])'
    pattern_2 = r'OL\:\s*(?:<span.*?>)?([♠♥♦♣])(?:<\/span.*?>)?\s*(\d+|[AKQJT0123456789])'
    pattern_3 = r'Partner led the (?:<span.*?>)?([♠♥♦♣])(?:<\/span.*?>)?\s*(\d+|[AKQJT0123456789])'
    pattern_4 = r'Lead the (?:<span.*?>)?([♠♥♦♣])(?:<\/span.*?>)?\s*(\d+|[AKQJT0123456789])'
    pattern_5 = r'probably the (?:<span.*?>)?([♠♥♦♣])(?:<\/span.*?>)?\s*(\d+|[AKQJT0123456789])'
    
    match = re.search(pattern_1, str(lead_td), re.DOTALL)
    if not match:
        match = re.search(pattern_2, str(lead_td), re.DOTALL)
    if not match:
        match = re.search(pattern_3, str(lead_td), re.DOTALL)
    if not match:
        match = re.search(pattern_4, str(lead_td), re.DOTALL)
    if not match:
        match = re.search(pattern_5, str(lead_td), re.DOTALL)

    if match:
        rank = match.group(1)
        suit = match.group(2)
        # print("Found it!")
        # print(f"{rank}{suit}")
        return f"{rank}{suit}"
    return ""
    
def process_files(folder_path, output_csv, max_files=3000):
    files = [
        os.path.join(dirpath, file)
        for dirpath, _, filenames in os.walk(folder_path)
        for file in filenames
        if file.startswith("deal") and file.endswith(".html") and file not in ["deal00.html", "deal000.html"]
    ]

    results = []

    for filepath in files[:max_files]:
        filename = os.path.basename(filepath)
        subfolder_path = os.path.relpath(os.path.dirname(filepath), folder_path)
        
        match = re.search(r"deal(\d+)", filename)
        deal_number = int(match.group(1)) if match else None
        
        with open(filepath, "r", encoding="utf-8") as file:
            soup = BeautifulSoup(file, "html.parser")
            hands = extract_hands(soup)
            dealer, auction_str, contract, declarer, analysis = extract_bidding_info(soup,filepath)
            contract = replace_suits(contract,False).replace("!", "")
            auction_str = replace_suits(auction_str,False).replace("!","").replace("redouble","XX").replace("double","X")
            opening_lead = replace_suits(extract_opening_lead(soup,filepath),False)
            if opening_lead:
                opening_lead = opening_lead.replace("!","")
            kind = extract_lesson_kind(soup)
            
            if "[ROTATE]" in analysis:
                rotate_hand_180_degrees(hands)
                dealer = rotate_seat_180_degrees(dealer)
                declarer = rotate_seat_180_degrees(declarer)
            
#         print()
#         print(filepath, ":")
#         print("Dealer:", dealer, "contract:", contract, "declarer:", declarer, "auction:", auction_str, "lead:", opening_lead)
#         print()
#         print("analysis:", analysis)
        
        results.append([
            subfolder_path, filename, deal_number, kind,
            hands["North"], hands["East"], hands["South"], hands["West"],
            dealer, auction_str, contract, declarer, opening_lead, analysis
        ])

    results.sort(key=lambda x: (x[0], x[1]))
    
    with open(output_csv, "w", newline="", encoding="utf-8") as csvfile:
        csvwriter = csv.writer(csvfile, quoting=csv.QUOTE_MINIMAL)
        csvwriter.writerow([
            "Subfolder", "Filename", "DealNumber", "Kind", "NorthHand", "EastHand", "SouthHand", "WestHand",
            "Dealer", "Auction", "Contract", "Declarer", "Lead", "Analysis"
        ])
        csvwriter.writerows(results)

folder_path = "/Users/rick/Documents/Bridge/Baker Bridge/Website/Baker Bridge/bakerbridge.coffeecup.com"
output_csv = "BakerBridge.csv"
process_files(folder_path, output_csv)
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

def parse_hand(hand_text):
    hand = []
    # print("Parsing hand", hand_text)
    for line in hand_text.splitlines():
        line = line.strip()
        if line:
            hand.append(clean_up_suits(line,True))
    return " ".join(hand).replace("  ", " ")

def extract_bidding_info(soup):
    bidding_div = soup.find("div", class_="bidding")
    if not bidding_div:
        return None, None, None, None, None  
    
    table = bidding_div.find("table")
    if not table:
        return None, None, None, None, None
    
    rows = table.find_all("tr")
    headers = [th.get_text(strip=True) for th in rows[0].find_all("th")]
    
    auction = []
    for row in rows[1:]:
        bids = [td.get_text(strip=True) or "pass" for td in row.find_all("td")]
        auction.append(bids)
    
    all_bids = [bid for round_bids in auction for bid in round_bids]
    positions = ["West", "North", "East", "South"]
    
    dealer = next((positions[i % 4] for i, bid in enumerate(all_bids) if bid.lower() not in ["", "pass"]), None)
    contract, declarer = None, None
    
    for i in range(len(all_bids) - 1, -1, -1):
        if all_bids[i].lower() not in ["", "pass"]:
            contract = all_bids[i]
            declarer = positions[i % 4]
            break
    
    all_text = bidding_div.get_text(separator="\n").strip().split("\n")
    analysis_start = False
    analysis_lines = []
    pass_count = 0
    for line in all_text:
        stripped = line.strip()
        if analysis_start:
            if stripped:
                analysis_lines.append(stripped)
        elif stripped and stripped != "pass":
        	pass_count = 0
        elif stripped and stripped == "pass":
            pass_count = pass_count + 1
            if pass_count >= 3:
                analysis_start = True
    
    analysis_str = "\\n".join(analysis_lines)
    auction_str = " | ".join([" ".join(bid_row) for bid_row in auction])
    auction_str = clean_up_suits(auction_str,False)
    
    contract = replace_suits(contract,False)
    analysis_str = replace_suits(analysis_str,False)
    
    return dealer, auction_str, contract, declarer, analysis_str

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
            dealer, auction, contract, declarer, analysis = extract_bidding_info(soup)
        
        results.append([
            subfolder_path, filename, deal_number,
            hands["North"], hands["East"], hands["South"], hands["West"],
            dealer, auction, contract, declarer, analysis
        ])

    results.sort(key=lambda x: (x[0], x[1]))
    
    with open(output_csv, "w", newline="", encoding="utf-8") as csvfile:
        csvwriter = csv.writer(csvfile, quoting=csv.QUOTE_MINIMAL)
        csvwriter.writerow([
            "Subfolder", "Filename", "DealNumber", "NorthHand", "EastHand", "SouthHand", "WestHand",
            "Dealer", "Auction", "Contract", "Declarer", "Analysis"
        ])
        csvwriter.writerows(results)

folder_path = "/Users/rick/Documents/Bridge/Baker Bridge/Website/Baker Bridge/bakerbridge.coffeecup.com"
output_csv = "BakerBridge.csv"
process_files(folder_path, output_csv)
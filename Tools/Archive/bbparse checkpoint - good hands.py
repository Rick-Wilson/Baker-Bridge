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

    # Handle Bidpractice format
    bidpractice_div = soup.find("div", class_="bidhands")
    if bidpractice_div:
        text_lines = bidpractice_div.get_text(separator="\n").split("\n")
        current_hand = None
        hand_data = {"North": [], "South": []}

        for line in text_lines:
            line = line.strip()
            if line == "NORTH":
                current_hand = "North"
            elif line == "SOUTH":
                current_hand = "South"
            elif current_hand and line:  # If we're in a hand and the line has text
                hand_data[current_hand].append(line)

        if hand_data["North"]:
            hands["North"] = parse_hand("\n".join(hand_data["North"]))
        if hand_data["South"]:
            hands["South"] = parse_hand("\n".join(hand_data["South"]))

    return hands
def parse_hand(hand_text):
    suits = {"♠": "S:", "♥": "H:", "♦": "D:", "♣": "C:"}
    hand = []
    for line in hand_text.splitlines():
        line = line.strip()
        if line and line[0] in suits:
            suit_initial = suits[line[0]]
            cards = line[1:].strip().replace(" ", "").replace("10","T").replace("--","")
            hand.append(f"{suit_initial} {cards}")
    return " ".join(hand)

def process_files(folder_path, output_csv, max_files=5000):
    files = [
        os.path.join(dirpath, file)
        for dirpath, _, filenames in os.walk(folder_path)
        for file in filenames
        if file.startswith("deal") and file.endswith(".html") and not file in ["deal00.html", "deal000.html"]
    ]
    
    results = []
    
    for filepath in files[:max_files]:
        filename = os.path.basename(filepath)
        subfolder_path = os.path.relpath(os.path.dirname(filepath), folder_path)
        
        match = re.search(r"deal(\d+)", filename)
        deal_number = int(match.group(1)) if match else None
        
        with open(filepath, "r", encoding="utf-8") as file:
            soup = BeautifulSoup(file, "html.parser")
            is_bidpractice = "Bidpractice" in subfolder_path  # Check if file is from Bidpractice
            hands = extract_hands(soup)
        
        results.append([
            subfolder_path,
            filename,
            deal_number,
            hands["North"],
            hands["East"],    
            hands["South"],
            hands["West"]
        ])
    
    results.sort(key=lambda x: (x[0], x[1]))
    
    with open(output_csv, "w", newline="", encoding="utf-8") as csvfile:
        csvwriter = csv.writer(csvfile)
        csvwriter.writerow(["Subfolder", "Filename", "DealNumber", "NorthHand", "EastHand", "SouthHand", "WestHand"])
        csvwriter.writerows(results)

# Example usage
folder_path = "/Users/rick/Documents/Bridge/Baker Bridge/Website/Baker Bridge/bakerbridge.coffeecup.com"
output_csv = "BakerBridge.csv"
process_files(folder_path, output_csv)

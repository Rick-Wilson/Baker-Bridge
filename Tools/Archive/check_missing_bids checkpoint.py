import csv
import sys
import re

SEATS = ['North', 'East', 'South', 'West']

# Detect if a bid is a pass or non-pass
def is_non_pass(bid):
    bid = bid.strip().lower()
    return bid not in ('', 'pass', 'p', 'all')

# Parse the auction string to get a list of bids per seat
def parse_auction(auction):
    auction = auction.strip()
    if not auction:
        return []
    # Remove labels like | and extra whitespace
    auction = re.sub(r'[|\n]+', ' ', auction)
    return [b.strip() for b in auction.split() if b.strip()]

# Determine starting seat based on dealer
def get_seat_order(dealer):
    if dealer not in SEATS:
        return SEATS
    start = SEATS.index(dealer)
    return SEATS[start:] + SEATS[:start]

def check_missing_hands(input_csv):
    with open(input_csv, newline='', encoding='utf-8') as infile:
        reader = csv.DictReader(infile)
        for row in reader:
            dealer = row.get('Dealer', 'North')
            auction = parse_auction(row.get('Auction', ''))
            seat_order = get_seat_order(dealer)
            
            hands = {
                'North': row.get('NorthHand', '').strip(),
                'East': row.get('EastHand', '').strip(),
                'South': row.get('SouthHand', '').strip(),
                'West': row.get('WestHand', '').strip()
            }

            for i, bid in enumerate(auction):
                seat = seat_order[i % 4]
                if hands.get(seat, '') == '' and is_non_pass(bid):
                    print(f"{row['Subfolder']}, Deal {row['DealNumber']}: Missing hand for {seat} who made non-pass bid '{bid}'")

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python check_missing_bids.py input.csv")
    else:
        check_missing_hands(sys.argv[1])

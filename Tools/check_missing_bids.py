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
    auction = re.sub(r'[|\n]+', ' ', auction)
    return [b.strip() for b in auction.split() if b.strip()]

# Determine starting seat based on dealer
def get_seat_order(dealer):
    if dealer not in SEATS:
        return SEATS
    start = SEATS.index(dealer)
    return SEATS[start:] + SEATS[:start]

def check_missing_hands(input_csv, output_csv):
    with open(input_csv, newline='', encoding='utf-8') as infile, \
         open(output_csv, 'w', newline='', encoding='utf-8') as outfile:

        reader = csv.DictReader(infile)
        fieldnames = ['Subfolder', 'Deal', 'Seat', 'Bid', 'BidSequence', 'NorthHand', 'EastHand', 'SouthHand', 'WestHand']
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()

        for row in reader:
            dealer = row.get('Dealer', 'North')
            auction = parse_auction(row.get('Auction', ''))
            seat_order = get_seat_order(dealer)
            row_written = False

            hands = {
                'North': row.get('NorthHand', '').strip(),
                'East': row.get('EastHand', '').strip(),
                'South': row.get('SouthHand', '').strip(),
                'West': row.get('WestHand', '').strip()
            }

            first_non_pass_index = None
            for i, bid in enumerate(auction):
                if is_non_pass(bid):
                    first_non_pass_index = i
                    break

            for i, bid in enumerate(auction):
                seat = seat_order[i % 4]
                if is_non_pass(bid) and hands.get(seat, '') == '':
                    bid_sequence = '-'.join(auction[first_non_pass_index:i+1]) if first_non_pass_index is not None else bid

                    writer.writerow({
                        'Subfolder': row['Subfolder'],
                        'Deal': row['DealNumber'],
                        'Seat': seat,
                        'Bid': bid,
                        'BidSequence': bid_sequence,
                        'NorthHand': hands['North'],
                        'EastHand': hands['East'],
                        'SouthHand': hands['South'],
                        'WestHand': hands['West']
                    })
                    
                    row_written = True
                    
            if not row_written and hands.get('East','') == '':
                writer.writerow({
                    'Subfolder': row['Subfolder'],
                    'Deal': row['DealNumber'],
                    'Seat': 'West',
                    'Bid': 'Calm',
                    'BidSequence': 'Calm',
                    'NorthHand': hands['North'],
                    'EastHand': hands['East'],
                    'SouthHand': hands['South'],
                    'WestHand': hands['West']
                })

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: python check_missing_bids.py input.csv output.csv")
    else:
        check_missing_hands(sys.argv[1], sys.argv[2])

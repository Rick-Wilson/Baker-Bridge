import csv
import sys
from collections import defaultdict

SUITS = ['S', 'H', 'D', 'C']

# Parse a hand string like 'S:J86 H:A98 D:8653 C:AKQ' into a dict of suit:cards
def parse_hand(hand):
    cards = set()
    if not hand.strip():
        return cards  # empty hand (allowed)
    try:
        parts = hand.strip().split()
        for part in parts:
            suit, values = part.split(':')
            for card in values:
                cards.add(f"{suit}{card}")
    except Exception as e:
        pass  # basic format error
    return cards

def validate_csv(filename):
    with open(filename, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            subfolder = row.get("Subfolder", "")
            deal_number = row.get("DealNumber", "")
            hands = {
                'North': parse_hand(row.get("NorthHand", "")),
                'East': parse_hand(row.get("EastHand", "")),
                'South': parse_hand(row.get("SouthHand", "")),
                'West': parse_hand(row.get("WestHand", ""))
            }

            # Check hand lengths
            for direction, cards in hands.items():
                if len(cards) not in (0, 13):
                    print(f"{subfolder}, Deal {deal_number}: {direction} has {len(cards)} cards (expected 0 or 13)")

            # Check for duplicate cards
            all_cards = defaultdict(list)
            for direction, cards in hands.items():
                for card in cards:
                    all_cards[card].append(direction)

            for card, locations in all_cards.items():
                if len(locations) > 1:
                    print(f"{subfolder}, Deal {deal_number}: Card {card} appears in multiple hands: {', '.join(locations)}")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python validate_deals.py <csv_filename>")
    else:
        validate_csv(sys.argv[1])

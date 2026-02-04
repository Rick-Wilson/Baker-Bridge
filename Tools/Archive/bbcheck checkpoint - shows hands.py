import csv
import sys
from collections import defaultdict

SUITS = ['S', 'H', 'D', 'C']

# Parse a hand string like 'S:J86 H:A98 D:8653 C:AKQ' into a dict of suit:cards
def parse_hand(hand):
    hand_dict = {suit: set() for suit in SUITS}
    if not hand.strip():
        return hand_dict
    try:
        parts = hand.strip().split()
        for part in parts:
            suit, values = part.split(':')
            for card in values:
                hand_dict[suit].add(card)
    except Exception as e:
        pass  # basic format error
    return hand_dict

def validate_csv(filename):
    with open(filename, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            subfolder = row.get("Subfolder", "")
            deal_number = row.get("DealNumber", "")
            hands_raw = {
                'North': row.get("NorthHand", ""),
                'East': row.get("EastHand", ""),
                'South': row.get("SouthHand", ""),
                'West': row.get("WestHand", "")
            }
            hands = {direction: parse_hand(hands_raw[direction]) for direction in hands_raw}

            # Check hand lengths
            for direction, suits in hands.items():
                total_cards = sum(len(cards) for cards in suits.values())
                if total_cards not in (0, 13):
                    print(f"{subfolder}, Deal {deal_number}: {direction} has {total_cards} cards (expected 0 or 13)")

            # Check for duplicate cards
            all_cards = defaultdict(list)
            for direction, suits in hands.items():
                for suit, cards in suits.items():
                    for card in cards:
                        all_cards[f"{suit}{card}"].append(direction)

            for card, locations in all_cards.items():
                if len(locations) > 1:
                    print(f"{subfolder}, Deal {deal_number}: Card {card} appears in multiple hands: {', '.join(locations)}")
                    suit = card[0]
                    for direction in locations:
                        suit_cards = ''.join(sorted(hands[direction][suit]))
                        print(f"    {direction} {suit} holding: {suit_cards}")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python validate_deals.py <csv_filename>")
    else:
        validate_csv(sys.argv[1])

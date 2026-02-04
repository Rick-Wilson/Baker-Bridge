import csv
from collections import defaultdict
import sys
import random

SUITS = ['S', 'H', 'D', 'C']
RANKS = 'AKQJT98765432'
FULL_DECK = {f"{suit}{rank}" for suit in SUITS for rank in RANKS}

# Parse a hand like "S:KQ5 H:AK6 D:AK92 C:AT8" into a set of cards
def parse_hand(hand_str):
    cards = set()
    if not hand_str:
        return cards
    for part in hand_str.split():
        suit, ranks = part.split(':')
        for rank in ranks:
            cards.add(f"{suit}{rank}")
    return cards

# Format a set of cards into the expected hand string format
def format_hand(cards):
    suit_map = defaultdict(list)
    for card in cards:
        suit, rank = card[0], card[1:]
        suit_map[suit].append(rank)
    for suit in suit_map:
        suit_map[suit] = sorted(suit_map[suit], key=lambda r: RANKS.index(r))
    return ' '.join(f"{s}:{''.join(suit_map[s])}" for s in SUITS)

# Assign remaining cards to East and West
def assign_to_east_west(unused_cards):
    suit_groups = {s: [] for s in SUITS}
    for card in unused_cards:
        suit_groups[card[0]].append(card)

    east_hand, west_hand = set(), set()

    for suit in SUITS:
        cards = sorted(suit_groups[suit], key=lambda c: RANKS.index(c[1:]))
        random.shuffle(cards)
        for i, card in enumerate(cards):
            if len(east_hand) < 13 and (len(east_hand) <= len(west_hand)):
                east_hand.add(card)
            else:
                west_hand.add(card)

    while len(east_hand) > 13:
        card = east_hand.pop()
        west_hand.add(card)
    while len(west_hand) > 13:
        card = west_hand.pop()
        east_hand.add(card)

    return format_hand(east_hand), format_hand(west_hand)

def load_constructed_hands(filename):
    constructed = {}
    with open(filename, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (row['Subfolder'], row['Deal'])
            constructed[key] = row
    return constructed

def fill_missing_hands(input_csv, output_csv, constructed_csv):
    constructed_hands = load_constructed_hands(constructed_csv)
    used_constructed = 0
    generated = 0

    with open(input_csv, newline='', encoding='utf-8') as infile, \
         open(output_csv, 'w', newline='', encoding='utf-8') as outfile:

        reader = csv.DictReader(infile)
        fieldnames = reader.fieldnames
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()

        for row in reader:
            key = (row['Subfolder'], row['DealNumber'])
            north = parse_hand(row['NorthHand'])
            south = parse_hand(row['SouthHand'])
            east = parse_hand(row['EastHand'])
            west = parse_hand(row['WestHand'])

            if len(east) == 0 and len(west) == 0:
                if key in constructed_hands:
                    c = constructed_hands[key]
                    c_north = parse_hand(c['NorthHand'])
                    c_south = parse_hand(c['SouthHand'])
                    if c_north != north or c_south != south:
                        print(f"ERROR: Hand mismatch for {key[0]}, Deal {key[1]}")
                    else:
                        row['EastHand'] = c['EastHand']
                        row['WestHand'] = c['WestHand']
                        used_constructed += 1
                else:
                    used = north | south
                    unused = FULL_DECK - used
                    if len(unused) != 26:
                        print(f"Warning: {row['Filename']} has unexpected used card count")
                    east_hand, west_hand = assign_to_east_west(unused)
                    row['EastHand'] = east_hand
                    row['WestHand'] = west_hand
                    generated += 1

            writer.writerow(row)

    print(f"Hands used from constructed_hands: {used_constructed}")
    print(f"Hands generated internally: {generated}")

if __name__ == '__main__':
    if len(sys.argv) != 4:
        print("Usage: python bb_fill.py input.csv output.csv constructed_hands.csv")
    else:
        fill_missing_hands(sys.argv[1], sys.argv[2], sys.argv[3])

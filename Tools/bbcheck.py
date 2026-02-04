import csv
import sys
from collections import defaultdict

SUITS = ['S', 'H', 'D', 'C']
RANKS = 'AKQJT98765432'
ALL_CARDS = {f"{suit}{rank}" for suit in SUITS for rank in RANKS}
PREF_ORDER = ['North', 'West', 'East', 'South']
SUIT_SYMBOLS = {'S': '&spades;', 'H': '&hearts;', 'D': '&diams;', 'C': '&clubs;'}

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
        pass
    return hand_dict

def hand_to_string(hand):
    return ' '.join(RANKS[i] if RANKS[i] != 'T' else '10' for i in range(len(RANKS)) if RANKS[i] in hand)

def suggest_replacement(used_cards, duplicate_card, hands_with_card, full_hands):
    missing_cards = ALL_CARDS - used_cards
    suit = duplicate_card[0]
    rank = duplicate_card[1]
    
    # If all 4 hands are present, there's only 1 card missing
    if full_hands:
        candidates = sorted([c for c in missing_cards if c[0] == suit], key=lambda c: RANKS.index(c[1]))
        if candidates:
            return candidates[0]
    else:
        # Pick closest card in rank within same suit
        missing_ranks = [c[1] for c in missing_cards if c[0] == suit]
        if not missing_ranks:
            return None
        # Find the closest rank by index
        rank_index = RANKS.index(rank)
        closest = sorted(missing_ranks, key=lambda r: abs(RANKS.index(r) - rank_index))
        if closest:
            return f"{suit}{closest[0]}"
    return None

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
            used_cards = set()
            for direction, suits in hands.items():
                for suit, cards in suits.items():
                    for card in cards:
                        all_cards[f"{suit}{card}"].append(direction)
                        used_cards.add(f"{suit}{card}")

            for card, locations in all_cards.items():
                if len(locations) > 1:
                    print(f"{subfolder}, Deal {deal_number}: Card {card} appears in multiple hands: {', '.join(locations)}")
                    suit = card[0]
                    for direction in locations:
                        suit_cards = ''.join(sorted(hands[direction][suit]))
                        print(f"    {direction} {suit} holding: {suit_cards}")
                    
                    full_hands = all(sum(len(hands[d][s]) for s in SUITS) == 13 for d in hands)
                    replacement = suggest_replacement(used_cards, card, locations, full_hands)
                    if replacement:
                        for preferred in PREF_ORDER:
                            if preferred in locations:
                                suit = card[0]
                                old_hand = hands[preferred][suit].copy()
                                hands[preferred][suit].remove(card[1])
                                hands[preferred][suit].add(replacement[1])
                                old_display = hand_to_string(old_hand)
                                new_display = hand_to_string(hands[preferred][suit])
                                print(f"    Suggestion: replace {suit}: {old_display} with {suit}: {new_display}")

                                # Print regex suggestion
                                html_suit = SUIT_SYMBOLS[suit]
                                escaped_old = ' '.join(old_display.split())
                                escaped_new = ' '.join(new_display.split())
                                print(f"    Regex: r\"{html_suit}.*?{escaped_old}\" => '{html_suit} {escaped_new}'")
                                break

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python validate_deals.py <csv_filename>")
    else:
        validate_csv(sys.argv[1])

#!/usr/bin/env python3
"""
apply_sme_corrections.py - Apply SME corrections to BakerBridge.csv

Reads sme_corrections.txt and applies Dealer and Exchange corrections to the CSV.
AllowAuction entries are passed through for use by create_full_pbn.py.

Correction types:
  - Dealer X       : Change dealer to specified seat (N/E/S/W)
  - Exchange XX-YY : Swap two cards between hands (e.g., DJ-DQ swaps Diamond Jack and Queen)
  - AllowAuction   : Ignored here (handled by create_full_pbn.py)

Usage:
    python3 apply_sme_corrections.py [--input CSV] [--corrections FILE] [--output CSV]
"""

import csv
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
TOOLS_DIR = SCRIPT_DIR.parent
DEFAULT_INPUT = TOOLS_DIR / "BakerBridge.csv"
DEFAULT_CORRECTIONS = SCRIPT_DIR / "sme_corrections.txt"
DEFAULT_OUTPUT = TOOLS_DIR / "BakerBridge-sme.csv"


def parse_corrections(path: Path) -> dict:
    """
    Parse sme_corrections.txt into a dict keyed by board_id.
    Returns: {board_id: [list of corrections]}
    """
    corrections = {}
    if not path.exists():
        return corrections

    with open(path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            # Parse: BoardID - CorrectionType [params]
            match = re.match(r'^([^\s-]+(?:/[^\s-]+)?-\d+)\s*-\s*(.+)$', line)
            if not match:
                print(f"Warning: Could not parse line: {line}", file=sys.stderr)
                continue

            board_id = match.group(1)
            correction = match.group(2).strip()

            if board_id not in corrections:
                corrections[board_id] = []
            corrections[board_id].append(correction)

    return corrections


def parse_card(card_str: str) -> tuple:
    """
    Parse card string like 'DJ' or 'SQ' into (suit, rank).
    Returns (suit_letter, rank_letter) e.g., ('D', 'J')
    """
    card_str = card_str.upper()
    if len(card_str) != 2:
        return None, None
    return card_str[0], card_str[1]


def find_card_in_hand(hand: str, suit: str, rank: str) -> bool:
    """Check if a card exists in a hand string like 'S:xxx H:xxx D:xxx C:xxx'"""
    suit_map = {'S': 'S:', 'H': 'H:', 'D': 'D:', 'C': 'C:'}
    prefix = suit_map.get(suit)
    if not prefix:
        return False

    # Find the suit section
    match = re.search(rf'{prefix}([^\s]*)', hand)
    if not match:
        return False

    return rank in match.group(1)


def remove_card_from_hand(hand: str, suit: str, rank: str) -> str:
    """Remove a card from a hand string."""
    suit_map = {'S': 'S:', 'H': 'H:', 'D': 'D:', 'C': 'C:'}
    prefix = suit_map.get(suit)
    if not prefix:
        return hand

    def replacer(m):
        cards = m.group(1)
        cards = cards.replace(rank, '', 1)
        return prefix + cards

    return re.sub(rf'{prefix}([^\s]*)', replacer, hand)


def add_card_to_hand(hand: str, suit: str, rank: str) -> str:
    """Add a card to a hand string, maintaining rank order."""
    suit_map = {'S': 'S:', 'H': 'H:', 'D': 'D:', 'C': 'C:'}
    prefix = suit_map.get(suit)
    if not prefix:
        return hand

    rank_order = 'AKQJT98765432'

    def replacer(m):
        cards = m.group(1)
        # Find correct position for the new rank
        new_cards = ''
        inserted = False
        for c in cards:
            if not inserted and rank_order.index(rank) < rank_order.index(c):
                new_cards += rank
                inserted = True
            new_cards += c
        if not inserted:
            new_cards += rank
        return prefix + new_cards

    return re.sub(rf'{prefix}([^\s]*)', replacer, hand)


def exchange_cards(row: dict, card1_str: str, card2_str: str) -> bool:
    """
    Exchange two cards between hands.
    Returns True if successful, False otherwise.
    """
    suit1, rank1 = parse_card(card1_str)
    suit2, rank2 = parse_card(card2_str)

    if not suit1 or not suit2:
        print(f"Warning: Invalid card format: {card1_str}-{card2_str}", file=sys.stderr)
        return False

    hand_cols = ['NorthHand', 'EastHand', 'SouthHand', 'WestHand']

    # Find which hands have each card
    hand1_col = None
    hand2_col = None

    for col in hand_cols:
        hand = row.get(col, '')
        if find_card_in_hand(hand, suit1, rank1):
            hand1_col = col
        if find_card_in_hand(hand, suit2, rank2):
            hand2_col = col

    if not hand1_col:
        print(f"Warning: Card {card1_str} not found in any hand", file=sys.stderr)
        return False
    if not hand2_col:
        print(f"Warning: Card {card2_str} not found in any hand", file=sys.stderr)
        return False

    if hand1_col == hand2_col:
        # Both cards in same hand - just swap them within the hand
        # This is a no-op for the hand content, but validates the cards exist
        return True

    # Remove cards from original hands
    row[hand1_col] = remove_card_from_hand(row[hand1_col], suit1, rank1)
    row[hand2_col] = remove_card_from_hand(row[hand2_col], suit2, rank2)

    # Add cards to swapped hands
    row[hand1_col] = add_card_to_hand(row[hand1_col], suit2, rank2)
    row[hand2_col] = add_card_to_hand(row[hand2_col], suit1, rank1)

    return True


def apply_dealer_correction(row: dict, new_dealer: str) -> bool:
    """
    Change the dealer to the specified seat.
    Also trims the auction to remove leading bids from original dealer to new dealer.
    """
    new_dealer = new_dealer.strip().upper()
    seat_map = {'N': 'North', 'E': 'East', 'S': 'South', 'W': 'West',
                'NORTH': 'North', 'EAST': 'East', 'SOUTH': 'South', 'WEST': 'West'}
    seat_order = ['N', 'E', 'S', 'W']

    if new_dealer not in seat_map:
        print(f"Warning: Invalid dealer: {new_dealer}", file=sys.stderr)
        return False

    # Normalize new dealer to single letter
    new_dealer_letter = new_dealer[0]

    # Get original dealer
    old_dealer = row.get('Dealer', 'North')
    old_dealer_letter = old_dealer[0].upper()

    # Calculate how many bids to remove
    old_idx = seat_order.index(old_dealer_letter) if old_dealer_letter in seat_order else 0
    new_idx = seat_order.index(new_dealer_letter)
    bids_to_remove = (new_idx - old_idx) % 4

    # Trim auction if needed
    if bids_to_remove > 0:
        auction = row.get('Auction', '')
        if auction:
            # Parse auction: split by spaces, respecting | separators
            # Format: "bid bid | bid bid | bid"
            parts = auction.replace('|', ' | ').split()
            # Remove pipe markers temporarily, count actual bids
            bids = [p for p in parts if p != '|']

            if len(bids) >= bids_to_remove:
                # Remove the first N bids
                remaining_bids = bids[bids_to_remove:]

                # Reconstruct with pipe separators every 4 bids
                new_auction_parts = []
                for i, bid in enumerate(remaining_bids):
                    if i > 0 and i % 4 == 0:
                        new_auction_parts.append('|')
                    new_auction_parts.append(bid)

                row['Auction'] = ' '.join(new_auction_parts)

    row['Dealer'] = seat_map[new_dealer]
    return True


def make_board_id(row: dict) -> str:
    """Create board ID from subfolder and deal number."""
    subfolder = row.get('Subfolder', '')
    deal_num = row.get('DealNumber', '')
    return f"{subfolder}-{deal_num}"


def main():
    # Parse arguments
    input_path = DEFAULT_INPUT
    corrections_path = DEFAULT_CORRECTIONS
    output_path = DEFAULT_OUTPUT

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == '--input' and i + 1 < len(args):
            input_path = Path(args[i + 1])
            i += 2
        elif args[i] == '--corrections' and i + 1 < len(args):
            corrections_path = Path(args[i + 1])
            i += 2
        elif args[i] == '--output' and i + 1 < len(args):
            output_path = Path(args[i + 1])
            i += 2
        else:
            i += 1

    if not input_path.exists():
        print(f"Error: {input_path} not found", file=sys.stderr)
        sys.exit(1)

    # Load corrections
    corrections = parse_corrections(corrections_path)
    print(f"Loaded {len(corrections)} board corrections from {corrections_path}")

    # Count correction types
    dealer_count = 0
    exchange_count = 0
    allow_count = 0

    # Process CSV
    rows = []
    with open(input_path, 'r', encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames

        for row in reader:
            board_id = make_board_id(row)

            if board_id in corrections:
                for correction in corrections[board_id]:
                    if correction.upper().startswith('DEALER'):
                        # Dealer X
                        parts = correction.split()
                        if len(parts) >= 2:
                            if apply_dealer_correction(row, parts[1]):
                                dealer_count += 1
                                print(f"  {board_id}: Dealer -> {parts[1]}")

                    elif correction.upper().startswith('EXCHANGE'):
                        # Exchange XX-YY
                        match = re.search(r'EXCHANGE\s+(\w+)-(\w+)', correction, re.IGNORECASE)
                        if match:
                            if exchange_cards(row, match.group(1), match.group(2)):
                                exchange_count += 1
                                print(f"  {board_id}: Exchange {match.group(1)}-{match.group(2)}")

                    elif correction.upper() == 'ALLOWAUCTION':
                        allow_count += 1
                        # Handled by create_full_pbn.py

            rows.append(row)

    # Write output
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nApplied corrections:")
    print(f"  Dealer changes: {dealer_count}")
    print(f"  Card exchanges: {exchange_count}")
    print(f"  AllowAuction (for PBN): {allow_count}")
    print(f"\nOutput: {output_path}")


if __name__ == '__main__':
    main()

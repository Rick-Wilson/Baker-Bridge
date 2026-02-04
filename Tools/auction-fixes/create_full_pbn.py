#!/usr/bin/env python3
"""
create_full_pbn.py - Create a single PBN file from BakerBridgeFull.csv

Compares against BakerBridge.csv to identify which hands were filled by
fill_hands.py and adds a [Fill] tag to those deals.

Usage:
    python3 create_full_pbn.py [--output FILE]

Output:
    BakerBridgeFull.pbn (or specified output file)
"""

import csv
import re
import sys
from pathlib import Path

# Default paths
SCRIPT_DIR = Path(__file__).parent.resolve()
TOOLS_DIR = SCRIPT_DIR.parent  # Parent folder contains the CSV files
ORIGINAL_CSV = TOOLS_DIR / "BakerBridge-sme.csv"
FULL_CSV = TOOLS_DIR / "BakerBridgeFull.csv"
DEFAULT_OUTPUT = SCRIPT_DIR / "BakerBridgeFull.pbn"
SME_CORRECTIONS = SCRIPT_DIR / "sme_corrections.txt"


def load_auction_corrections(path: Path) -> tuple[set, set]:
    """
    Load board IDs that have AllowAuction or UseBBAAuction corrections.
    Returns (allow_boards, use_bba_boards) tuple of sets.
    """
    allow_boards = set()
    use_bba_boards = set()
    if not path.exists():
        return allow_boards, use_bba_boards

    with open(path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            # Parse: BoardID - CorrectionType
            match = re.match(r'^([^\s-]+(?:/[^\s-]+)?-\d+)\s*-\s*(.+)$', line)
            if match:
                board_id = match.group(1)
                correction = match.group(2).strip().upper()
                if correction == 'ALLOWAUCTION':
                    allow_boards.add(board_id)
                elif correction == 'USEBBAAUCTION':
                    use_bba_boards.add(board_id)

    return allow_boards, use_bba_boards


def load_original_hands(path: Path) -> dict:
    """
    Load original hands from BakerBridge.csv.
    Returns dict: {(subfolder, deal_num): {'N': hand, 'E': hand, 'S': hand, 'W': hand}}
    """
    hands = {}
    if not path.exists():
        return hands

    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (row.get('Subfolder', ''), row.get('DealNumber', ''))
            hands[key] = {
                'N': row.get('NorthHand', ''),
                'E': row.get('EastHand', ''),
                'S': row.get('SouthHand', ''),
                'W': row.get('WestHand', '')
            }
    return hands


def convert_hand_to_pbn(hand: str) -> str:
    """
    Convert hand from 'S:xxx H:xxx D:xxx C:xxx' format to PBN format 'xxxx.xxxx.xxxx.xxxx'
    """
    if not hand:
        return "..."

    suits = {'S': '', 'H': '', 'D': '', 'C': ''}

    # Parse the hand string
    parts = hand.split()
    for part in parts:
        if ':' in part:
            suit, cards = part.split(':', 1)
            suit = suit.upper()
            if suit in suits:
                # Convert T to 10-style or keep as T (PBN uses T for 10)
                suits[suit] = cards

    # Return in PBN order: Spades.Hearts.Diamonds.Clubs
    return f"{suits['S']}.{suits['H']}.{suits['D']}.{suits['C']}"


def dealer_to_pbn(dealer: str) -> str:
    """Convert dealer string to single letter."""
    if not dealer:
        return 'N'
    d = dealer.strip().upper()
    if d in ('N', 'NORTH'):
        return 'N'
    elif d in ('E', 'EAST'):
        return 'E'
    elif d in ('S', 'SOUTH'):
        return 'S'
    elif d in ('W', 'WEST'):
        return 'W'
    return 'N'


def get_filled_seats(original: dict, full_row: dict) -> list:
    """
    Compare original hands with full row to find which seats were filled.
    Returns list of filled seat letters, e.g., ['E', 'W']
    """
    filled = []
    seat_cols = [('N', 'NorthHand'), ('E', 'EastHand'), ('S', 'SouthHand'), ('W', 'WestHand')]

    for seat, col in seat_cols:
        orig_hand = original.get(seat, '')
        full_hand = full_row.get(col, '')
        if full_hand != orig_hand:
            filled.append(seat)

    return filled


def format_auction_for_pbn(auction: str) -> list:
    """
    Format auction string for PBN output.
    Returns list of lines, each with up to 4 bids.
    """
    if not auction:
        return []

    # Normalize bids
    bids = auction.split()
    normalized = []
    for bid in bids:
        bid_upper = bid.upper()
        if bid_upper in ('PASS', 'P', '-'):
            normalized.append('Pass')
        elif bid_upper in ('X', 'DBL', 'DOUBLE'):
            normalized.append('X')
        elif bid_upper in ('XX', 'RDBL', 'REDOUBLE'):
            normalized.append('XX')
        elif len(bid) == 2 and bid[0].isdigit() and bid[1].upper() == 'N':
            normalized.append(bid[0] + 'NT')
        else:
            # Capitalize suit letter
            if len(bid) >= 2 and bid[0].isdigit():
                normalized.append(bid[0] + bid[1:].upper())
            else:
                normalized.append(bid)

    # Group into lines of 4 bids each
    lines = []
    for i in range(0, len(normalized), 4):
        line_bids = normalized[i:i+4]
        lines.append(' '.join(line_bids))

    return lines


def main():
    # Parse arguments
    output_path = DEFAULT_OUTPUT

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == '--output' and i + 1 < len(args):
            output_path = Path(args[i + 1])
            i += 2
        else:
            i += 1

    # Load original hands for comparison
    print(f"Loading original hands from {ORIGINAL_CSV}...")
    original_hands = load_original_hands(ORIGINAL_CSV)
    print(f"  Loaded {len(original_hands)} original deals")

    # Load auction corrections from SME corrections
    allow_auction_boards, use_bba_boards = load_auction_corrections(SME_CORRECTIONS)
    print(f"  Loaded {len(allow_auction_boards)} AllowAuction entries")
    print(f"  Loaded {len(use_bba_boards)} UseBBAAuction entries")

    # Process full CSV and create PBN
    print(f"Processing {FULL_CSV}...")

    pbn_lines = ['% PBN 2.1', '% Generated from BakerBridgeFull.csv', '']

    board_num = 0
    filled_count = 0
    allow_count = 0
    use_bba_count = 0

    with open(FULL_CSV, 'r', encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(f)

        for row in reader:
            board_num += 1

            subfolder = row.get('Subfolder', '')
            deal_num = row.get('DealNumber', '')
            dealer = dealer_to_pbn(row.get('Dealer', 'North'))

            # Get hands
            north = convert_hand_to_pbn(row.get('NorthHand', ''))
            east = convert_hand_to_pbn(row.get('EastHand', ''))
            south = convert_hand_to_pbn(row.get('SouthHand', ''))
            west = convert_hand_to_pbn(row.get('WestHand', ''))

            # Build deal string (PBN format: starts with dealer's hand)
            deal = f"N:{north} {east} {south} {west}"

            # Get auction (clean up separators)
            auction = row.get('Auction', '').replace('|', '').strip()

            # Check if any hands were filled
            key = (subfolder, deal_num)
            original = original_hands.get(key, {})
            filled_seats = get_filled_seats(original, row)

            # Use subfolder-dealnumber as board identifier for correlation
            board_id = f"{subfolder}-{deal_num}"

            # Write board
            pbn_lines.append(f'[Board "{board_id}"]')
            pbn_lines.append(f'[Dealer "{dealer}"]')
            pbn_lines.append(f'[Vulnerable "None"]')
            pbn_lines.append(f'[Deal "{deal}"]')

            # Add Fill tag if hands were filled
            if filled_seats:
                fill_str = ''.join(filled_seats)
                pbn_lines.append(f'[Fill "{fill_str}"]')
                filled_count += 1

            # Add AllowAuction tag if marked by SME
            if board_id in allow_auction_boards:
                pbn_lines.append('[AllowAuction "Y"]')
                allow_count += 1

            # Add UseBBAAuction tag if marked by SME
            if board_id in use_bba_boards:
                pbn_lines.append('[UseBBAAuction "Y"]')
                use_bba_count += 1

            # Add original Baker Bridge auction as a tag value (not free-form bids)
            auction_str = ' '.join(format_auction_for_pbn(auction))
            pbn_lines.append(f'[ExpectedAuction "{auction_str}"]')

            # Add empty auction tag for BBA to fill
            pbn_lines.append(f'[Auction "{dealer}"]')
            pbn_lines.append('')  # Empty line between boards

    # Write output
    with open(output_path, 'w') as f:
        f.write('\n'.join(pbn_lines))

    print(f"\nCreated {output_path}")
    print(f"  Total boards: {board_num}")
    print(f"  Boards with filled hands: {filled_count}")
    print(f"  Boards with AllowAuction: {allow_count}")
    print(f"  Boards with UseBBAAuction: {use_bba_count}")


if __name__ == '__main__':
    main()

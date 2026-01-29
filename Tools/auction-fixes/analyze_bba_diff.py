#!/usr/bin/env python3
"""
analyze_bba_diff.py - Analyze differences between expected and BBA auctions

Reads BakerBridgeFull-bba.pbn and compares ExpectedAuction with Auction tags.
Produces a summary table by subfolder.

Usage:
    python3 analyze_bba_diff.py [--input FILE]
"""

import re
import sys
from collections import defaultdict
from pathlib import Path

TOOLS_DIR = Path(__file__).parent.resolve()
DEFAULT_INPUT = TOOLS_DIR / "BakerBridgeFull-bba.pbn"


def normalize_bid(bid: str) -> str:
    """Normalize a bid for comparison."""
    bid = bid.upper().strip()
    if bid in ('PASS', 'P', '-'):
        return 'PASS'
    elif bid in ('X', 'DBL', 'DOUBLE'):
        return 'X'
    elif bid in ('XX', 'RDBL', 'REDOUBLE'):
        return 'XX'
    elif len(bid) == 2 and bid[0].isdigit() and bid[1] == 'N':
        return bid[0] + 'NT'
    return bid


def parse_auction(auction_str: str) -> list:
    """Parse auction string into list of normalized bids."""
    if not auction_str:
        return []
    # Remove annotations like =1=, =2=
    auction_str = re.sub(r'=[0-9]+=', '', auction_str)
    bids = auction_str.split()
    return [normalize_bid(b) for b in bids if b and not b.startswith('=')]


def get_opening_bid(auction: list) -> str:
    """Get the first non-pass bid from an auction."""
    for bid in auction:
        if bid != 'PASS':
            return bid
    return 'ALLPASS'


def get_opening_info(auction: list, dealer: str) -> tuple:
    """
    Get opening bid info including seat position.
    Returns (seat, bid) where seat is W/N/E/S and bid is the opening or 'PASS' if that seat passed.
    """
    seats = ['N', 'E', 'S', 'W']
    dealer_idx = seats.index(dealer.upper()) if dealer.upper() in seats else 0

    for i, bid in enumerate(auction):
        seat = seats[(dealer_idx + i) % 4]
        if bid != 'PASS':
            return (seat, bid)
    return (None, 'ALLPASS')


def format_opening_change(expected: list, bba: list, dealer: str) -> str:
    """
    Format a description of how the opening bid changed.
    Shows when a pass became an opening or vice versa.
    """
    seats = ['N', 'E', 'S', 'W']
    dealer_idx = seats.index(dealer.upper()) if dealer.upper() in seats else 0

    exp_seat, exp_bid = get_opening_info(expected, dealer)
    bba_seat, bba_bid = get_opening_info(bba, dealer)

    if exp_seat == bba_seat:
        # Same opener, different bid
        return f"{exp_seat}:{exp_bid}->{bba_bid}"
    else:
        # Different opener - show the first seat that changed
        max_len = max(len(expected), len(bba))
        for i in range(max_len):
            seat = seats[(dealer_idx + i) % 4]
            exp_b = expected[i] if i < len(expected) else ''
            bba_b = bba[i] if i < len(bba) else ''

            if exp_b != bba_b:
                if exp_b == 'PASS' and bba_b and bba_b != 'PASS':
                    return f"{seat}:Pass->{bba_b}"
                elif bba_b == 'PASS' and exp_b and exp_b != 'PASS':
                    return f"{seat}:{exp_b}->Pass"
                elif exp_b and bba_b:
                    return f"{seat}:{exp_b}->{bba_b}"
                break

        return f"{exp_bid}->{bba_bid}"


def auctions_match(expected: list, actual: list) -> bool:
    """Check if two auctions match."""
    return expected == actual


def get_seat_for_bid(dealer: str, bid_index: int) -> str:
    """Get the seat that made a bid at given index, based on dealer."""
    seat_order = {'N': 'NESW', 'E': 'ESWN', 'S': 'SWNE', 'W': 'WNES'}
    order = seat_order.get(dealer, 'NESW')
    return order[bid_index % 4]


def find_first_diff_seat(expected: list, actual: list, dealer: str) -> str:
    """
    Find the seat that made the first different bid.
    Returns the seat letter or empty string if auctions match.
    """
    max_len = max(len(expected), len(actual))
    for i in range(max_len):
        exp_bid = expected[i] if i < len(expected) else ''
        act_bid = actual[i] if i < len(actual) else ''
        if exp_bid != act_bid:
            return get_seat_for_bid(dealer, i)
    return ''


def parse_pbn_file(path: Path) -> list:
    """
    Parse PBN file and extract board data.
    Returns list of dicts with board_id, subfolder, expected_auction, bba_auction.
    """
    with open(path, 'r') as f:
        content = f.read()

    boards = []
    # Split by board
    board_sections = re.split(r'\[Board "([^"]+)"\]', content)[1:]

    # Process pairs (board_id, content)
    for i in range(0, len(board_sections), 2):
        if i + 1 >= len(board_sections):
            break

        board_id = board_sections[i]
        board_content = board_sections[i + 1]

        # Parse subfolder from board_id (format: subfolder-dealnumber)
        if '-' in board_id:
            parts = board_id.rsplit('-', 1)
            subfolder = parts[0]
        else:
            subfolder = 'Unknown'

        # Extract ExpectedAuction
        expected_match = re.search(r'\[ExpectedAuction "([^"]*)"\]', board_content)
        expected_str = expected_match.group(1) if expected_match else ''

        # Extract BBA Auction (the actual auction after [Auction "X"])
        auction_match = re.search(r'\[Auction "[^"]+"\]\n(.*?)(?:\n\[|\Z)', board_content, re.DOTALL)
        if auction_match:
            auction_text = auction_match.group(1).strip()
            # Parse bids from auction lines
            bba_bids = []
            for line in auction_text.split('\n'):
                if line.startswith('['):
                    break
                bba_bids.extend(line.split())
            bba_str = ' '.join(bba_bids)
        else:
            bba_str = ''

        # Check for Fill tag
        fill_match = re.search(r'\[Fill "([^"]*)"\]', board_content)
        filled = fill_match.group(1) if fill_match else ''

        # Extract dealer
        dealer_match = re.search(r'\[Dealer "([^"]*)"\]', board_content)
        dealer = dealer_match.group(1) if dealer_match else 'N'

        # Check for AllowAuction tag
        allow_match = re.search(r'\[AllowAuction "([^"]*)"\]', board_content)
        allow_auction = allow_match.group(1).upper() == 'Y' if allow_match else False

        # Check for UseBBAAuction tag
        use_bba_match = re.search(r'\[UseBBAAuction "([^"]*)"\]', board_content)
        use_bba_auction = use_bba_match.group(1).upper() == 'Y' if use_bba_match else False

        boards.append({
            'board_id': board_id,
            'subfolder': subfolder,
            'expected': expected_str,
            'bba': bba_str,
            'filled': filled,
            'dealer': dealer,
            'allow_auction': allow_auction,
            'use_bba_auction': use_bba_auction
        })

    return boards


def main():
    # Parse arguments
    input_path = DEFAULT_INPUT

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == '--input' and i + 1 < len(args):
            input_path = Path(args[i + 1])
            i += 2
        else:
            i += 1

    if not input_path.exists():
        print(f"Error: {input_path} not found", file=sys.stderr)
        sys.exit(1)

    print(f"Analyzing {input_path}...")
    boards = parse_pbn_file(input_path)
    print(f"Parsed {len(boards)} boards\n")

    # Analyze by subfolder
    stats = defaultdict(lambda: {
        'total': 0,
        'matches': 0,
        'different': 0,
        'opening_diff': 0,
        'fill_caused': 0,
        'allow_auction': 0,
        'use_bba_auction': 0,
        'opening_mismatches': defaultdict(int)
    })

    for board in boards:
        subfolder = board['subfolder']
        expected = parse_auction(board['expected'])
        bba = parse_auction(board['bba'])
        filled = board['filled']
        dealer = board['dealer']
        allow_auction = board.get('allow_auction', False)
        use_bba_auction = board.get('use_bba_auction', False)

        stats[subfolder]['total'] += 1

        # AllowAuction boards count as matches (SME approved the auction)
        if allow_auction:
            stats[subfolder]['allow_auction'] += 1
            stats[subfolder]['matches'] += 1
            continue

        # UseBBAAuction boards count as matches (BBA auction replaces expected)
        if use_bba_auction:
            stats[subfolder]['use_bba_auction'] += 1
            stats[subfolder]['matches'] += 1
            continue

        if auctions_match(expected, bba):
            stats[subfolder]['matches'] += 1
        else:
            stats[subfolder]['different'] += 1

            # Check if first different bid was by a filled seat
            if filled:
                first_diff_seat = find_first_diff_seat(expected, bba, dealer)
                if first_diff_seat and first_diff_seat in filled:
                    stats[subfolder]['fill_caused'] += 1

            # Check opening bid
            expected_open = get_opening_bid(expected)
            bba_open = get_opening_bid(bba)

            if expected_open != bba_open:
                stats[subfolder]['opening_diff'] += 1
                mismatch_key = format_opening_change(expected, bba, dealer)
                stats[subfolder]['opening_mismatches'][mismatch_key] += 1

    # Sort subfolders
    sorted_subfolders = sorted(stats.keys())

    # Print table header
    print(f"{'Subfolder':<20} {'Deals':>6} {'%Mat':>6} {'Match':>6} {'Diff':>6} {'%Fill':>6} {'Open':>6} {'Top Opening Mismatch':<25} {'Count':>5}")
    print("-" * 105)

    # Print rows
    total_deals = 0
    total_matches = 0
    total_diff = 0
    total_open = 0
    total_fill = 0
    total_allow = 0
    total_use_bba = 0

    for subfolder in sorted_subfolders:
        s = stats[subfolder]
        total_deals += s['total']
        total_matches += s['matches']
        total_diff += s['different']
        total_open += s['opening_diff']
        total_fill += s['fill_caused']
        total_allow += s['allow_auction']
        total_use_bba += s['use_bba_auction']

        # Calculate percentages
        match_pct = 100.0 * s['matches'] / s['total'] if s['total'] > 0 else 0
        fill_pct = 100.0 * s['fill_caused'] / s['different'] if s['different'] > 0 else 0

        # Find most common opening mismatch
        if s['opening_mismatches']:
            top_mismatch = max(s['opening_mismatches'].items(), key=lambda x: x[1])
            top_str = top_mismatch[0]
            top_count = top_mismatch[1]
        else:
            top_str = '-'
            top_count = 0

        print(f"{subfolder:<20} {s['total']:>6} {match_pct:>5.0f}% {s['matches']:>6} {s['different']:>6} {fill_pct:>5.0f}% {s['opening_diff']:>6} {top_str:<25} {top_count:>5}")

    # Print totals
    print("-" * 105)
    total_match_pct = 100.0 * total_matches / total_deals if total_deals > 0 else 0
    total_fill_pct = 100.0 * total_fill / total_diff if total_diff > 0 else 0
    print(f"{'TOTAL':<20} {total_deals:>6} {total_match_pct:>5.0f}% {total_matches:>6} {total_diff:>6} {total_fill_pct:>5.0f}% {total_open:>6}")

    # Print match percentage
    if total_deals > 0:
        match_pct = 100.0 * total_matches / total_deals
        print(f"\nOverall match rate: {match_pct:.1f}%")
        if total_allow > 0 or total_use_bba > 0:
            print(f"  (includes {total_allow} AllowAuction, {total_use_bba} UseBBAAuction boards)")

    # Print top opening mismatches overall
    print("\n" + "=" * 50)
    print("TOP OPENING BID MISMATCHES (Overall)")
    print("=" * 50)

    all_mismatches = defaultdict(int)
    for subfolder in stats:
        for mismatch, count in stats[subfolder]['opening_mismatches'].items():
            all_mismatches[mismatch] += count

    sorted_mismatches = sorted(all_mismatches.items(), key=lambda x: -x[1])[:15]
    for mismatch, count in sorted_mismatches:
        print(f"  {mismatch:<20} {count:>5}")


if __name__ == '__main__':
    main()

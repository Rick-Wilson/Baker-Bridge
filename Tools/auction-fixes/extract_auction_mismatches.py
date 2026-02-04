#!/usr/bin/env python3
"""
extract_auction_mismatches.py - Extract boards with auction mismatches (non-fill only)

Reads BakerBridgeFull-bba.pbn and creates a new PBN file with only boards
where any bid differs between expected and BBA auctions.
Only includes boards with no filled hands.

Usage:
    python3 extract_auction_mismatches.py [--input FILE] [--output FILE] [--no-pdf]
"""

import re
import subprocess
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).parent.resolve()
DEFAULT_INPUT = TOOLS_DIR / "BakerBridgeFull-bba.pbn"
DEFAULT_OUTPUT = TOOLS_DIR / "auction_mismatches.pbn"
PBN_TO_PDF = Path.home() / "Development/GitHub/pbn-to-pdf/target/release/pbn-to-pdf"


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


def auctions_match(expected: list, actual: list) -> bool:
    """Check if two auctions match exactly."""
    return expected == actual


def find_first_diff_index(expected: list, bba: list) -> int:
    """Find the index of the first differing bid between two auctions."""
    max_len = max(len(expected), len(bba))
    for i in range(max_len):
        exp_bid = expected[i] if i < len(expected) else ''
        bba_bid = bba[i] if i < len(bba) else ''
        if exp_bid != bba_bid:
            return i
    return -1


def get_seat_for_bid(dealer: str, bid_index: int) -> str:
    """Get the seat that made a bid at given index, based on dealer."""
    seat_order = {'N': 'NESW', 'E': 'ESWN', 'S': 'SWNE', 'W': 'WNES'}
    order = seat_order.get(dealer, 'NESW')
    return order[bid_index % 4]


def format_bid_change(expected: list, bba: list, dealer: str) -> str:
    """
    Format a description of how the auction changed.
    Shows the first differing bid with seat.
    """
    diff_index = find_first_diff_index(expected, bba)
    if diff_index < 0:
        return "Match"

    seat = get_seat_for_bid(dealer, diff_index)
    exp_bid = expected[diff_index] if diff_index < len(expected) else '(end)'
    bba_bid = bba[diff_index] if diff_index < len(bba) else '(end)'

    return f"Bid #{diff_index + 1} ({seat}): {exp_bid} -> {bba_bid}"


def format_auction_rows(auction_str: str, dealer: str = 'W', diff_index: int = -1) -> str:
    """
    Format auction string into rows of 4 bids for display.
    Pads with '-' placeholders based on dealer position since table starts with West.
    Uses blank lines as row separators.
    If diff_index >= 0, adds "?" after the bid at that index.
    """
    if not auction_str:
        return ''

    # Calculate padding needed (table order is W, N, E, S)
    dealer_offset = {'W': 0, 'N': 1, 'E': 2, 'S': 3}
    padding = dealer_offset.get(dealer.upper(), 0)

    # Split bids and mark the first different one
    raw_bids = auction_str.split()
    if diff_index >= 0 and diff_index < len(raw_bids):
        raw_bids[diff_index] = raw_bids[diff_index] + '?'

    # Add placeholder dashes for seats before dealer (4 chars to match "Pass" width)
    bids = ['----'] * padding + raw_bids

    rows = []
    for i in range(0, len(bids), 4):
        rows.append(' '.join(bids[i:i+4]))
    # Use double newlines (blank lines) since single newlines get collapsed
    return '\n\n'.join(rows)


def parse_boards(content: str) -> list:
    """
    Parse PBN content and extract full board sections.
    Returns list of dicts with board data.
    """
    boards = []
    # Split by board
    board_sections = re.split(r'(\[Board "[^"]+"\])', content)

    # Skip header (everything before first board)
    i = 1
    while i < len(board_sections):
        board_tag = board_sections[i]
        board_content = board_sections[i + 1] if i + 1 < len(board_sections) else ''

        # Extract board ID
        board_id_match = re.search(r'\[Board "([^"]+)"\]', board_tag)
        board_id = board_id_match.group(1) if board_id_match else 'Unknown'

        # Extract ExpectedAuction
        expected_match = re.search(r'\[ExpectedAuction "([^"]*)"\]', board_content)
        expected_str = expected_match.group(1) if expected_match else ''

        # Extract BBA Auction
        auction_match = re.search(r'\[Auction "[^"]+"\]\n(.*?)(?:\n\[|\Z)', board_content, re.DOTALL)
        if auction_match:
            auction_text = auction_match.group(1).strip()
            bba_bids = []
            for line in auction_text.split('\n'):
                if line.startswith('['):
                    break
                bba_bids.extend(line.split())
            bba_str = ' '.join(bba_bids)
        else:
            bba_str = ''

        # Extract dealer
        dealer_match = re.search(r'\[Dealer "([^"]*)"\]', board_content)
        dealer = dealer_match.group(1) if dealer_match else 'N'

        # Check for Fill tag
        fill_match = re.search(r'\[Fill "([^"]*)"\]', board_content)
        filled = fill_match.group(1) if fill_match else ''

        # Check for AllowAuction tag
        allow_match = re.search(r'\[AllowAuction "([^"]*)"\]', board_content)
        allow_auction = allow_match.group(1).upper() == 'Y' if allow_match else False

        # Check for UseBBAAuction tag
        use_bba_match = re.search(r'\[UseBBAAuction "([^"]*)"\]', board_content)
        use_bba_auction = use_bba_match.group(1).upper() == 'Y' if use_bba_match else False

        boards.append({
            'board_id': board_id,
            'board_tag': board_tag,
            'board_content': board_content,
            'expected': expected_str,
            'bba': bba_str,
            'dealer': dealer,
            'filled': filled,
            'allow_auction': allow_auction,
            'use_bba_auction': use_bba_auction
        })

        i += 2

    return boards


def reformat_board(board: dict, new_board_num: int) -> str:
    """
    Reformat a board for output:
    - Update board number
    - Move expected auction to comment after [Result ""]
    - Clean up for pbn-to-pdf compatibility
    """
    content = board['board_content']

    # Remove tags that pbn-to-pdf doesn't need
    content = re.sub(r'\[ExpectedAuction "[^"]*"\]\n?', '', content)
    content = re.sub(r'\[North "[^"]*"\]\n?', '', content)
    content = re.sub(r'\[East "[^"]*"\]\n?', '', content)
    content = re.sub(r'\[South "[^"]*"\]\n?', '', content)
    content = re.sub(r'\[West "[^"]*"\]\n?', '', content)
    content = re.sub(r'\[Room "[^"]*"\]\n?', '', content)
    content = re.sub(r'\[Scoring "[^"]*"\]\n?', '', content)
    content = re.sub(r'\[BidSystemEW "[^"]*"\]\n?', '', content)
    content = re.sub(r'\[BidSystemNS "[^"]*"\]\n?', '', content)
    content = re.sub(r'\[Play "[^"]*"\]\n\*\n?', '', content)

    # Create the comment with expected vs BBA
    expected = board['expected']
    bba = board['bba']
    dealer = board.get('dealer', 'N')

    # Find first differing bid index
    expected_bids = parse_auction(expected)
    bba_bids = parse_auction(bba)
    diff_index = find_first_diff_index(expected_bids, bba_bids)

    # Format expected auction with "?" marking the first different bid
    expected_rows = format_auction_rows(expected, dealer, diff_index)
    bid_change = format_bid_change(expected_bids, bba_bids, dealer)
    comment = f"{{Difference: {bid_change}.\n\nExpected:\n\n{expected_rows}}}"

    # Mark first different bid in BBA auction with "?"
    if diff_index >= 0:
        # Find and modify the auction in content
        auction_match = re.search(r'(\[Auction "[^"]+"\]\n)(.*?)(\n\[|\Z)', content, re.DOTALL)
        if auction_match:
            auction_prefix = auction_match.group(1)
            auction_text = auction_match.group(2)
            auction_suffix = auction_match.group(3)

            # Split auction into bids, mark the diff_index one
            auction_lines = auction_text.strip().split('\n')
            all_bids = []
            for line in auction_lines:
                all_bids.extend(line.split())

            if diff_index < len(all_bids):
                all_bids[diff_index] = all_bids[diff_index] + '?'

            # Reformat into rows of 4
            new_auction_lines = []
            for i in range(0, len(all_bids), 4):
                new_auction_lines.append(' '.join(all_bids[i:i+4]))
            new_auction_text = '\n'.join(new_auction_lines)

            content = content[:auction_match.start()] + auction_prefix + new_auction_text + auction_suffix

    # Check if [Result exists, if not add it after auction
    if '[Result "' not in content:
        content = content.rstrip() + f'\n[Result ""]\n{comment}\n'
    else:
        # Insert comment after existing [Result]
        content = re.sub(r'(\[Result "[^"]*"\])', r'\1\n' + comment, content)

    # Build new board with board ID in comment
    # Event must come before Board for pbn-to-pdf to recognize the board number
    board_id = board['board_id']
    new_board = f'[Event ""]\n[Board "{new_board_num}"]\n{{{board_id}}}\n'

    # Remove old board number, Fill tag, and clean up extra newlines
    content = re.sub(r'\[Board "[^"]+"\]\n?', '', content)
    content = re.sub(r'\[Fill "[^"]*"\]\n?', '', content)
    content = re.sub(r'\n{3,}', '\n\n', content)  # Collapse multiple newlines
    content = content.strip()

    return new_board + content + '\n'


def main():
    # Parse arguments
    input_path = DEFAULT_INPUT
    output_path = DEFAULT_OUTPUT
    generate_pdf = True

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == '--input' and i + 1 < len(args):
            input_path = Path(args[i + 1])
            i += 2
        elif args[i] == '--output' and i + 1 < len(args):
            output_path = Path(args[i + 1])
            i += 2
        elif args[i] == '--no-pdf':
            generate_pdf = False
            i += 1
        else:
            i += 1

    if not input_path.exists():
        print(f"Error: {input_path} not found", file=sys.stderr)
        sys.exit(1)

    print(f"Reading {input_path}...")
    with open(input_path, 'r') as f:
        content = f.read()

    boards = parse_boards(content)
    print(f"Parsed {len(boards)} boards")

    # Find auction mismatches (skip AllowAuction, UseBBAAuction, and filled boards)
    mismatches = []
    skipped_allow = 0
    skipped_use_bba = 0
    skipped_filled = 0
    skipped_match = 0

    for board in boards:
        # Skip boards marked as AllowAuction by SME
        if board.get('allow_auction', False):
            skipped_allow += 1
            continue

        # Skip boards marked as UseBBAAuction by SME
        if board.get('use_bba_auction', False):
            skipped_use_bba += 1
            continue

        # Skip boards with filled hands
        if board.get('filled', ''):
            skipped_filled += 1
            continue

        expected = parse_auction(board['expected'])
        bba = parse_auction(board['bba'])

        if auctions_match(expected, bba):
            skipped_match += 1
            continue

        mismatches.append(board)

    print(f"Found {len(mismatches)} auction mismatches (non-fill deals only)")
    print(f"  (skipped {skipped_allow} AllowAuction boards)")
    print(f"  (skipped {skipped_use_bba} UseBBAAuction boards)")
    print(f"  (skipped {skipped_filled} boards with filled hands)")
    print(f"  (skipped {skipped_match} matching auctions)")

    # Create output PBN
    pbn_lines = [
        '% PBN 2.1',
        '% Auction Mismatches - Expected vs BBA (non-fill deals only)',
        f'% Source: {input_path.name}',
        f'% Total mismatches: {len(mismatches)}',
        ''
    ]

    for i, board in enumerate(mismatches, 1):
        formatted = reformat_board(board, i)
        pbn_lines.append(formatted)

    # Write output
    with open(output_path, 'w') as f:
        f.write('\n'.join(pbn_lines))

    print(f"Created {output_path}")

    # Generate PDF
    if generate_pdf and len(mismatches) > 0 and PBN_TO_PDF.exists():
        pdf_path = output_path.with_suffix('.pdf')
        print(f"\nGenerating PDF: {pdf_path}")

        cmd = [
            str(PBN_TO_PDF),
            str(output_path),
            '-o', str(pdf_path),
            '--layout', 'analysis',
            '-n', '2',  # 2 boards per page
            '--orientation', 'portrait'
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"PDF created: {pdf_path}")
        else:
            print(f"PDF generation failed: {result.stderr}", file=sys.stderr)
    elif generate_pdf and len(mismatches) == 0:
        print("No mismatches to generate PDF for")
    elif generate_pdf:
        print(f"Warning: pbn-to-pdf not found at {PBN_TO_PDF}")


if __name__ == '__main__':
    main()

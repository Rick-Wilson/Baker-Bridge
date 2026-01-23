#!/usr/bin/env python3
"""
fill_hands.py - Mac replacement for Fill_Hands.ps1

Generates constrained hands for deals where East/West bid but have no cards.
Uses the dealer3 Rust binary instead of dealer.exe.

Usage:
    python3 fill_hands.py [--dealer PATH]

Output:
    constructed_hands.csv
"""

import csv
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

# Default path to dealer binary - adjust if needed
DEALER_PATH = Path.home() / "Development/GitHub/dealer3/target/release/dealer"

# Input/output files
MISSING_BIDS_PATH = "missing_bids.csv"
AUCTION_TEMPLATES_PATH = "auction_templates.dlr"
OUTPUT_CSV = "constructed_hands.csv"


def load_auction_templates(path: str) -> str:
    """Load auction templates file content (lowercased for matching)."""
    with open(path, 'r') as f:
        return f.read().lower()


def format_hand(hand_string: str) -> str:
    """
    Convert period-delimited hand string (Spades.Hearts.Diamonds.Clubs)
    into format: S:{cards} H:{cards} D:{cards} C:{cards}
    """
    suits = hand_string.split('.')
    if len(suits) == 4:
        return f"S:{suits[0]} H:{suits[1]} D:{suits[2]} C:{suits[3]}"
    else:
        print(f"Warning: Hand string '{hand_string}' does not have 4 parts", file=sys.stderr)
        return hand_string


def convert_hand_to_predeal(hand: str) -> str:
    """
    Convert hand from CSV format (S:xx H:xx D:xx C:xx) to dealer predeal format (Sxx,Hxx,Dxx,Cxx).
    """
    # Replace spaces with commas, remove colons
    return hand.replace(" ", ",").replace(":", "")


def swap_east_west(content: str) -> str:
    """Swap east and west references in template content."""
    content = content.replace("east", "__TEMP__")
    content = content.replace("west", "east")
    content = content.replace("__TEMP__", "west")
    return content


def run_dealer(script_content: str, dealer_path: Path) -> str | None:
    """Run dealer with the given script content and return the first line of output."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.dlr', delete=False) as f:
        f.write(script_content)
        temp_path = f.name

    try:
        result = subprocess.run(
            [str(dealer_path), temp_path],
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode != 0:
            print(f"Dealer error: {result.stderr}", file=sys.stderr)
            return None

        lines = result.stdout.strip().split('\n')
        return lines[0] if lines else None

    except subprocess.TimeoutExpired:
        print("Dealer timed out", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Error running dealer: {e}", file=sys.stderr)
        return None
    finally:
        os.unlink(temp_path)


def parse_dealer_output(line: str) -> dict | None:
    """
    Parse dealer printoneline output.
    Format: n {north} e {east} s {south} w {west}
    Where each hand is in period-delimited format (e.g., AK32.QJ5.T98.762)
    """
    pattern = r'^n\s*(?P<north>.*?)\s*e\s*(?P<east>.*?)\s*s\s*(?P<south>.*?)\s*w\s*(?P<west>.*)$'
    match = re.match(pattern, line, re.IGNORECASE)

    if match:
        return {
            'north': format_hand(match.group('north').strip()),
            'east': format_hand(match.group('east').strip()),
            'south': format_hand(match.group('south').strip()),
            'west': format_hand(match.group('west').strip()),
        }
    return None


def main():
    # Parse command line args
    dealer_path = DEALER_PATH
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == '--dealer' and i < len(sys.argv) - 1:
            dealer_path = Path(sys.argv[i + 1])

    # Check dealer exists
    if not dealer_path.exists():
        print(f"Error: dealer binary not found at {dealer_path}", file=sys.stderr)
        print("Use --dealer PATH to specify the location", file=sys.stderr)
        sys.exit(1)

    # Load auction templates
    if not os.path.exists(AUCTION_TEMPLATES_PATH):
        print(f"Error: {AUCTION_TEMPLATES_PATH} not found", file=sys.stderr)
        sys.exit(1)

    auction_templates = load_auction_templates(AUCTION_TEMPLATES_PATH)

    # Load missing bids
    if not os.path.exists(MISSING_BIDS_PATH):
        print(f"Error: {MISSING_BIDS_PATH} not found", file=sys.stderr)
        sys.exit(1)

    # Initialize output CSV
    with open(OUTPUT_CSV, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Subfolder', 'Deal', 'NorthHand', 'EastHand', 'SouthHand', 'WestHand', 'label'])

    # Track statistics
    unsupported_bid_sequences = set()
    unprocessed_hands = 0
    supported_hands = 0
    max_hands = 5000

    # Process each row
    with open(MISSING_BIDS_PATH, 'r') as f:
        reader = csv.DictReader(f)

        for row in reader:
            bid_sequence = row.get('BidSequence', '').strip()

            # Determine label
            if not bid_sequence:
                label = "auction_calm"
            else:
                modified_bid_sequence = bid_sequence.replace("-", "_")
                label = f"auction_{modified_bid_sequence}".lower()

            # Check if label exists in templates
            if label not in auction_templates:
                unsupported_bid_sequences.add(bid_sequence or "(empty)")
                unprocessed_hands += 1
                continue

            # Get template content, swap if needed
            template_content = auction_templates
            if row.get('Seat', '').lower() == 'east':
                template_content = swap_east_west(template_content)

            # Build dealer script
            script_lines = [
                "produce 1",
                "generate 100000",
                template_content,
            ]

            # Add predeal statements for existing hands
            for seat in ['North', 'South', 'East', 'West']:
                hand_key = f"{seat}Hand"
                hand = row.get(hand_key, '').strip()
                if hand:
                    predeal_hand = convert_hand_to_predeal(hand)
                    script_lines.append(f"predeal {seat.lower()} {predeal_hand}")

            script_lines.append(f"condition {label}")
            script_lines.append("action printoneline")

            script_content = '\n'.join(script_lines)

            # Run dealer
            output = run_dealer(script_content, dealer_path)

            if output and output.lower().startswith('n '):
                hands = parse_dealer_output(output)
                if hands:
                    # Append to CSV
                    with open(OUTPUT_CSV, 'a', newline='') as csvfile:
                        writer = csv.writer(csvfile)
                        writer.writerow([
                            row['Subfolder'],
                            row['Deal'],
                            hands['north'],
                            hands['east'],
                            hands['south'],
                            hands['west'],
                            label
                        ])
                    supported_hands += 1
                else:
                    print(f"Error: Could not parse dealer output '{output}' for {row['Subfolder']}/{row['Deal']}", file=sys.stderr)
            else:
                print(f"Error: dealer output does not start with 'n ' for {row['Subfolder']}/{row['Deal']}, label {label}. Output: {output}", file=sys.stderr)

            if supported_hands >= max_hands:
                print(f"Reached maximum supported hands ({max_hands}). Stopping.")
                break

    # Report statistics
    print(f"\nUnsupported bid sequences: {sorted(unsupported_bid_sequences)}")
    print(f"Total unprocessed hands: {unprocessed_hands}")
    print(f"Successfully processed {supported_hands} hands.")


if __name__ == '__main__':
    main()

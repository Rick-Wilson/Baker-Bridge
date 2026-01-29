#!/usr/bin/env python3
"""
fill_hands.py - Mac replacement for Fill_Hands.ps1

Generates constrained hands for deals where East/West bid but have no cards.
Uses the dealer3 Rust binary instead of dealer.exe.

With --validate-bba flag, generates multiple candidates and picks the one
where BBA's auction matches the expected auction.

Usage:
    python3 fill_hands.py [--dealer PATH] [--validate-bba] [--max-candidates N]

Output:
    constructed_hands.csv
"""

import csv
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

# Default path to dealer binary - adjust if needed
DEALER_PATH = Path.home() / "Development/GitHub/dealer3/target/release/dealer"

# Input/output files (defaults, can be overridden via args)
DEFAULT_MISSING_BIDS_PATH = "missing_bids.csv"
AUCTION_TEMPLATES_PATH = "auction_templates.dlr"
DEFAULT_OUTPUT_CSV = "constructed_hands.csv"
SOURCE_CSV = "BakerBridgeFull.csv"

# BBA configuration
PBS_BUILD_SCRIPTS = Path.home() / "Development/GitHub/Practice-Bidding-Scenarios/build-scripts-mac"
BBA_CLI_PATH = r"C:\BBA-CLI\bba-cli"
TOOLS_DIR = Path(__file__).parent.resolve()
NS_CONVENTION_PATH = TOOLS_DIR / "BAKER-BRIDGE.bbsa"
EW_CONVENTION_PATH = TOOLS_DIR / "BAKER-BRIDGE.bbsa"
BBA_TIMEOUT = 60


def load_auction_templates(path: str) -> str:
    """Load auction templates file content (lowercased for matching)."""
    with open(path, 'r') as f:
        return f.read().lower()


def load_expected_auctions(path: str) -> dict:
    """
    Load expected auctions and dealer info from source CSV.
    Returns dict: {(subfolder, deal_num): {'auction': str, 'dealer': str, 'vuln': str}}
    """
    auctions = {}
    if not os.path.exists(path):
        return auctions

    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(f)
        for row in reader:
            subfolder = row.get('Subfolder', '')
            deal_num = row.get('DealNumber', '')
            auction = row.get('Auction', '')
            dealer = row.get('Dealer', 'North')
            if subfolder and deal_num:
                # Clean up auction - remove | separators, normalize
                clean_auction = auction.replace('|', '').strip()
                # Convert dealer to single letter
                dealer_letter = dealer[0].upper() if dealer else 'N'
                auctions[(subfolder, deal_num)] = {
                    'auction': clean_auction,
                    'dealer': dealer_letter,
                    'vuln': 'None',  # Could parse from source if available
                }

    return auctions


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
    return hand.replace(" ", ",").replace(":", "")


def convert_hand_to_pbn(hand: str) -> str:
    """
    Convert hand from CSV format (S:xx H:xx D:xx C:xx) to PBN format (xxxx.xxxx.xxxx.xxxx).
    """
    # Parse S:xx H:xx D:xx C:xx format
    parts = hand.split()
    suits = {}
    for part in parts:
        if ':' in part:
            suit, cards = part.split(':', 1)
            suits[suit.upper()] = cards if cards else ''

    # Return in SHDC order with dots
    return f"{suits.get('S', '')}.{suits.get('H', '')}.{suits.get('D', '')}.{suits.get('C', '')}"


def swap_east_west(content: str) -> str:
    """Swap east and west references in template content."""
    content = content.replace("east", "__TEMP__")
    content = content.replace("west", "east")
    content = content.replace("__TEMP__", "west")
    return content


def run_dealer(script_content: str, dealer_path: Path, num_hands: int = 1) -> list[str]:
    """
    Run dealer with the given script content and return output lines.
    Returns list of hand lines (one per generated hand).
    """
    # Replace produce count
    script_content = re.sub(r'produce \d+', f'produce {num_hands}', script_content)

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
            return []

        lines = result.stdout.strip().split('\n')
        # Filter to only hand lines (start with 'n ')
        return [line for line in lines if line.lower().startswith('n ')]

    except subprocess.TimeoutExpired:
        print("Dealer timed out", file=sys.stderr)
        return []
    except Exception as e:
        print(f"Error running dealer: {e}", file=sys.stderr)
        return []
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


def normalize_auction(bids: list[str] | str) -> list[str]:
    """Normalize auction for comparison."""
    if isinstance(bids, str):
        bids = bids.split()

    result = []
    for bid in bids:
        bid = bid.upper().strip()
        if not bid:
            continue
        if bid in ("PASS", "P", "--", "AP"):
            result.append("PASS")
        elif bid in ("X", "DBL", "DOUBLE", "DB"):
            result.append("X")
        elif bid in ("XX", "RDBL", "REDOUBLE", "RD"):
            result.append("XX")
        elif len(bid) == 2 and bid[0].isdigit() and bid[1] == "N":
            result.append(bid[0] + "NT")
        else:
            result.append(bid)
    return result


def call_bba_batch(hands_list: list[dict], dealer: str, vulnerability: str,
                   run_windows_command, mac_to_windows_path) -> list[list[str]]:
    """
    Call BBA via ssh_runner to get auctions for multiple deals at once.

    Args:
        hands_list: list of dicts, each with 'north', 'east', 'south', 'west' hands
        dealer: 'N', 'E', 'S', or 'W'
        vulnerability: 'None', 'NS', 'EW', 'Both'
        run_windows_command: ssh_runner function
        mac_to_windows_path: path conversion function

    Returns:
        List of auctions (one per input hand), empty list on error
    """
    if not hands_list:
        return []

    # Build PBN file with all hands
    pbn_lines = ['% PBN 2.1']

    for i, hands in enumerate(hands_list, 1):
        n_pbn = convert_hand_to_pbn(hands['north'])
        e_pbn = convert_hand_to_pbn(hands['east'])
        s_pbn = convert_hand_to_pbn(hands['south'])
        w_pbn = convert_hand_to_pbn(hands['west'])
        pbn_deal = f"N:{n_pbn} {e_pbn} {s_pbn} {w_pbn}"

        pbn_lines.extend([
            f'[Board "{i}"]',
            f'[Dealer "{dealer}"]',
            f'[Vulnerable "{vulnerability}"]',
            f'[Deal "{pbn_deal}"]',
            f'[Auction "{dealer}"]',
            '',
        ])

    pbn_content = '\n'.join(pbn_lines)

    with tempfile.NamedTemporaryFile(mode='w', suffix='.pbn', delete=False,
                                      dir=str(Path.home() / "Development/GitHub/Baker-Bridge/Tools")) as f:
        f.write(pbn_content)
        input_path = f.name

    output_path = input_path.replace('.pbn', '-bba-out.pbn')

    try:
        # Convert paths
        input_win = mac_to_windows_path(input_path)
        output_win = mac_to_windows_path(output_path)
        ns_bbsa = mac_to_windows_path(str(NS_CONVENTION_PATH))
        ew_bbsa = mac_to_windows_path(str(EW_CONVENTION_PATH))

        # Build command
        cmd = (
            f'{BBA_CLI_PATH} --auto-update '
            f'--input "{input_win}" '
            f'--output "{output_win}" '
            f'--ns-conventions "{ns_bbsa}" '
            f'--ew-conventions "{ew_bbsa}"'
        )

        returncode, stdout, stderr = run_windows_command(
            cmd, timeout=BBA_TIMEOUT, verbose=False
        )

        if returncode != 0:
            return []

        # Parse output to get auctions for each board
        auctions = []
        if os.path.exists(output_path):
            with open(output_path, 'r') as f:
                content = f.read()

            # Split into boards and extract each auction
            boards = re.split(r'\[Board ', content)[1:]  # Skip header
            for board in boards:
                auction_match = re.search(r'\[Auction "[^"]+"\]\n(.*?)(?:\n\[|\Z)', board, re.DOTALL)
                if auction_match:
                    auction_text = auction_match.group(1).strip()
                    bids = []
                    for line in auction_text.split('\n'):
                        if line.startswith('['):
                            break
                        bids.extend(line.split())
                    auctions.append(bids)
                else:
                    auctions.append([])

        return auctions

    except Exception as e:
        return []
    finally:
        # Cleanup
        if os.path.exists(input_path):
            os.unlink(input_path)
        if os.path.exists(output_path):
            os.unlink(output_path)


def auctions_match(expected: str, actual: list[str]) -> bool:
    """Compare expected auction string with actual bid list."""
    expected_normalized = normalize_auction(expected)
    actual_normalized = normalize_auction(actual)
    return expected_normalized == actual_normalized


def main():
    # Parse command line args
    dealer_path = DEALER_PATH
    validate_bba = False
    max_candidates = 10
    missing_bids_path = DEFAULT_MISSING_BIDS_PATH
    output_csv = DEFAULT_OUTPUT_CSV

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == '--dealer' and i + 1 < len(args):
            dealer_path = Path(args[i + 1])
            i += 2
        elif args[i] == '--validate-bba':
            validate_bba = True
            i += 1
        elif args[i] == '--max-candidates' and i + 1 < len(args):
            max_candidates = int(args[i + 1])
            i += 2
        elif args[i] == '--input' and i + 1 < len(args):
            missing_bids_path = args[i + 1]
            i += 2
        elif args[i] == '--output' and i + 1 < len(args):
            output_csv = args[i + 1]
            i += 2
        else:
            i += 1

    # Check dealer exists
    if not dealer_path.exists():
        print(f"Error: dealer binary not found at {dealer_path}", file=sys.stderr)
        print("Use --dealer PATH to specify the location", file=sys.stderr)
        sys.exit(1)

    # Load ssh_runner if validating with BBA
    run_windows_command = None
    mac_to_windows_path = None
    if validate_bba:
        try:
            sys.path.insert(0, str(PBS_BUILD_SCRIPTS))
            from ssh_runner import run_windows_command, mac_to_windows_path
            print("BBA validation enabled")
        except ImportError as e:
            print(f"Error: Could not import ssh_runner: {e}", file=sys.stderr)
            print("Continuing without BBA validation", file=sys.stderr)
            validate_bba = False

    # Load auction templates
    if not os.path.exists(AUCTION_TEMPLATES_PATH):
        print(f"Error: {AUCTION_TEMPLATES_PATH} not found", file=sys.stderr)
        sys.exit(1)

    auction_templates = load_auction_templates(AUCTION_TEMPLATES_PATH)

    # Load expected auctions if validating
    expected_auctions = {}
    if validate_bba:
        expected_auctions = load_expected_auctions(SOURCE_CSV)
        print(f"Loaded {len(expected_auctions)} expected auctions from {SOURCE_CSV}")

    # Load missing bids
    if not os.path.exists(missing_bids_path):
        print(f"Error: {missing_bids_path} not found", file=sys.stderr)
        sys.exit(1)

    # Initialize output CSV
    with open(output_csv, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Subfolder', 'Deal', 'NorthHand', 'EastHand', 'SouthHand', 'WestHand', 'label'])

    # Track statistics
    unsupported_bid_sequences = set()
    unprocessed_hands = 0
    supported_hands = 0
    bba_matched = 0
    bba_unmatched = 0
    max_hands = 5000

    # Process each row
    with open(missing_bids_path, 'r') as f:
        reader = csv.DictReader(f)

        for row in reader:
            bid_sequence = row.get('BidSequence', '').strip()
            subfolder = row.get('Subfolder', '')
            deal_num = row.get('Deal', '')

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
                "produce 1",  # Will be replaced by run_dealer
                "generate 100000",
                template_content,
            ]

            # Add predeal statements for existing hands
            existing_hands = {}
            for seat in ['North', 'South', 'East', 'West']:
                hand_key = f"{seat}Hand"
                hand = row.get(hand_key, '').strip()
                if hand:
                    predeal_hand = convert_hand_to_predeal(hand)
                    script_lines.append(f"predeal {seat.lower()} {predeal_hand}")
                    existing_hands[seat.lower()] = hand

            script_lines.append(f"condition {label}")
            script_lines.append("action printoneline")

            script_content = '\n'.join(script_lines)

            # Get expected auction for BBA validation
            expected_info = expected_auctions.get((subfolder, deal_num), {})
            expected_auction = expected_info.get('auction', '')
            expected_dealer = expected_info.get('dealer', 'N')
            expected_vuln = expected_info.get('vuln', 'None')

            # Determine how many candidates to generate
            num_candidates = max_candidates if (validate_bba and expected_auction) else 1

            # Run dealer
            output_lines = run_dealer(script_content, dealer_path, num_candidates)

            if not output_lines:
                print(f"Error: No dealer output for {subfolder}/{deal_num}, label {label}", file=sys.stderr)
                continue

            # Parse all candidate hands
            all_hands = []
            for output_line in output_lines:
                hands = parse_dealer_output(output_line)
                if hands:
                    # Merge with existing hands
                    for seat, hand in existing_hands.items():
                        hands[seat] = hand
                    all_hands.append(hands)

            if not all_hands:
                print(f"Error: No valid hands parsed for {subfolder}/{deal_num}", file=sys.stderr)
                continue

            # Find best matching hand
            best_hands = all_hands[0]  # Default to first
            found_match = False

            if validate_bba and expected_auction:
                # Call BBA once for all candidates
                bba_auctions = call_bba_batch(all_hands, expected_dealer, expected_vuln,
                                              run_windows_command, mac_to_windows_path)

                # Find first matching auction
                for i, bba_auction in enumerate(bba_auctions):
                    if bba_auction and auctions_match(expected_auction, bba_auction):
                        best_hands = all_hands[i]
                        found_match = True
                        bba_matched += 1
                        break

            if best_hands:
                # Append to CSV
                with open(output_csv, 'a', newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow([
                        subfolder,
                        deal_num,
                        best_hands['north'],
                        best_hands['east'],
                        best_hands['south'],
                        best_hands['west'],
                        label
                    ])
                supported_hands += 1

                if validate_bba and expected_auction and not found_match:
                    bba_unmatched += 1
                    print(f"  No BBA match for {subfolder}/{deal_num} (used first candidate)", file=sys.stderr)
            else:
                print(f"Error: Could not generate hands for {subfolder}/{deal_num}", file=sys.stderr)

            if supported_hands >= max_hands:
                print(f"Reached maximum supported hands ({max_hands}). Stopping.")
                break

    # Report statistics
    print(f"\nUnsupported bid sequences: {sorted(unsupported_bid_sequences)}")
    print(f"Total unprocessed hands: {unprocessed_hands}")
    print(f"Successfully processed {supported_hands} hands.")

    if validate_bba:
        total_validated = bba_matched + bba_unmatched
        if total_validated > 0:
            print(f"\nBBA validation results:")
            print(f"  Matched: {bba_matched} ({100*bba_matched/total_validated:.1f}%)")
            print(f"  Unmatched: {bba_unmatched} ({100*bba_unmatched/total_validated:.1f}%)")


if __name__ == '__main__':
    main()

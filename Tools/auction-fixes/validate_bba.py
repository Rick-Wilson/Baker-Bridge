#!/usr/bin/env python3
"""
Validate Baker Bridge PBN hands by comparing auctions with BBA (Bridge Bidding Analyzer).

Uses bba-cli on Windows via SSH to rebid hands and compare with original auctions.

Usage:
    python validate_bba.py "Package/*.pbn"
    python validate_bba.py "Package/*.pbn" --limit 5
    python validate_bba.py "Package/2over1.pbn" --verbose

This script:
1. Reads PBN files matching the wildcard pattern
2. Calls bba-cli via SSH to rebid each file
3. Creates {filename}-bba.pbn with BBA's auctions
4. Creates {filename}-diff.txt if there are auction differences
"""
import os
import sys
import re
import glob
import argparse
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

# Add Practice-Bidding-Scenarios build-scripts-mac to path for ssh_runner
PBS_BUILD_SCRIPTS = os.path.expanduser(
    "~/Development/GitHub/Practice-Bidding-Scenarios/build-scripts-mac"
)
sys.path.insert(0, PBS_BUILD_SCRIPTS)

from ssh_runner import run_windows_command, mac_to_windows_path

# Configuration
BBA_CLI_PATH = r"C:\BBA-CLI\bba-cli"
BBSA_PATH = os.path.expanduser("~/Development/GitHub/Practice-Bidding-Scenarios/bbsa")
DEFAULT_NS_CONVENTION = "baker-bridge"
DEFAULT_EW_CONVENTION = "baker-bridge"
BBA_TIMEOUT = 300  # seconds


@dataclass
class Deal:
    """Parsed deal from PBN file."""
    board: str
    dealer: str
    vulnerability: str
    pbn: str
    auction: list[str]
    raw_block: str = ""


@dataclass
class ValidationResult:
    """Result of validating a single deal."""
    board: str
    reference_auction: list[str]
    bba_auction: list[str]
    match: bool
    error: Optional[str] = None


def parse_pbn_file(filepath: str) -> tuple[str, list[Deal]]:
    """
    Parse a PBN file and extract header and deals.

    Returns:
        Tuple of (header_text, list_of_deals)
    """
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    # Split header (lines starting with %) from deal blocks
    lines = content.split("\n")
    header_lines = []
    body_start = 0

    for i, line in enumerate(lines):
        if line.startswith("%") or (line.strip() == "" and i < 50):
            header_lines.append(line)
        else:
            body_start = i
            break

    header = "\n".join(header_lines)
    body = "\n".join(lines[body_start:])

    # Split into deal blocks
    blocks = re.split(r'\n(?=\[Board )', body)

    deals = []
    for block in blocks:
        if not block.strip():
            continue

        # Extract tags
        tags = {}
        for match in re.finditer(r'\[(\w+)\s+"([^"]*)"\]', block):
            tags[match.group(1)] = match.group(2)

        if "Board" not in tags or "Deal" not in tags:
            continue

        # Extract auction - first try [Auction] section, then fall back to [ExpectedAuction] tag
        auction_match = re.search(r'\[Auction "([^"]+)"\]\n(.*?)(?:\n\[|\n\{|\Z)', block, re.DOTALL)
        auction = []
        if auction_match:
            auction_text = auction_match.group(2)
            for line in auction_text.strip().split("\n"):
                if line.startswith("[") or line.startswith("{"):
                    break
                # Remove note markers and alerts
                line = re.sub(r'=\d+=', '', line)
                line = re.sub(r'\$\d+', '', line)
                bids = line.split()
                auction.extend(bids)

        # If no auction found in [Auction] section, use [ExpectedAuction] tag
        if not auction and "ExpectedAuction" in tags:
            auction = tags["ExpectedAuction"].split()

        deals.append(Deal(
            board=tags.get("Board", "0"),
            dealer=tags.get("Dealer", "N"),
            vulnerability=tags.get("Vulnerable", "None"),
            pbn=tags.get("Deal", ""),
            auction=auction,
            raw_block=block,
        ))

    return header, deals


def normalize_auction(bids: list[str]) -> list[str]:
    """Normalize auction for comparison."""
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


def format_auction(bids: list[str]) -> str:
    """Format auction for display."""
    if not bids:
        return "(none)"
    if len(bids) == 4 and all(b.upper() in ("PASS", "P", "--") for b in bids):
        return "PassOut"
    return " ".join(bids)


def create_limited_pbn(input_path: str, output_path: str, limit: int) -> int:
    """
    Create a PBN file with only the first N deals.

    Returns:
        Number of deals written
    """
    header, deals = parse_pbn_file(input_path)

    limited_deals = deals[:limit]

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(header)
        if not header.endswith("\n"):
            f.write("\n")
        f.write("\n")

        for deal in limited_deals:
            f.write(deal.raw_block)
            if not deal.raw_block.endswith("\n"):
                f.write("\n")
            f.write("\n")

    return len(limited_deals)


def run_bba_cli(input_path: str, output_path: str, ns_convention: str,
                ew_convention: str, verbose: bool = True) -> bool:
    """
    Run bba-cli on Windows via SSH.

    Args:
        input_path: Mac path to input PBN file
        output_path: Mac path to output PBN file
        ns_convention: NS convention card name (without .bbsa)
        ew_convention: EW convention card name (without .bbsa)
        verbose: Whether to print progress

    Returns:
        True if successful
    """
    # Convert paths to Windows format
    input_win = mac_to_windows_path(input_path)
    output_win = mac_to_windows_path(output_path)
    ns_bbsa = mac_to_windows_path(os.path.join(BBSA_PATH, f"{ns_convention}.bbsa"))
    ew_bbsa = mac_to_windows_path(os.path.join(BBSA_PATH, f"{ew_convention}.bbsa"))

    # Build command
    cmd = (
        f'{BBA_CLI_PATH} --auto-update '
        f'--input "{input_win}" '
        f'--output "{output_win}" '
        f'--ns-conventions "{ns_bbsa}" '
        f'--ew-conventions "{ew_bbsa}"'
    )

    if verbose:
        print(f"  Running bba-cli...")

    try:
        returncode, stdout, stderr = run_windows_command(
            cmd, timeout=BBA_TIMEOUT, verbose=verbose
        )

        if returncode != 0:
            print(f"  ERROR: bba-cli failed with exit code {returncode}")
            if stderr:
                print(f"  {stderr}")
            return False

        if verbose and stdout:
            print(f"  {stdout.strip()}")

        return True

    except Exception as e:
        print(f"  ERROR: {e}")
        return False


def compare_auctions(original_deals: list[Deal], bba_deals: list[Deal]) -> list[ValidationResult]:
    """Compare auctions between original and BBA-generated deals."""
    results = []

    # Build lookup by board number
    bba_by_board = {d.board: d for d in bba_deals}

    for orig in original_deals:
        bba = bba_by_board.get(orig.board)

        if not bba:
            results.append(ValidationResult(
                board=orig.board,
                reference_auction=orig.auction,
                bba_auction=[],
                match=False,
                error="Board not found in BBA output",
            ))
            continue

        orig_normalized = normalize_auction(orig.auction)
        bba_normalized = normalize_auction(bba.auction)
        is_match = orig_normalized == bba_normalized

        results.append(ValidationResult(
            board=orig.board,
            reference_auction=orig.auction,
            bba_auction=bba.auction,
            match=is_match,
        ))

    return results


def write_diff_file(filepath: str, scenario: str, results: list[ValidationResult]) -> int:
    """Write diff file with auction differences. Returns count of differences."""
    mismatches = [r for r in results if not r.match and r.error is None]
    errors = [r for r in results if r.error is not None]

    if not mismatches and not errors:
        if os.path.exists(filepath):
            os.remove(filepath)
        return 0

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"BBA Validation Differences: {scenario}\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 80 + "\n\n")

        total = len(results)
        matches = sum(1 for r in results if r.match)

        f.write(f"Summary: {matches}/{total} matches ({100*matches/total:.1f}%)\n")
        f.write(f"Mismatches: {len(mismatches)}\n")
        f.write(f"Errors: {len(errors)}\n\n")

        if mismatches:
            f.write("-" * 80 + "\n")
            f.write("AUCTION DIFFERENCES\n")
            f.write("-" * 80 + "\n\n")

            for r in mismatches:
                f.write(f"Board {r.board}:\n")
                f.write(f"  Original: {format_auction(r.reference_auction)}\n")
                f.write(f"  BBA:      {format_auction(r.bba_auction)}\n\n")

        if errors:
            f.write("-" * 80 + "\n")
            f.write("ERRORS\n")
            f.write("-" * 80 + "\n\n")

            for r in errors:
                f.write(f"Board {r.board}: {r.error}\n")

    return len(mismatches) + len(errors)


def validate_pbn_file(filepath: str, ns_convention: str, ew_convention: str,
                      limit: Optional[int], verbose: bool) -> tuple[int, int, int]:
    """
    Validate a single PBN file.

    Returns:
        Tuple of (matches, mismatches, errors)
    """
    basename = os.path.basename(filepath)
    scenario = os.path.splitext(basename)[0]
    dirname = os.path.dirname(os.path.abspath(filepath))

    print(f"\nValidating: {basename}")

    # Parse original file
    try:
        header, original_deals = parse_pbn_file(filepath)
    except Exception as e:
        print(f"  ERROR: Failed to parse: {e}")
        return 0, 0, 1

    if not original_deals:
        print(f"  WARNING: No deals found")
        return 0, 0, 0

    # Determine input file (original or limited)
    if limit and limit < len(original_deals):
        # Create temporary limited file
        temp_input = os.path.join(dirname, f"{scenario}-temp.pbn")
        count = create_limited_pbn(filepath, temp_input, limit)
        print(f"  Processing first {count} of {len(original_deals)} deals")
        input_file = temp_input
        original_deals = original_deals[:limit]
    else:
        print(f"  Processing {len(original_deals)} deals")
        input_file = os.path.abspath(filepath)
        temp_input = None

    # Output file
    bba_output = os.path.join(dirname, f"{scenario}-bba.pbn")

    # Remove old output if exists
    if os.path.exists(bba_output):
        os.remove(bba_output)

    # Run BBA
    success = run_bba_cli(input_file, bba_output, ns_convention, ew_convention, verbose)

    # Clean up temp file
    if temp_input and os.path.exists(temp_input):
        os.remove(temp_input)

    if not success:
        print(f"  ERROR: bba-cli failed")
        return 0, 0, len(original_deals)

    # Check output was created
    if not os.path.exists(bba_output):
        print(f"  ERROR: BBA output not created")
        return 0, 0, len(original_deals)

    # Parse BBA output
    try:
        _, bba_deals = parse_pbn_file(bba_output)
    except Exception as e:
        print(f"  ERROR: Failed to parse BBA output: {e}")
        return 0, 0, len(original_deals)

    # Compare auctions
    results = compare_auctions(original_deals, bba_deals)

    matches = sum(1 for r in results if r.match)
    mismatches = sum(1 for r in results if not r.match and r.error is None)
    errors = sum(1 for r in results if r.error is not None)

    print(f"  Results: {matches} matches, {mismatches} mismatches, {errors} errors")

    # Write diff file
    diff_filepath = os.path.join(dirname, f"{scenario}-diff.txt")
    diff_count = write_diff_file(diff_filepath, scenario, results)
    if diff_count > 0:
        print(f"  Wrote: {scenario}-diff.txt ({diff_count} differences)")

    # Print mismatches if verbose
    if verbose:
        for r in results:
            if not r.match:
                print(f"    Board {r.board}: {format_auction(r.reference_auction)} → {format_auction(r.bba_auction)}")

    return matches, mismatches, errors


def main():
    parser = argparse.ArgumentParser(
        description="Validate Baker Bridge PBN hands with BBA"
    )
    parser.add_argument(
        "pattern",
        help="Glob pattern for PBN files (e.g., 'Package/*.pbn')",
    )
    parser.add_argument(
        "--limit", "-l",
        type=int,
        help="Limit to first N deals per file",
    )
    parser.add_argument(
        "--ns-convention",
        default=DEFAULT_NS_CONVENTION,
        help=f"NS convention card (default: {DEFAULT_NS_CONVENTION})",
    )
    parser.add_argument(
        "--ew-convention",
        default=DEFAULT_EW_CONVENTION,
        help=f"EW convention card (default: {DEFAULT_EW_CONVENTION})",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed output",
    )

    args = parser.parse_args()

    # Find matching files (exclude -bba.pbn files)
    all_files = sorted(glob.glob(args.pattern))
    files = [f for f in all_files if not f.endswith("-bba.pbn")]

    if not files:
        print(f"ERROR: No files match pattern: {args.pattern}")
        sys.exit(1)

    print(f"BBA Validation (via bba-cli)")
    print(f"  Pattern: {args.pattern}")
    print(f"  Files: {len(files)}")
    print(f"  NS Convention: {args.ns_convention}")
    print(f"  EW Convention: {args.ew_convention}")
    if args.limit:
        print(f"  Limit: {args.limit} deals per file")

    # Validate each file
    total_matches = 0
    total_mismatches = 0
    total_errors = 0

    for filepath in files:
        matches, mismatches, errors = validate_pbn_file(
            filepath, args.ns_convention, args.ew_convention,
            args.limit, args.verbose
        )
        total_matches += matches
        total_mismatches += mismatches
        total_errors += errors

    # Print summary
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    total = total_matches + total_mismatches + total_errors
    if total > 0:
        print(f"  Total deals: {total}")
        print(f"  Matches:     {total_matches} ({100*total_matches/total:.1f}%)")
        print(f"  Mismatches:  {total_mismatches} ({100*total_mismatches/total:.1f}%)")
        print(f"  Errors:      {total_errors} ({100*total_errors/total:.1f}%)")
    else:
        print("  No deals processed")

    if total_mismatches > 0 or total_errors > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()

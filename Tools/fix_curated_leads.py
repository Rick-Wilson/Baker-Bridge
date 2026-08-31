#!/usr/bin/env python3
"""One-time: give the curated boards an opening lead of their own.

`package_results.py` merges Curated/*.pbn over the generated boards by replacing the
board WHOLESALE, so a curated board without a [Play] section drops the generated
opening lead. Thirty-two boards ended up that way.

The pipeline deliberately does not fill these in on every build: a curated board may
exist precisely to correct BEN's choice, and a build that overwrote it each time would
undo the curation. So the leads are written into the curated sources once, here, and
from then on the curated file is the authority -- exactly like every other tag it
carries. New curated boards should simply include their own [Play] section.

The lead is computed from the MERGED board, not the curated text, because most curated
boards are partially specified: they give N/S and leave E/W as "..." for the generated
fill to supply. The opening leader is usually one of those inherited hands, so only the
merged board knows what it actually holds.

Usage:
    export BEN_URL=https://ben.bridge-craftwork.com
    python3 fix_curated_leads.py --dry-run
    python3 fix_curated_leads.py
"""
import argparse
import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ben_leads as B                                   # noqa: E402  (same directory)

HERE = os.path.dirname(os.path.abspath(__file__))
CURATED_DIR = os.path.join(HERE, "..", "Curated")
MERGED_DIR = os.environ.get("BB_PACKAGE_DIR") or os.path.join(HERE, "..", "Collection")

SEAT_ORDER = ["N", "E", "S", "W"]


def split_boards(text):
    """[(board_number, board_text)] in file order."""
    out = []
    for chunk in re.split(r"(?=\[Event )", text):
        m = re.search(r'\[Board "(\d+)"\]', chunk)
        if m:
            out.append((m.group(1), chunk))
    return out


def deal_hands(board):
    """[Deal "N:x ... y ..."] -> {seat: 'S.H.D.C'}; '...' entries are left out."""
    m = re.search(r'\[Deal "([^"]*)"\]', board)
    if not m:
        return {}
    body = m.group(1)
    if ":" not in body:
        return {}
    first, rest = body.split(":", 1)
    first = first.strip().upper()
    if first not in SEAT_ORDER:
        return {}
    start = SEAT_ORDER.index(first)
    hands = {}
    for i, h in enumerate(rest.split()):
        if h and h != "...":
            hands[SEAT_ORDER[(start + i) % 4]] = h
    return hands


def auction_text(board):
    """The call tokens following the [Auction] tag pair."""
    m = re.search(r'\[Auction "([NESW])"\]\s*\n(.*?)(?=^\[|\Z)', board, re.S | re.M)
    if not m:
        return None, None
    # Take call lines only, stopping at the commentary block or the next tag -- the
    # auction is followed directly by "{...}" in most boards, and its prose would
    # otherwise be read as calls.
    lines = []
    for line in m.group(2).splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(("[", "{", "%")):
            break
        lines.append(stripped)
    return m.group(1), " ".join(lines)


def insert_play(board, seat, card):
    """Append the [Play] section, matching how CSV_to_PBN.py writes it (issue #42)."""
    section = f'[Play "{seat}"]\n{card}'
    trimmed = board.rstrip("\n")
    return f"{trimmed}\n{section}\n\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default=os.environ.get("BEN_URL", ""))
    ap.add_argument("--merged", default=MERGED_DIR, help="post-merge PBNs (Collection/)")
    ap.add_argument("--curated", default=CURATED_DIR)
    ap.add_argument("--timeout", type=int, default=120)
    ap.add_argument("--retries", type=int, default=3)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not args.url and not args.dry_run:
        print("No BEN URL. Pass --url or set BEN_URL.", file=sys.stderr)
        return 2

    total = added = skipped = failed = filled = 0
    for cf in sorted(glob.glob(os.path.join(args.curated, "*.pbn"))):
        name = os.path.basename(cf)
        merged_path = os.path.join(args.merged, name)
        if not os.path.exists(merged_path):
            print(f"{name}: no merged counterpart in {args.merged}; skipped")
            continue
        merged = dict(split_boards(open(merged_path, encoding="utf-8", errors="replace").read()))

        original = open(cf, encoding="utf-8", errors="replace").read()
        updated = original
        for num, board in split_boards(original):
            if re.search(r"\[Play ", board):
                continue
            total += 1
            label = f"{name} #{num}"
            mb = merged.get(num)
            if not mb:
                print(f"  {label}: no merged board; skipped"); skipped += 1; continue

            hands = deal_hands(mb)
            dealer_m = re.search(r'\[Dealer "([NESW])"\]', mb)
            dealer, calls = (dealer_m.group(1) if dealer_m else None), None
            adealer, calls = auction_text(mb)
            dealer = dealer or adealer
            if not dealer or not calls:
                print(f"  {label}: no auction; skipped"); skipped += 1; continue
            try:
                ctx, contract, declarer = B.parse_auction(calls, dealer)
            except B.AuctionError as e:
                print(f"  {label}: {e}; skipped"); skipped += 1; continue

            leader = B.lho(declarer)
            hand = hands.get(leader)
            if not hand:
                print(f"  {label}: leader {leader} hand unavailable; skipped")
                skipped += 1; continue

            if args.dry_run:
                print(f"  [dry run] {label}: {contract} by {declarer}, "
                      f"leader {leader} holds {hand}")
                continue

            try:
                data = B.ask_ben(args.url,
                                 {"hand": hand, "seat": leader, "dealer": dealer,
                                  "ctx": ctx, "vul": ""},
                                 args.timeout, args.retries)
                card = data["card"].strip().upper()
                if card not in B.cards_in_hand(hand):
                    raise RuntimeError(f"BEN returned {card}, not in {hand}")
            except Exception as e:                       # noqa: BLE001
                print(f"  {label}: FAILED — {e}"); failed += 1; continue

            new_board = insert_play(board, leader, card)

            # Pin the deal alongside the lead. Most curated boards give only N/S and
            # leave E/W as "...", inheriting them from the generated fill -- and the
            # opening leader is usually one of those inherited hands. Storing a lead
            # against a hand that can be re-rolled would let the two drift apart until
            # the lead names a card the leader no longer holds. Writing the merged
            # deal back makes the curated board self-contained: deal and lead move
            # together, or not at all.
            merged_deal = re.search(r'\[Deal "[^"]*"\]', mb)
            note = ""
            if merged_deal and "..." in (re.search(r'\[Deal "([^"]*)"\]', board) or
                                         type("", (), {"group": lambda s, i: ""})()).group(1):
                new_board = re.sub(r'\[Deal "[^"]*"\]', merged_deal.group(0).replace("\\", "\\\\"),
                                   new_board, count=1)
                filled += 1
                note = "  [deal pinned]"

            updated = updated.replace(board, new_board, 1)
            added += 1
            print(f"  {label}: {leader} leads {card}  ({contract} by {declarer}){note}")

        if updated != original and not args.dry_run:
            with open(cf, "w", encoding="utf-8") as f:
                f.write(updated)

    print(f"\nboards without a lead: {total} | added: {added} | deals pinned: {filled} | "
          f"skipped: {skipped} | failed: {failed}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Fill in missing opening leads by asking BEN, with a resumable cache.

Most lesson boards carry no opening lead, and pbn-to-pdf's declarer's-plan layouts want
one. This asks a running BEN service (`GET /lead`) for the lead the defender on opening
lead would make, given that seat's hand and the full auction.

BEN takes up to ~30 seconds per board, so a full pass over ~750 boards is an overnight
run. The script is therefore built to be interrupted and resumed:

  * every answer is appended to the cache and flushed to disk immediately, so a crash,
    a dropped connection or Ctrl-C costs at most the board in flight;
  * a re-run reads the cache and asks only about boards it does not already hold;
  * each cached row records a fingerprint of the leader's hand + auction, so a board
    whose deal later changes (a re-rolled passer, say — the leader is usually an
    opponent, and those hands are generated) is re-asked rather than silently reused.

The cache, not the deal set, is the durable artifact: `bb_fill.py` rewrites
BakerBridgeFull.csv from scratch on every deals build, so a lead written into that CSV
would not survive. Committing the cache is what makes this a one-time cost.

Usage:
    export BEN_URL=http://<droplet>:8085
    python3 ben_leads.py                          # fill every board missing a lead
    python3 ben_leads.py --limit 5 --verbose      # a short trial first
    python3 ben_leads.py --lesson Stayman         # one lesson
    python3 ben_leads.py --apply                  # write cached leads into the CSV

Nothing here hardcodes the service address; pass --url or set BEN_URL.
"""
import argparse
import csv
import hashlib
import json
import os
import re
import signal
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CSV = os.path.join(HERE, "BakerBridgeFull.csv")
DEFAULT_CACHE = os.path.join(HERE, "lead_cache.csv")

SEATS = ["N", "E", "S", "W"]           # clockwise
SEAT_COLUMN = {"N": "NorthHand", "E": "EastHand", "S": "SouthHand", "W": "WestHand"}
SUITS = ["S", "H", "D", "C"]
CACHE_FIELDS = ["Lesson", "Board", "Seat", "Fingerprint", "Card", "Who", "Quality", "FetchedAt"]

# Auction tokens that are prose rather than calls. "all" is the "all pass" idiom: the
# passes that close the auction are spelled out as separate tokens either way, so the
# word itself is dropped. "|" is a line break carried over from the source HTML.
NOISE_TOKENS = {"all", "|"}
# PBN note references attached to a call, e.g. "4C =1=" with a matching [Note "1:control"].
NOTE_REF = re.compile(r"^=\d+=$")
DOUBLE_TOKENS = {"x", "dbl", "double"}
REDOUBLE_TOKENS = {"xx", "rdbl", "redouble"}
PASS_TOKENS = {"pass", "p", "--"}


class AuctionError(Exception):
    """The auction could not be read as a complete, legal auction."""


def seat_letter(name):
    """'South' / 'S' -> 'S'."""
    n = (name or "").strip()
    return n[0].upper() if n else ""


def lho(seat):
    """The seat to a player's left — declarer's LHO is on opening lead."""
    return SEATS[(SEATS.index(seat) + 1) % 4]


def hand_to_pbn(hand):
    """'S:J86 H:A98 D:8653 C:AKQ' -> 'J86.A98.8653.AKQ'."""
    parts = {}
    for chunk in (hand or "").split():
        if ":" in chunk:
            suit, cards = chunk.split(":", 1)
            parts[suit.strip().upper()] = cards.strip()
    if not parts:
        raise AuctionError(f"unreadable hand: {hand!r}")
    return ".".join(parts.get(s, "") for s in SUITS)


def encode_call(token):
    """One auction token -> BEN's 2-character encoding, or None for noise."""
    t = token.strip()
    if not t or t.lower() in NOISE_TOKENS or NOTE_REF.match(t):
        return None
    low = t.lower()
    if low in PASS_TOKENS:
        return "--"
    if low in DOUBLE_TOKENS:
        return "Db"
    if low in REDOUBLE_TOKENS:
        return "Rd"
    level, denom = t[0], t[1:].upper()
    if not level.isdigit() or not 1 <= int(level) <= 7:
        raise AuctionError(f"unrecognised call {token!r}")
    if denom in ("NT", "N"):
        denom = "N"
    elif denom not in ("C", "D", "H", "S"):
        raise AuctionError(f"unrecognised denomination in {token!r}")
    return level + denom


def parse_auction(auction, dealer):
    """Return (ctx, contract, declarer) derived from the auction itself.

    Deriving the contract and declarer rather than trusting the CSV's columns gives a
    free correctness check: if the auction does not produce the contract the lesson
    claims, the auction is malformed and the board is not safe to ask BEN about.
    """
    calls = [c for c in (encode_call(t) for t in (auction or "").split()) if c]
    if not calls:
        raise AuctionError("empty auction")

    seat = SEATS.index(dealer)
    last_bid = None          # (level, denom, seat_index)
    # First seat of each side to name each denomination, for the declarer rule.
    first_named = {}
    passes_at_end = 0
    for call in calls:
        if call == "--":
            passes_at_end += 1
        else:
            passes_at_end = 0
            if call not in ("Db", "Rd"):
                level, denom = call[0], call[1]
                if last_bid and (int(level), "CDHSN".index(denom)) <= (
                        int(last_bid[0]), "CDHSN".index(last_bid[1])):
                    raise AuctionError(f"call {call} does not raise {last_bid[0]}{last_bid[1]}")
                last_bid = (level, denom, seat)
                side = seat % 2
                first_named.setdefault((side, denom), seat)
        seat = (seat + 1) % 4

    if last_bid is None:
        raise AuctionError("passed out — no contract")
    if passes_at_end < 3:
        raise AuctionError(f"auction not closed ({passes_at_end} trailing passes)")

    level, denom, bidder = last_bid
    declarer = SEATS[first_named[(bidder % 2, denom)]]
    contract = f"{level}{'NT' if denom == 'N' else denom}"
    return "".join(calls), contract, declarer


def normalize_contract(c):
    """'4H', '4 H', '3NT', '3N' -> '4H' / '3NT' for comparison."""
    c = (c or "").replace(" ", "").upper()
    for suffix in ("XX", "X"):          # doubled contracts compare on the strain alone
        if c.endswith(suffix):
            c = c[: -len(suffix)]
    if c.endswith("N") and not c.endswith("NT"):
        c += "T"
    return c


def fingerprint(hand_pbn, ctx):
    return hashlib.sha256(f"{hand_pbn}|{ctx}".encode()).hexdigest()[:16]


def cards_in_hand(hand_pbn):
    out = set()
    for suit, holding in zip(SUITS, hand_pbn.split(".")):
        for rank in holding:
            out.add(suit + rank.upper())
    return out


def board_key(row):
    return (row.get("Subfolder", ""), row.get("DealNumber", ""))


def load_cache(path):
    cache = {}
    if not os.path.exists(path):
        return cache
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            cache[(row["Lesson"], row["Board"])] = row
    return cache


class CacheWriter:
    """Append-only cache, flushed after every row so an interrupted run loses nothing."""

    def __init__(self, path):
        self.path = path
        self.new = not os.path.exists(path) or os.path.getsize(path) == 0
        self.f = open(path, "a", newline="", encoding="utf-8")
        self.w = csv.DictWriter(self.f, fieldnames=CACHE_FIELDS)
        if self.new:
            self.w.writeheader()
            self.f.flush()

    def write(self, row):
        self.w.writerow(row)
        self.f.flush()
        os.fsync(self.f.fileno())

    def close(self):
        self.f.close()


def rewrite_cache(path, cache):
    """Rewrite the cache in sorted order (used after stale rows are dropped)."""
    tmp = path + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CACHE_FIELDS)
        w.writeheader()
        for key in sorted(cache, key=lambda k: (k[0], int(k[1]) if k[1].isdigit() else 0)):
            w.writerow({k: cache[key].get(k, "") for k in CACHE_FIELDS})
    os.replace(tmp, path)


def ask_ben(url, params, timeout, retries, verbose=False):
    """GET /lead, retrying transient failures with backoff. Returns the parsed JSON."""
    query = urllib.parse.urlencode(params)
    endpoint = f"{url.rstrip('/')}/lead?{query}"
    if verbose:
        print(f"    GET {endpoint}")
    last = None
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(endpoint, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            if "error" in data:
                raise RuntimeError(data["error"])
            if not data.get("card"):
                raise RuntimeError(f"no card in response: {data}")
            return data
        except Exception as e:                      # noqa: BLE001 - retry anything transient
            last = e
            if attempt < retries:
                backoff = min(60, 2 ** attempt)
                print(f"    attempt {attempt} failed ({e}); retrying in {backoff}s")
                time.sleep(backoff)
    raise RuntimeError(f"{retries} attempts failed: {last}")


def prepare(row):
    """Everything BEN needs for one board, or raise AuctionError."""
    dealer = seat_letter(row.get("Dealer"))
    if dealer not in SEATS:
        raise AuctionError(f"unreadable dealer {row.get('Dealer')!r}")
    ctx, contract, declarer = parse_auction(row.get("Auction"), dealer)

    claimed = normalize_contract(row.get("Contract"))
    if claimed and normalize_contract(contract) != claimed:
        raise AuctionError(f"auction yields {contract}, lesson says {row.get('Contract')}")
    claimed_declarer = seat_letter(row.get("Declarer"))
    if claimed_declarer and claimed_declarer != declarer:
        raise AuctionError(f"auction yields declarer {declarer}, lesson says {claimed_declarer}")

    leader = lho(declarer)
    hand_pbn = hand_to_pbn(row.get(SEAT_COLUMN[leader]))
    return {
        "seat": leader,
        "hand": hand_pbn,
        "ctx": ctx,
        "dealer": dealer,
        # Every board in this collection is generated with [Vulnerable "None"]
        # (CSV_to_PBN.py), so the lead is asked for at nil vulnerability to match.
        "vul": "",
    }


def selected(args, row):
    """Honour the --lesson / --board filters."""
    if args.lesson and row.get("Subfolder") != args.lesson:
        return False
    if args.board and str(row.get("DealNumber")) != str(args.board):
        return False
    return True


def cmd_apply(args, rows, cache, fieldnames):
    """Write cached leads into the CSV's Lead column."""
    filled = skipped = 0
    for row in rows:
        if not selected(args, row):
            continue
        key = board_key(row)
        cached = cache.get(key)
        if not cached or not cached.get("Card"):
            continue
        if (row.get("Lead") or "").strip() and not args.force:
            skipped += 1
            continue
        try:
            info = prepare(row)
        except AuctionError:
            continue
        if cached.get("Fingerprint") != fingerprint(info["hand"], info["ctx"]):
            skipped += 1
            continue
        row["Lead"] = cached["Card"]
        filled += 1
    if args.dry_run:
        print(f"[dry run] would fill {filled} leads ({skipped} skipped)")
        return 0
    tmp = args.csv + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, args.csv)
    print(f"Filled {filled} leads into {args.csv} ({skipped} skipped)")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", default=DEFAULT_CSV, help="deal-set CSV to read")
    ap.add_argument("--cache", default=DEFAULT_CACHE, help="resumable lead cache")
    ap.add_argument("--url", default=os.environ.get("BEN_URL", ""),
                    help="BEN base URL (or set BEN_URL), e.g. http://host:8085")
    ap.add_argument("--lesson", default="", help="only this lesson (Subfolder)")
    ap.add_argument("--board", default="", help="only this board number (with --lesson)")
    ap.add_argument("--limit", type=int, default=0, help="stop after N boards")
    ap.add_argument("--timeout", type=int, default=120, help="per-request timeout (s)")
    ap.add_argument("--retries", type=int, default=3, help="attempts per board")
    ap.add_argument("--sleep", type=float, default=0.0, help="pause between boards (s)")
    ap.add_argument("--force", action="store_true", help="re-ask boards that already have a lead")
    ap.add_argument("--apply", action="store_true", help="write cached leads into the CSV")
    ap.add_argument("--dry-run", action="store_true", help="show what would happen, ask nothing")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    with open(args.csv, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    cache = load_cache(args.cache)
    if args.apply:
        return cmd_apply(args, rows, cache, fieldnames)

    if not args.url and not args.dry_run:
        print("No BEN URL. Pass --url or set BEN_URL (e.g. http://<droplet>:8085).",
              file=sys.stderr)
        return 2

    # Work out what still needs asking.
    todo, unreadable, reused, stale = [], [], 0, 0
    for row in rows:
        if not selected(args, row):
            continue
        if (row.get("Lead") or "").strip() and not args.force:
            continue
        try:
            info = prepare(row)
        except AuctionError as e:
            unreadable.append((board_key(row), str(e)))
            continue
        fp = fingerprint(info["hand"], info["ctx"])
        cached = cache.get(board_key(row))
        if cached and cached.get("Card") and not args.force:
            if cached.get("Fingerprint") == fp:
                reused += 1
                continue
            stale += 1          # the deal moved under the cached answer; ask again
        todo.append((row, info, fp))

    if args.limit:
        todo = todo[: args.limit]

    print(f"boards needing a lead : {len(todo)}")
    print(f"  already cached      : {reused}")
    if stale:
        print(f"  cached but stale    : {stale} (deal changed; will re-ask)")
    if unreadable:
        print(f"  unreadable auctions : {len(unreadable)} (skipped)")
        for key, why in unreadable[:8]:
            print(f"      {key[0]} #{key[1]}: {why}")
        if len(unreadable) > 8:
            print(f"      ... and {len(unreadable) - 8} more")
    if not todo:
        print("Nothing to do.")
        return 0
    print(f"estimated time        : ~{len(todo) * 30 / 3600:.1f}h at 30s/board")

    if args.dry_run:
        for row, info, _ in todo[:5]:
            print(f"  [dry run] {row['Subfolder']} #{row['DealNumber']}: "
                  f"seat={info['seat']} hand={info['hand']} ctx={info['ctx']}")
        return 0

    writer = CacheWriter(args.cache)
    interrupted = {"flag": False}

    def on_sigint(_sig, _frame):
        # Finish cleanly rather than dying mid-write; the cache is already flushed.
        interrupted["flag"] = True
        print("\nInterrupt received — stopping after the board in flight.")

    signal.signal(signal.SIGINT, on_sigint)

    done = failed = 0
    started = time.time()
    try:
        for n, (row, info, fp) in enumerate(todo, 1):
            if interrupted["flag"]:
                break
            label = f"{row['Subfolder']} #{row['DealNumber']}"
            try:
                data = ask_ben(args.url, info, args.timeout, args.retries, args.verbose)
                card = data["card"].strip().upper()
                if card not in cards_in_hand(info["hand"]):
                    raise RuntimeError(f"BEN returned {card}, not in {info['hand']}")
            except Exception as e:                  # noqa: BLE001
                failed += 1
                print(f"[{n}/{len(todo)}] {label}: FAILED — {e}")
                continue

            writer.write({
                "Lesson": row["Subfolder"], "Board": row["DealNumber"],
                "Seat": info["seat"], "Fingerprint": fp, "Card": card,
                "Who": data.get("who", ""), "Quality": data.get("quality", ""),
                "FetchedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            })
            done += 1
            per = (time.time() - started) / done
            left = (len(todo) - n) * per
            print(f"[{n}/{len(todo)}] {label}: {card} "
                  f"({data.get('quality', '?')}) — {per:.0f}s/board, ~{left/3600:.1f}h left")
            if args.sleep:
                time.sleep(args.sleep)
    finally:
        writer.close()

    print(f"\nDone: {done} leads cached, {failed} failed"
          f"{', interrupted' if interrupted['flag'] else ''}.")
    print(f"Cache: {args.cache}")
    print("Re-run to continue; --apply writes the cached leads into the CSV.")
    return 1 if failed and not done else 0


if __name__ == "__main__":
    sys.exit(main())

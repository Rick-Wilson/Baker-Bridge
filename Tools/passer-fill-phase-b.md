# Phase B — unified BBA-reject passer fill, cache, mac/windows unification

**Status:** Done (2026-07-14). **Related:** issue #21, `passer-fill-bba-redesign.md`,
Phase 0 (`passer-fill-phase0-audit.md`), Phase A (`passer-fill-phase-a.md`).
**Tools:** `Tools/passer_reroll.py`, `Tools/passer_cache.csv`.

Generalizes the Phase A prototype to the whole collection, adds a committed cache, unifies
the retired mac/windows split, removes the Windows build path, and moves the build's output
to a new `bridge-classroom/` folder.

## The two-source problem (found in Phase B)

The build filled passers **two** ways, and both produced biddable passers:

1. `constructed_hands.csv` (fill_hands.py) — the loose `auction_calm` constraint. **465 boards.**
2. `bb_fill.py`'s `assign_to_east_west` — an **unseeded `random.shuffle`** used for every
   board not in `missing_bids.csv` (all 12 `Partnership-*` lessons). **288 boards** —
   unconstrained *and* a second non-determinism source beyond the mac/windows split.

Patching only `auction_calm` (the original plan) would have missed the 288 random-passer
boards. So Phase B inserts **one unified step** downstream of both.

## `passer_reroll.py` — the unified step

Runs after `bb_fill` over the assembled `BakerBridgeFull.csv`. For each board it re-rolls the
passers **iff** E/W were empty in the source **and** E/W are the quiet (all-pass) side —
exactly the generated-quiet-passer universe. It:

- keeps the bidding hands (N/S) exactly;
- redraws E/W with the Phase A managed-variety BBA-reject loop (dealer3 draw → hard outlier
  filter → BBA-reject via `bba-cli --auction-prefix` → variety controller), the acceptance
  test imported from `audit_passers.py` so **accepted ≡ audit-clean by construction**;
- supersedes *both* `auction_calm` and the random shuffle with one deterministic result.

Competitive/interference boards (E/W scripted to bid) have no all-pass E/W side → skipped,
so their constructed fills are preserved. Boards where N/S were generated (defender lessons)
are `ns-quiet` → skipped (we only ever re-roll the generated E/W pair).

### Committed cache (`passer_cache.csv`)

Keyed by board identity `(Subfolder, DealNumber)` + the fixed bidding hands + auction. A
board is re-rolled only when it has no cached fill or its N/S/auction changed (or
`--revalidate`). This is what kills the non-determinism and the mac/windows split: **one
machine-independent cache**, committed, reused every build.

- Cache-cold (first generation): 553 boards, ~95s.
- Cache-warm (normal build): **0.09s**, reused=553, byte-identical output (idempotent).
- Determinism: per-board seed derived from the board key (`--seed` base, default 20260714);
  two runs produce a byte-identical cache.

### Forced-distribution escalation

A few deals force distribution on the passers (e.g. Blackwood d18: South has a club void
and N/S hold 12 spades, so **one E/W hand always has a spade void**). The outlier filter
escalates only when the gentle default can't be met: `(6,no-void,no-5-5) → (allow void) →
(7) → (13, allow 5-5)`. Same seed each try, so it's deterministic; escalation just relaxes
which clean hands are allowed. One board (Blackwood d18) needed policy 1 (forced void).

## Results

Audit of the new `bridge-classroom/` build (`BB_PACKAGE_DIR=bridge-classroom python3
audit_passers.py`): **biddable-passer boards 141 → 34.**

- **Every board the generated fill owns is BBA-clean: 0 biddable** (553 re-rolled quiet
  boards, covering both the constructed-Calm and Partnership-random sources).
- The remaining 34 are **not** generated quiet passers:
  - **32** are source-deal play lessons (100Deals, Eliminations, Establishment, Entries,
    Finesse, Squeeze, SecondHand, Signals, ThirdHand, Trumpmgmt, 100NT) — real deals from
    the HTML, not fill output.
  - **1** is a curated board (2over1 b10, from `Curated/2over1.pbn`; curation bypasses the
    generated pipeline) — byte-identical to the orphaned `Package/`.
  - **1** is an audit false positive on a defender lesson (DONT b18: East opens 1NT
    passed-out; the flag is *South the student's* DONT double, not a passer).
- **N/S untouched:** 0 N/S hands changed vs `HEAD`; exactly 553 E/W rows changed.
- **Variety managed:** balanced 65% (target), 0 gratuitous outliers (the 1 forced-void
  counts as outlier but is deal-forced, not gratuitous).
- **Tokens track the change:** re-rolled boards get new `[VersionToken]`s;
  curated/source boards keep the same token as `Package/`.

## Output moved to `bridge-classroom/`

Per the plan, the build's contracted files now go to a new **`bridge-classroom/`** root
folder (50 PBNs + `manifest.json` + `toc.json` + `titles.csv`); the original **`Package/`
is left in place as a frozen orphan** until Bridge-Classroom repoints its props at the new
folder. `BB_PACKAGE_DIR` (env) drives the target; `package_results.py`, `stamp_board_tokens.py`,
`generate_manifest.py`, `CSV_to_PBN.py` (toc) and `audit_passers.py` all honor it, defaulting
to `bridge-classroom/` in `build-mac.sh` (override to rebuild the orphan `Package/`).

> PDFs are **not** committed to `bridge-classroom/` — they are print handouts, not producer-
> contract artifacts. The `rotations` build renders them from the re-rolled PBNs, in the
> `rotate` phase, into `Rotations/`. (`pbns/` no longer holds PDFs at all: the old `pbn-pdf`
> phase rendered them from PBNs that still carried the control tags, and nothing consumed
> them.)

## Windows build path removed

Removed from the tree (history retained in git); see `Tools/windows-build-legacy.md`:
the `-windows` CSVs, `pbns-windows/`, `pdfs-windows/`, `Rotations-windows/`, the four `.ps1`
scripts, `auction-fixes/validate_bba.py`, and the SSH/Windows BBA validation inside
`fill_hands.py` (which now only does dealer3 generation for interference lessons).

## Build

```bash
cd Tools
./build-mac.sh classroom            # parse … fill → reroll → pbn → package → stamp → export
./build-mac.sh reroll               # just the re-roll (reuses passer_cache.csv)
./build-mac.sh reroll REROLL_ARGS=--revalidate   # re-check cached fills against BBA
BB_PACKAGE_DIR=bridge-classroom python3 audit_passers.py   # regression audit
```

## Deferred / follow-ups

- **Curated quiet boards aren't BBA-checked** (2over1 b10). Curation is hand-authored and
  bypasses the fill; if desired, extend the audit to curated boards and fix at the source.
- **Audit heuristic on defender lessons** (DONT b18) flags the student's own action as a
  passer; harmless, but the audit could exclude boards whose all-pass side contains the
  `[Student]` seat.
- **BC cutover:** point Bridge-Classroom's props at `bridge-classroom/`; the re-rolled boards
  carry new `[VersionToken]`s (new board identity) — coordinate per the producer contract.

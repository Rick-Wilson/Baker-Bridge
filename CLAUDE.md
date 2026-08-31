# Baker Bridge - Claude Code Notes

## Division of Labor: Baker-Bridge vs Bridge-Classroom

### Baker-Bridge (This Repo - Content Generation)
- Produces PBN files with ALL instructions for display and interaction
- bbparse.py extracts content from HTML and generates control directives
- CSV_to_PBN.py formats the CSV into PBN (mostly formatting, not logic)
- Single source of truth for lesson behavior

### Bridge-Classroom (Dumb Renderer)
- Reads PBN files and follows instructions exactly
- Does NOT make decisions based on presence/absence of tags
- Does NOT infer visibility from lesson type or mode

### Key Principle
**The PBN provides explicit instructions; the app follows them.**

If something needs to be shown or hidden, the PBN says so explicitly via `[show ...]` tags. The app doesn't try to be smart.

---

## Build Process Overview

The Baker Bridge content pipeline converts HTML lessons into PBN files:

```
HTML Files → bbparse.py → CSV → CSV_to_PBN.py → PBN Files
```

### Step 1: HTML Parsing (bbparse.py)

Parses the original Baker Bridge HTML files to extract:
- Deal information (hands, auction, contract, declarer)
- Progressive analysis text for each step
- Opening lead
- Student seat (South by default, West for OLead, East for ThirdHand)
- **Control directives** (`[show]`, `[PLAY]`, `[BID]`, `[NEXT]`, etc.)

### Step 2: CSV to PBN (CSV_to_PBN.py)

Converts CSV data to PBN format. Mostly formatting - the control directives come from bbparse.py.

## HTML Section Structure

Each deal in the HTML has numbered anchor sections. **Important**: Some HTML files use `<a name="1">` while others use `<a id="1">`. The code must check for both attributes:

```python
anchors = soup.find_all("a", attrs={"id": True}) + soup.find_all("a", attrs={"name": True})
anchor_name = anchor.get("id") or anchor.get("name", "")
```

Each section contains:
- A table with the bridge diagram (N/S/E/W hands)
- The auction table
- Analysis text
- A NEXT/ROTATE button linking to the next section

### Hand Visibility Detection

Key logic in `extract_hands_by_anchor()` and `extract_hands_from_table()`:

#### Step 1: Detect which hands are visible

`extract_hands_from_table()` finds hands by CSS patterns:
- **North**: `<td>` with `width:6em/7em/8em` style
- **South**: `<td>` with `height:800px`
- **E/W**: Row containing `t1.gif` image, first and third `<td>`

**Critical check**: `has_card_values()` - a hand is only "visible" if it has:
- All 4 suit symbols (♠♥♦♣) AND
- Actual card values (A, K, Q, J, T, 9-2)

Empty placeholders (suit symbols with no cards) are NOT counted as visible. This is how bidding lessons like FSF show only South initially - the North position has suit symbols but no cards.

#### Step 2: Generate initial [show] directive

For section 0 (first section), `extract_hands_by_anchor()` generates:
```python
visible_seats = []
if section_hands[i]["north_raw"]:  # has actual cards
    visible_seats.append("N")
if section_hands[i]["south_raw"]:
    visible_seats.append("S")
# ... etc
initial_show = "[show " + "".join(visible_seats) + "]"
```

**Example**: FSF HTML has only South cards visible → generates `[show S]`

#### Step 3: Detect visibility changes

Compare consecutive sections:
- **Played cards**: Cards in section N but not in N+1 = played
- **E/W visibility**: If E/W appear in N+1 but not N → add `[show NESW]`

#### Output directives:
- `[show S]` - Initial visibility (only South)
- `[show NS]` - Initial visibility (declarer + dummy)
- `[show NESW]` - When E/W hands become visible
- `[PLAY N:SK,S:H3]` - Cards that were played
- `[RESET]` - After "complete deal" text

## Control Directives

Directives in the PBN analysis control the Bridge Classroom app UI:

### Hand Visibility
- `[show NS]` - Show only North/South hands
- `[show NESW]` - Show all four hands
- `[show W]` / `[show E]` - Show only one defender (for OLead/ThirdHand)

### Navigation
- `[NEXT]` - Marks end of step, shows Next button
- `[ROTATE]` - Like NEXT but rotates the table view

### Auction/Lead Display
- `[AUCTION off]` - Hide the auction table
- `[AUCTION on]` - Show the auction table
- `[SHOW_LEAD]` - Display the opening lead banner

### Card Play
- `[PLAY N:SK,N:S4,S:H3]` - Mark cards as played (removed from hands)
- `[RESET]` - Reset hands to original (show all cards again)

---

## How bbparse.py Generates Each Directive

### `[BID X]` - Bidding Prompts

**Location**: `clean_up_analysis()` function, line ~415

**Logic**: If a section doesn't have NEXT/ROTATE buttons and isn't a deal link, it's a bidding prompt:
```python
elif not 'href="deal' in td_str:
    analysis = analysis + " [BID " + replace_suits(last_bid,False) + "]"
```

The bid value comes from the full auction - finds what bid corresponds to this position.

### `[NEXT]` and `[ROTATE]` - Navigation

**Location**: `clean_up_analysis()` function, lines ~402-413

**Logic**:
- If "NEXT" button in HTML → append `[NEXT]`
- If "rotate" text or ROTATE button → append `[ROTATE]`

### `[RESET]` - Reset Hands

**Location**: `extract_progressive_analysis()` function, lines ~531-535

**Logic**: If a step mentions "complete deal" or "full deal", add `[RESET]` to the NEXT step.

---

## CSV_to_PBN.py Role

Mostly formatting, not logic:
1. Converts CSV columns to PBN tags
2. Adds metadata ([SkillPath], [Category], [Difficulty])
3. **Fallback only**: Adds `[show NS]` if bbparse didn't provide a `[show]` directive
4. For play instruction mode: injects `[AUCTION off]` and `[SHOW_LEAD]` after first [NEXT]

The key visibility logic is in bbparse.py - CSV_to_PBN just passes it through.

## Running the Build

The complete build pipeline has five steps:

```bash
cd Tools

# Step 1: Parse HTML to CSV (also generates debug anchor files)
python3 bbparse.py

# Step 2: Convert CSV to PBN files
python3 CSV_to_PBN.py BakerBridge.csv

# Step 2b: Inject the defense-lesson [showcards] dummy-card fixes onto pbns/
python3 apply_showcards_dummy.py pbns

# Step 3: Copy PBN/PDF files to Package folder for distribution
python3 package_results.py

# Step 4: Stamp board-identity tokens on the released Package PBNs (must run after step 3)
python3 stamp_board_tokens.py

# Step 5: Emit the build-generated manifest (must run LAST, after tokens are stamped)
python3 generate_manifest.py
```

(`Tools/build-materials.sh` runs all of these; steps 4–5 are its `stamp` phase, after `package`.)

**The build is two scripts** (split at `BakerBridgeFull.csv`, the deal set of record).
`build-deals.sh` turns the HTML into that CSV and is **not reproducible** — `bb_fill`'s E/W
assignment is an unseeded shuffle, so a re-run can change deals and therefore
`[VersionToken]`s, which BC keys mastery and problem reports off. `build-materials.sh` turns
the CSV into the published trees and **is** idempotent: the same CSV yields byte-identical
output, so re-running it on an unchanged deal set leaves a clean `git status`. Packaging
work uses `build-materials.sh` only. (`build-mac.sh` is a shim forwarding to it; its old
`classroom`/`rotations` shortcuts ran both halves and silently re-dealt hands.)

The PBN `%Created:` stamp is pinned to the deal set, not the clock — bridge-wrangler passes
it through, so a wall-clock stamp would rewrite ~3,000 files per run. See
`resolve_build_time()` in `CSV_to_PBN.py` and `resolve_build_date()` in `build-common.sh`.

**Passer fill (issue #21, Phase B).** Before the CSV becomes PBNs, the generated *passer*
(opponent) hands are made BBA-clean by `passer_reroll.py` (the `reroll` phase, after
`bb_fill`): it re-rolls every board whose E/W were generated and are the quiet (all-pass)
side, rejecting any fill where a bidding engine shows the opponents would act, and caches the
result in the committed `passer_cache.csv` (deterministic, machine-independent — this
replaced the non-deterministic mac/windows split). The Windows build path was removed here —
see `Tools/windows-build-legacy.md` and `Tools/passer-fill-phase-b.md`.

**Build folder layout (issue #21, Phase B).** The merge+stamp+manifest steps write a shared
master, **`Collection/`** (`BB_PACKAGE_DIR`; a regenerable, gitignored intermediate that
replaced `Package/`'s old role — `Package/` is a frozen orphan). Two committed exports
**diverge** from `Collection/` (they are NOT chained through each other):

- **`bridge-classroom/`** — the app's contracted files (control-tag PBNs + `manifest.json` +
  `toc.json` + `titles.csv` + optional `*_Intro.pdf`), copied out by the `export` phase.
- **`Presentation/` → `Rotations/`** — the face-to-face teaching materials (control tags
  stripped, table rotations/slices/handouts), built from `Collection/` by
  `package_presentation.py` (which honors `BB_PACKAGE_DIR`) + the shared `package.sh` (bridge-lesson-packaging).
  Standard structure spec: `Tools/rotations-contract.md`.

Sourcing Presentation from `Collection/` (not the orphan `Package/`) is what keeps the
dealer files and the app in sync — the divergence that caused the 2026-07-14 class problem.

### What Each Step Does

1. **bbparse.py** → Parses HTML, generates `BakerBridge.csv` and debug files in `Tools/Anchors/`
2. **CSV_to_PBN.py** → Converts CSV to PBN files in `Tools/pbns/`, also generates `Package/toc.json`
   - **apply_showcards_dummy.py** → injects the defense-lesson `[showcards]` dummy-card fixes from `showcards_dummy_key.md` (bbparse can't recover dummy's played card from the HTML; see "Defense `[showcards]` dummy cards" below)
3. **package_results.py** → Copies all `.pbn` and `.pdf` files from `pbns/` to `Package/`, then merges in curated boards from `Curated/`
4. **stamp_board_tokens.py** → Stamps `[VersionToken]` on every board in `Package/*.pbn` and backstops the `%bridge-classroom-stable: true` header (see "Board Identity Metadata" below)
5. **generate_manifest.py** → Emits `Package/manifest.json`, the build-generated collection manifest (producer-contract R5); reads the fully-stamped `Package/*.pbn`

## Board Identity Metadata (Bridge Classroom)

Bridge Classroom uses board-identity + readiness metadata to decide whether Baker boards count toward mastery and to match "Report a Problem" reports across rotations.

- **`%bridge-classroom-stable: true`** — a file-level header comment. Present ⇒ that file's boards count toward mastery; absent/`false` ⇒ BC treats them as prerelease (recorded + navigable, but excluded from mastery/stats). Emitted by `CSV_to_PBN.py` next to `%bridge-context:`, and backstopped by `stamp_board_tokens.py` so curated-only files can't slip through. (Collection is **not** a PBN concern — BC sources `collection_id` from its own config.)
  - To mark a single board under active revision inside an otherwise-stable file, add a board-level override `[Stable "false"]`.
- **`[VersionToken "…"]`** — a 64-char lowercase sha256 hex per board, stamped by `stamp_board_tokens.py`. It is a **rotation-canonical** hash of the deal + auction: the deal is rotated so the ♠A holder becomes North, then `sha256(canonicalDeal + "|" + canonicalAuction)`. Identical across all rotational variants of a deal. **BC treats it as opaque** (records/echoes only).
  - **The normalization is frozen.** Changing it changes every token and breaks BC's ability to match previously-recorded tokens. See the module docstring in `stamp_board_tokens.py` for the exact rules; any new scheme must be a versioned, additive change.

`stamp_board_tokens.py` runs **after** the curated merge so generated, merged, and any future pure-curated boards are all stamped from their final released content. It fails the build (exit 1) if any board can't be tokenized or has a blank/`uncategorized` `[SkillPath]`.

- **`Package/manifest.json`** — the build-generated collection manifest (producer-contract **R5**), the authoritative description of the collection's shape that Bridge Classroom fetches directly (it does **not** re-parse the PBNs for sizing). Emitted by `generate_manifest.py` as the **last** build step, reading the fully-stamped `Package/*.pbn`. Schema v3, keyed by PBN basename; per lesson `skillPath`/`boardCount`/`stableBoardCount`/`boards[]` and an **optional** `intro` (the companion `{Lesson}_Intro.pdf`, present iff a lesson intro exists — the app offers it when present but never requires it); per board `number`/`stable`/`boardVersionToken`/`skillPath`. Per contract §7 it carries only producer-owned facts — **no** `collection` id, `report` flag, or `prerelease` column, and no `tier` (a PBS client-side concern). It fails the build (exit 1) if any released board lacks an integer `number`, a token, or a skill path. Note `manifest.json` does **not** replace `toc.json` (navigation TOC) — both ship.

## Defense `[showcards]` dummy cards

`bbparse.py` builds `[showcards]` directives from partial-hand diffs in the source HTML. Dummy is rendered as a *full* hand (`[show N]`), so its **played** card is never a diffable partial hand — every defense-lesson `[showcards]` (Signals, SecondHand, ThirdHand) omits dummy's card, and a few originals are malformed. The card can't be recovered from the HTML, so it is supplied out of band:

- **`Tools/showcards_dummy_key.md`** — the answer key, one line per board: `<Lesson> <Board> | <FROM directive> => <TO directive>`. Corrected directives (not just "the card") so it also covers dummy-led decision tricks and malformed-directive rebuilds. See BC issues #11/#12; the under-specified boards that need a full display rebuild are deferred to #13.
- **`apply_showcards_dummy.py`** — a build step (right after `CSV_to_PBN.py`, over `pbns/*.pbn`) that replaces each board's FROM directive with TO, scoped per board (the same directive text recurs across boards with different fixes). Idempotent and re-applied every build. Does **not** affect `[VersionToken]` (the token hashes only the deal + auction, not commentary).

### Debug Anchor Output

When `bbparse.py` runs, it generates debug files in `Tools/Anchors/` showing what was extracted from each HTML anchor. Example: `Anchors/NMF_deal01.txt` shows:

```
ANCHOR #1
----------------------------------------
Hands found: S

                    NORTH
                    (no hand)

WEST                          EAST
(no hand)                     (no hand)

                    SOUTH
                    S: QJ865
                    H: K92
                    D: AK
                    C: 863
```

Use these files to verify hand visibility is being detected correctly.

## File Locations

- `Tools/bbparse.py` - HTML parser, generates CSV
- `Tools/CSV_to_PBN.py` - CSV to PBN converter
- `Tools/BakerBridge.csv` - Parsed lesson data
- `Tools/pbns/` - Generated PBN files
- `Package/` - PBN files served via GitHub raw URLs

## Analysis Text Extraction

The `extract_analysis_text()` function extracts commentary from HTML `<td>` elements:

1. **Remove grey text**: Prior steps shown in grey `<font>` tags are stripped
2. **Remove nested tables**: Auction tables inside the TD are removed
3. **Extract full content**: All remaining text from the TD is captured

**Important**: The HTML uses `<br>` (not `<br/>`), so cleanup functions must handle both variants.

### Card Play Detection

The `extract_hands_by_anchor()` function detects played cards by comparing hands across sections:
- Tracks all four seats (N/E/S/W), not just N/S
- Cards in section N but missing in N+1 = played cards
- Generates `[PLAY N:SK,E:H5,S:H3,W:C2]` directives

## Bridge Classroom Integration

The Bridge Classroom app fetches PBN files from:
```
https://raw.githubusercontent.com/bridge-craftwork/Baker-Bridge/main/Package/{lesson}.pbn
```
(Issue #21, Phase B moved the build's output to a new `bridge-classroom/` folder; `Package/`
is a frozen orphan. Once BC repoints its props at `bridge-classroom/{lesson}.pbn`, update the
URL above. The re-rolled boards carry new `[VersionToken]`s — a board-identity change BC
coordinates per the producer contract.)

The app's `pbnParser.js` parses these directives and `useDealPractice.js` tracks state to control UI visibility.

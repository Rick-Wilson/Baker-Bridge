# Baker Bridge

A tool for extracting, validating, and repackaging bridge lesson content from the Baker Bridge website (bakerbridge.coffeecup.com) into standardized PBN (Portable Bridge Notation) and PDF formats.

## Build Layout: one master, two exports

The build produces a single master collection and then **diverges** into two committed exports for two different audiences. They are not chained through each other — both derive independently from the master.

```
                         Collection/            (master: merged, tokenized, manifest)
                         /          \
          bridge-classroom/          Presentation/ -> Rotations/
        (Bridge Classroom app)         (live face-to-face classes)
```

### Collection (the master)

`Collection/` is the shared intermediate the two exports diverge from: the merged, curated, token-stamped PBNs plus `manifest.json`, `toc.json`, and `titles.csv`. It is **regenerable and gitignored** — the committed artifacts are the two exports below. (`Collection/` replaced the old `Package/` in this role; `Package/` remains in the tree as a frozen orphan until Bridge Classroom repoints its props at `bridge-classroom/`.)

### bridge-classroom (for the Bridge Classroom app)

`bridge-classroom/` holds the **contracted files** served to the [Bridge Classroom](https://github.com/bridge-craftwork/Bridge-Classroom) web app: interactive PBNs (with `[show]`, `[BID]`, `[NEXT]`, … control directives), `manifest.json`, `toc.json`, `titles.csv`, and optional per-lesson `*_Intro.pdf` companions. The app renders lessons interactively with bidding prompts, hand-visibility control, and step-by-step analysis. This is the **Bridge Classroom producer contract** (`manifest.json`, schema v3).

### Rotations (for live teacher classes)

`Rotations/` holds PBN and PDF files organized for in-person instruction. Lessons are split into board sets (4/5/6 boards), rotated for different seat positions (South, North-South, all four hands), replicated across tables, and formatted with dealing sheets, dealer summaries, declarer plans, handouts, and bidding sheets — the files used with dealing machines in class. Its standard structure is a **second producer contract** (`Tools/rotations-contract.md`). Built from `Collection/` (control tags stripped), so its passers match the app exactly.

## Deterministic passer hands (issue #21)

Lessons specify only the bidding hands (usually N/S); the opponents' *passer* hands are generated. These are now made **BBA-clean and deterministic**:

- The `reroll` phase (`Tools/passer_reroll.py`) re-rolls every board whose E/W were generated and are the quiet (all-pass) side, **rejecting any fill a bidding engine (native BBA/EPBot) shows the opponents would bid** — then caches the result in the committed `Tools/passer_cache.csv`.
- The cache is keyed by board identity + bidding hands + auction, so builds are reproducible and machine-independent. This replaced a non-deterministic fill that had drifted between machines, causing dealer files and app handouts to disagree.

See `Tools/passer-fill-bba-redesign.md` and the phase write-ups (`passer-fill-phase0-audit.md`, `passer-fill-phase-a.md`, `passer-fill-phase-b.md`).

## Project Structure

```
Baker-Bridge/
+-- Website/            # HTTrack mirror of bakerbridge.coffeecup.com
+-- Tools/              # Build scripts and intermediate data
|   +-- bbparse.py      # HTML parser -> CSV
|   +-- CSV_to_PBN.py   # CSV -> PBN converter
|   +-- passer_reroll.py# BBA-reject passer fill (+ passer_cache.csv)
|   +-- audit_passers.py# BBA-reject audit / regression check
|   +-- build-deals.sh  # Deal set: HTML -> BakerBridgeFull.csv (rare; not reproducible)
|   +-- build-materials.sh # Packaging: the CSV -> published trees (idempotent)
|   +-- build-common.sh # Shared config/helpers for both
|   +-- pbns/           # Generated PBN + PDF files
|   +-- pdfs/           # Generated intro PDFs
|   +-- Anchors/        # Debug output from HTML parsing
|   +-- auction-fixes/  # SME corrections
+-- Curated/            # Hand-authored board overrides, merged at package time
+-- Collection/         # Master (gitignored, regenerable): merged + tokenized + manifest
+-- bridge-classroom/   # EXPORT -> Bridge Classroom app (PBN + manifest + toc + titles + intros)
+-- Presentation/       # Intermediate for Rotations: by category, control tags stripped
+-- Rotations/          # EXPORT -> live classes (rotated, sliced, with dealing sheets)
+-- Package/            # Frozen orphan (former app folder; pending BC cutover)
```

> **Note:** the previous Windows toolchain (PowerShell scripts, `-windows` caches, SSH-to-Windows BBA validation) was removed. See `Tools/windows-build-legacy.md`; the detail lives in git history.

## Prerequisites

- Python 3.x with BeautifulSoup4 (`pip install beautifulsoup4`)
- **dealer3** (Rust) — generates/deals constrained hands (`~/Development/GitHub/dealer3`)
- **bba-cli** (Rust, native Mac BBA/EPBot) — the passer-fill BBA-reject backend, with `--auction-prefix` (`~/Development/GitHub/BBA-tools/bba-cli`)
- **bridge-wrangler**, **pdf-handouts** (Rust) — PBN-to-PDF, hand rotations, and handout rendering for the `rotate` phase
- html2pdf (optional) — for regenerating lesson intro pages: `brew install ilaborie/tap/html2pdf`

## Quick Start

```bash
cd Tools

# Build the app export (Collection -> bridge-classroom)
./build-materials.sh classroom

# Build the teaching materials (Collection -> Presentation -> Rotations)
./build-materials.sh rotations

# Regenerate the deal set itself (rare - see the warning below)
./build-deals.sh '*'
./build-deals.sh '*' --generate          # also re-deal with dealer3 (slow)

# Re-validate cached passer fills against BBA (otherwise the cache is trusted)
REROLL_ARGS=--revalidate ./build-deals.sh reroll
```

`BB_PACKAGE_DIR` overrides the master folder (default `Collection/`); the package/stamp/manifest/toc/presentation/audit scripts all honor it.

## Build Pipeline

The build is **two scripts**, split at `BakerBridgeFull.csv` — the deal set of record.
They have opposite characters, and that is the whole point of the split:

| | `build-deals.sh` | `build-materials.sh` |
|---|---|---|
| Produces | `BakerBridgeFull.csv` | `Collection/`, `bridge-classroom/`, `Presentation/`, `Rotations/` |
| Reproducible? | **No** — `generate` deals fresh hands, and `bb_fill`'s E/W assignment is an unseeded shuffle | **Yes** — same CSV in, byte-identical output |
| Changes board identity? | **Yes** — new deals mean new `[VersionToken]`s, and Bridge Classroom keys mastery and problem reports off those | Never |
| Run it | rarely, and deliberately, when the *deals* must change | freely, for any packaging change |

> The source HTML never changes, and `parse`/`validate`/`correct`/`sme` are deterministic: a
> full re-run reproduces `BakerBridge.csv`, `BakerBridge-sme.csv`, `constructed_hands.csv`
> and `passer_cache.csv` byte for byte. **Only `fill` moves.** That is why the seam is where
> it is.

`build-mac.sh` remains as a shim that forwards to `build-materials.sh`, since its old
`classroom`/`rotations` shortcuts ran both halves — meaning a packaging change silently
re-dealt hands.

### Reproducible output

`build-materials.sh` re-run on an unchanged deal set leaves a **clean `git status`**. Every
generated PBN carries `%Created:`, and bridge-wrangler passes it through unchanged, so a
wall-clock stamp would rewrite ~3,000 files out to `Rotations/` on every run and bury real
changes in noise. The stamp is therefore derived from the input: `BB_BUILD_DATE` if set,
else the deal set's last git commit date, else its mtime (`resolve_build_time()` in
`CSV_to_PBN.py`; `resolve_build_date()` in `build-common.sh` does the same for `toc.json`
and `stats.json`).

```
HTML Files -> bbparse.py -> BakerBridge.csv
                               |
                     validate + correct + sme
                               |
                        BakerBridge-sme.csv
                               |
               +---------------+---------------+
               |                               |
         [--generate]                   (reuse existing)
               |                               |
     missing -> generate             constructed_hands.csv
               |                               |
               +---------------+---------------+
                               |
                      fill -> BakerBridgeFull.csv
                               |
        reroll (passer_reroll.py, BBA-reject + passer_cache.csv)
                               |
                    CSV_to_PBN.py -> pbns/*.pbn
                               |
             package_results.py (+ Curated merge) -> Collection/
                               |
       stamp_board_tokens.py + generate_manifest.py -> Collection/
                               |
                  +------------+-------------------+
                  |                                |
             (classroom)                     (rotations)
        export -> bridge-classroom/     package_presentation.py -> Presentation/
                                                   |
                                       package.sh (shared) -> Rotations/
```

### Build Phases

| Phase | Script | Description |
|-------|--------|-------------|
| **parse** | `bbparse.py` | Parse HTML lessons, extract hands/auctions/analysis -> `BakerBridge.csv` |
| **validate** | `bbcheck.py` | Check for card data errors -> `bbcheck.txt` |
| **correct** | `bb_correct.py` | Auto-fix duplicate card errors |
| **sme** | `apply_sme_corrections.py` | Apply subject-matter-expert corrections -> `BakerBridge-sme.csv` |
| **missing** | `check_missing_bids.py` | Find deals where an opponent bids but has no cards -> `missing_bids.csv` |
| **generate** | `fill_hands.py` | Generate constrained *interference* hands using dealer3 -> `constructed_hands.csv` |
| **fill** | `bb_fill.py` | Merge generated hands into full dataset -> `BakerBridgeFull.csv` |
| **reroll** | `passer_reroll.py` | BBA-reject re-roll of generated quiet passers (deterministic, cached) |
| **pbn** | `CSV_to_PBN.py` | Convert CSV to PBN files -> `pbns/`; generate `toc.json` |
| **package** | `package_results.py` | Copy PBNs (+ intro PDFs) to `Collection/`, merge `Curated/` overrides |
| **stamp** | `stamp_board_tokens.py` + `generate_manifest.py` | Stamp `[VersionToken]`s, emit `manifest.json` |
| **export** | (build-materials.sh) | Copy the contract files `Collection/` -> `bridge-classroom/` |
| **presentation** | `package_presentation.py` | Organize `Collection/` into `Presentation/` by category, strip interactive directives |
| **rotate** | the shared `package.sh` (bridge-lesson-packaging) | Slice into board sets, rotate hands, generate dealing sheets -> `Rotations/` |
| **manifest** | the shared `rotations_manifest.py` | Navigation index of `Rotations/` (category → lesson → set size → set → view + intro) -> `Rotations/manifest.json` |
| **publish** | (build-materials.sh) | Publish `Rotations/` to the public Google Drive teacher folder (delete + bulk copy) |

### The --generate Flag

The **generate** phase (running dealer3 to produce `constructed_hands.csv`) is the slowest step, and lives in `build-deals.sh`. By default it is skipped and the existing `constructed_hands.csv` reused. Pass `--generate` to regenerate it. Note the **reroll** phase separately reuses the committed `passer_cache.csv` unless `REROLL_ARGS=--revalidate` is set.

### Running Individual Phases

```bash
./build-deals.sh parse           # Just re-parse the HTML
./build-deals.sh reroll          # Just re-roll passers (uses the cache)
./build-materials.sh export      # Just re-export bridge-classroom from Collection
./build-materials.sh rotate      # Just redo rotations
./build-materials.sh '*'         # Run every packaging phase
./build-materials.sh --clean '*' # Clean artifacts, then run every packaging phase
```

### Publishing to Google Drive

Teachers can pull `Rotations/` from GitHub, but the easier-to-access copy is a public-readable
Google Drive folder. The `publish` phase replaces that folder with the current `Rotations/`
(mass-delete + one bulk copy — far faster than per-file sync on the Google Drive mount, and it
inherently drops anything no longer in the master):

```bash
./build-materials.sh publish                    # mirror the whole Rotations tree
./build-materials.sh publish --lesson Ogust     # publish just one lesson folder
PUBLISH_ARGS=-n ./build-materials.sh publish    # dry-run (show what would change)
```

`publish` is intentionally **not** part of the `classroom`/`rotations` shortcuts or `'*'` — it
pushes to a public drive, so it is always an explicit step. The target defaults to the
maintainer's Drive path; override with `BB_PUBLISH_DIR`.

## Data Files

| File | Description |
|------|-------------|
| `BakerBridge.csv` | Initial extraction from HTML (partial hands) |
| `BakerBridge-sme.csv` | After SME corrections applied |
| `BakerBridgeFull.csv` | Complete dataset with all four hands filled |
| `constructed_hands.csv` | Generated interference-opponent hands satisfying bidding constraints |
| `passer_cache.csv` | Committed BBA-clean quiet-passer fills (deterministic, keyed by board identity) |
| `missing_bids.csv` | Deals requiring constrained hand generation |
| `titles.csv` | Lesson-to-category folder mapping (in `Collection/`/`bridge-classroom/`) |

## PBN Control Directives

The PBN files include custom directives that control the Bridge Classroom app:

| Directive | Purpose |
|-----------|---------|
| `[show S]`, `[show NS]`, `[show NESW]` | Control which hands are visible |
| `[NEXT]` | End of step, show Next button |
| `[ROTATE]` | Like NEXT but rotates the table view |
| `[BID X]` | Prompt student to bid (X = expected bid) |
| `[PLAY N:SK,S:H3]` | Mark cards as played |
| `[RESET]` | Reset hands to original state |
| `[AUCTION on/off]` | Show/hide the auction table |
| `[SHOW_LEAD]` | Display the opening lead banner |

Board-identity metadata (`[VersionToken]`, the `%bridge-classroom-stable` header) is stamped by `stamp_board_tokens.py`; see `CLAUDE.md` for the contract details.

## Lesson Categories

50 lessons organized into 7 categories:

1. **Basic Bidding** — Major/Minor suit openings, Notrump
2. **Bidding Conventions** — Stayman, Transfers, Blackwood, 2/1, etc.
3. **Competitive Bidding** — Overcalls, Doubles, DONT, Michaels
4. **Declarer Play** — Finesses, Entries, Squeezes, Elimination
5. **Defense** — Opening Leads, Signals, 2nd/3rd Hand Play
6. **Practice Deals** — 100 Miscellaneous, 100 NT Openings
7. **Partnership Bidding** — Progressive practice sets

## License

See [LICENSE](LICENSE) file.

## Acknowledgments

Content sourced from [Baker Bridge](https://bakerbridge.coffeecup.com/) with permission from the site owner.

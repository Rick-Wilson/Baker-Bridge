# Baker Bridge

A tool for extracting, validating, and repackaging bridge lesson content from the Baker Bridge website (bakerbridge.coffeecup.com) into standardized PBN (Portable Bridge Notation) and PDF formats suitable for use with bridge software.

## Overview

This project preserves and repackages educational bridge content created by Baker Bridge. The pipeline:

1. Mirrors the source website using HTTrack
2. Extracts bridge hands, auctions, and analysis from HTML
3. Validates and corrects card data
4. Generates missing opponent hands (East/West) that satisfy bidding constraints
5. Converts to PBN and PDF formats
6. Organizes into lesson categories for presentation

## Project Structure

```
Baker-Bridge/
├── Website/           # HTTrack mirror of bakerbridge.coffeecup.com (source preservation)
├── Tools/             # Build scripts and intermediate data
│   ├── pbns/          # Generated PBN files by lesson
│   ├── pdfs/          # Generated PDF files
│   └── Archive/       # Previous script versions
├── Package/           # Intermediate build output (PBN, PDF, CSV)
├── Presentation/      # Final organized output by category
│   ├── 1. Basic Bidding/
│   ├── 2. Bidding Conventions/
│   ├── 3. Competitive Bidding/
│   ├── 4. Declarer Play/
│   ├── 5. Defense/
│   ├── 6. Practice Deals/
│   └── 7. Partnership Bidding/
└── Rotations/         # Hand rotations for different seat positions
```

## Prerequisites

### macOS

- Python 3.x with BeautifulSoup4 (`pip install beautifulsoup4`)
- HTTrack (for initial website mirror): `brew install httrack`
- dealer (for generating constrained hands): [dealer for macOS](https://github.com/dealer)
- BridgeComposer or equivalent for PBN to PDF conversion

## Build Pipeline

The build process consists of 12 steps. See `Tools/Baker Bridge Hand Extraction Workflow.pdf` for detailed documentation.

### Step 1: Mirror Website (HTTrack)

```bash
# Already completed - Website/ folder contains the mirror
httrack "https://bakerbridge.coffeecup.com/" -O "./Website"
```

### Step 2: Parse HTML and Extract Hands

```bash
cd Tools
python bbparse.py
# Output: BakerBridge.csv (1173 hands across 48 lessons)
```

### Step 3: Validate Card Data

```bash
python bbcheck.py
# Output: bbcheck.txt (validation report)
```

### Step 4: Auto-Correct Duplicate Cards

```bash
python bb_correct.py --apply
# Fixes duplicate card errors in CSV and source HTML
```

### Step 5: Identify Hands with Missing Bidders

```bash
python check_missing_bids.py
# Output: missing_bids.csv (hands where East/West bid but have no cards)
```

### Step 6: Generate Constrained Hands

Uses `dealer` to generate East/West hands that satisfy bidding constraints (e.g., a 1NT opener must have 15-17 HCP).

```bash
# Uses auction_templates.dlr for constraints
dealer -s auction_templates.dlr
# Output: constructed_hands.csv
```

### Step 7: Fill Missing Hands

```bash
python bb_fill.py
# Merges constructed hands + random balanced generation
# Output: BakerBridgeFull.csv
```

### Step 8: Convert to PBN Format

```bash
python CSV_to_PBN.py
# Output: pbns/ directory with organized PBN files
```

### Step 9: Convert Introduction Pages to PDF

```bash
python Convert_deal00_to_PDF.py
# Converts lesson intro pages to PDF format
```

### Step 10: Convert PBNs to PDFs

Requires BridgeComposer or equivalent PBN-to-PDF converter.

```bash
# macOS: Use BridgeComposer application
# Batch convert all PBN files in pbns/ to pdfs/
```

### Step 11: Package Results

```bash
python package_results.py
# Copies PBNs and PDFs to Package/ folder
```

### Step 12: Create Presentation Structure

```bash
python package_presentation.py
# Organizes into Presentation/ folder by category
# Cleans up interactive UI elements
# Adjusts formatting for different lesson levels

python split_pbns_into_sets.py
# Splits large lessons into 4/5/6-board practice sets
```

## Data Files

| File | Description |
|------|-------------|
| `BakerBridge.csv` | Initial extraction (1173 hands) |
| `BakerBridgeFull.csv` | Complete data with filled hands |
| `constructed_hands.csv` | Generated hands satisfying bid constraints |
| `missing_bids.csv` | Hands requiring constrained generation |
| `titles.csv` | Lesson-to-category mapping |
| `StandardHeader.pbn` | PBN file header template |
| `auction_templates.dlr` | Dealer constraints for hand generation |

## Lesson Categories

The 48 lessons are organized into 7 categories:

1. **Basic Bidding** - Major/Minor suit openings, Notrump
2. **Bidding Conventions** - Stayman, Transfers, Blackwood, 2/1, etc.
3. **Competitive Bidding** - Overcalls, Doubles, DONT, Michaels
4. **Declarer Play** - Finesses, Entries, Squeezes, Elimination
5. **Defense** - Opening Leads, Signals, 2nd/3rd Hand Play
6. **Practice Deals** - 100 Miscellaneous, 100 NT Openings
7. **Partnership Bidding** - Progressive practice sets (Sets 1-12)

## Statistics

- **Total hands:** 1,173
- **Lesson categories:** 48
- **Lesson types:** BID, NEXT, ROTATE variations
- **Hands requiring constrained generation:** 218
- **Hands with random balanced fill:** 753

## License

See [LICENSE](LICENSE) file.

## Acknowledgments

Content sourced from [Baker Bridge](https://bakerbridge.coffeecup.com/) with permission from the site owner.

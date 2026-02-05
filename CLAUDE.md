# Baker Bridge - Claude Code Notes

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

### Step 2: CSV to PBN (CSV_to_PBN.py)

Converts CSV data to PBN format with control directives for the Bridge Classroom app.

## HTML Section Structure

Each deal in the HTML has numbered anchor sections (`<a name="1">`, `<a name="2">`, etc.). Each section contains:
- A table with the bridge diagram (N/S/E/W hands)
- The auction table
- Analysis text
- A NEXT/ROTATE button linking to the next section

### Hand Visibility Detection

The app needs to show/hide hands based on what's visible in each HTML section. Key logic in `extract_hands_by_anchor()`:

1. **Extract hands from each section**: Parse the table to find N/S/E/W hands
   - North: `<td>` with `width:6em/7em/8em` style containing all 4 suit symbols
   - South: `<td>` with `height:800px` containing all 4 suit symbols
   - E/W: In the row containing `t1.gif` image, first and third `<td>` elements

2. **Compare consecutive sections**:
   - **Played cards**: Cards in section N but not in section N+1 = cards played
   - **E/W visibility**: If E/W hands appear in section N+1 but not in N → add `[show NESW]`

3. **Generate directives**:
   - `[PLAY N:SK,S:H3]` - Cards that were played
   - `[show NESW]` - When E/W hands become visible
   - `[RESET]` - After "complete deal" text to show original hands

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

## Directive Injection Logic (CSV_to_PBN.py)

For declarer play lessons (Student=S with [NEXT] tags):
1. Add `[show NS]` at the start (only show declarer's partnership)
2. After first `[NEXT]`: inject `[AUCTION off]` and `[SHOW_LEAD]`
3. The `[show NESW]` comes from bbparse.py when E/W hands appear in HTML

The timing matches Baker Bridge behavior:
- Step 1: Auction visible, only N/S hands shown
- After clicking NEXT: Auction hidden, lead shown, all hands visible (if E/W appear in HTML)

## Running the Build

```bash
cd Tools

# Parse HTML to CSV
python3 bbparse.py

# Convert CSV to PBN (uses BakerBridge.csv by default)
python3 CSV_to_PBN.py BakerBridge.csv

# Output goes to Tools/pbns/
# Copy to Package/ for GitHub distribution
cp pbns/*.pbn ../Package/
```

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
https://raw.githubusercontent.com/Rick-Wilson/Baker-Bridge/main/Package/{lesson}.pbn
```

The app's `pbnParser.js` parses these directives and `useDealPractice.js` tracks state to control UI visibility.

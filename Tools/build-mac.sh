#!/bin/bash
#
# build-mac.sh - Mac build pipeline for Baker Bridge lesson collection
#
# This script runs the complete build process using Rust tools (dealer3, bridge-wrangler)
# instead of Windows tools (dealer.exe, BridgeComposer).
#
# Usage:
#   ./build-mac.sh [--clean] [--skip-parse] [--skip-fill] [--skip-rotate] [--help]
#
# Options:
#   --clean        Remove existing build artifacts before building
#   --skip-parse   Skip HTML parsing (use existing BakerBridge.csv)
#   --skip-fill    Skip hand generation (use existing constructed_hands.csv)
#   --skip-rotate  Skip rotation generation (use existing Rotations/)
#   --help         Show this help message
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

# Tool paths
DEALER_PATH="$HOME/Development/GitHub/dealer3/target/release/dealer"
BRIDGE_WRANGLER_PATH="$HOME/Development/GitHub/bridge-wrangler/target/release/bridge-wrangler"

# Parse arguments
CLEAN=false
SKIP_PARSE=false
SKIP_FILL=false
SKIP_ROTATE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --clean)
            CLEAN=true
            shift
            ;;
        --skip-parse)
            SKIP_PARSE=true
            shift
            ;;
        --skip-fill)
            SKIP_FILL=true
            shift
            ;;
        --skip-rotate)
            SKIP_ROTATE=true
            shift
            ;;
        --help|-h)
            head -20 "$0" | tail -16
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Helper functions
step() {
    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}Step $1: $2${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

warn() {
    echo -e "${YELLOW}Warning: $1${NC}"
}

error() {
    echo -e "${RED}Error: $1${NC}"
    exit 1
}

check_tool() {
    if [[ ! -x "$1" ]]; then
        error "$2 not found at $1. Please build it first."
    fi
}

# Change to Tools directory
cd "$SCRIPT_DIR"

echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║       Baker Bridge Mac Build Pipeline                      ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "Repository: $REPO_ROOT"
echo "Tools dir:  $SCRIPT_DIR"

# Check required tools
echo ""
echo "Checking required tools..."
check_tool "$DEALER_PATH" "dealer3"
check_tool "$BRIDGE_WRANGLER_PATH" "bridge-wrangler"
if command -v html2pdf &> /dev/null; then
    echo -e "${GREEN}✓${NC} html2pdf found"
else
    warn "html2pdf not found - intro PDFs will be skipped"
    warn "Install with: brew install ilaborie/tap/html2pdf"
fi
echo -e "${GREEN}✓${NC} Required tools found"

# Clean if requested
if [[ "$CLEAN" == true ]]; then
    step "0" "Cleaning build artifacts"
    rm -rf pbns pdfs constructed_hands.csv BakerBridgeFull.csv
    rm -rf "$REPO_ROOT/Package" "$REPO_ROOT/Presentation" "$REPO_ROOT/Rotations"
    echo "Cleaned: pbns/, pdfs/, Package/, Presentation/, Rotations/, intermediate CSVs"
fi

# Step 2: Parse HTML and extract hands
if [[ "$SKIP_PARSE" == true ]]; then
    step "2" "Skipping HTML parsing (using existing BakerBridge.csv)"
else
    step "2" "Parse HTML and Extract Hands"
    if [[ ! -f "BakerBridge.csv" ]] || [[ "$CLEAN" == true ]]; then
        python3 bbparse.py
        echo "Output: BakerBridge.csv"
    else
        echo "BakerBridge.csv already exists, skipping (use --clean to regenerate)"
    fi
fi

# Verify BakerBridge.csv exists
if [[ ! -f "BakerBridge.csv" ]]; then
    error "BakerBridge.csv not found. Run without --skip-parse first."
fi

# Step 3: Validate card data
step "3" "Validate Card Data"
python3 bbcheck.py BakerBridge.csv > bbcheck.txt
ERRORS=$(grep -c "ERROR" bbcheck.txt 2>/dev/null || echo "0")
echo "Output: bbcheck.txt (found $ERRORS errors)"

# Step 4: Auto-correct duplicate cards
step "4" "Auto-Correct Duplicate Cards"
python3 bb_correct.py BakerBridge.csv --apply 2>/dev/null || true
echo "Applied corrections to BakerBridge.csv"

# Step 5: Identify hands with missing bidders
step "5" "Identify Hands with Missing Bidders"
python3 check_missing_bids.py BakerBridge.csv missing_bids.csv
MISSING=$(wc -l < missing_bids.csv | tr -d ' ')
echo "Output: missing_bids.csv ($((MISSING - 1)) hands need generation)"

# Step 6: Generate constrained hands (Mac version using dealer3)
if [[ "$SKIP_FILL" == true ]]; then
    step "6" "Skipping hand generation (using existing constructed_hands.csv)"
else
    step "6" "Generate Constrained Hands (using dealer3)"
    python3 fill_hands.py --dealer "$DEALER_PATH"
    GENERATED=$(wc -l < constructed_hands.csv | tr -d ' ')
    echo "Output: constructed_hands.csv ($((GENERATED - 1)) hands generated)"
fi

# Verify constructed_hands.csv exists
if [[ ! -f "constructed_hands.csv" ]]; then
    error "constructed_hands.csv not found. Run without --skip-fill first."
fi

# Step 7: Fill missing hands
step "7" "Fill Missing Hands"
python3 bb_fill.py BakerBridge.csv BakerBridgeFull.csv constructed_hands.csv
TOTAL=$(wc -l < BakerBridgeFull.csv | tr -d ' ')
echo "Output: BakerBridgeFull.csv ($((TOTAL - 1)) total hands)"

# Step 8: Convert to PBN format
step "8" "Convert to PBN Format"
python3 CSV_to_PBN.py BakerBridgeFull.csv StandardHeader.pbn "Baker Bridge Collection"
PBN_COUNT=$(find pbns -name "*.pbn" | wc -l | tr -d ' ')
echo "Output: pbns/ ($PBN_COUNT PBN files)"

# Step 9: Convert introduction pages to PDF (using html2pdf)
step "9" "Convert Introduction Pages to PDF (using html2pdf)"
if command -v html2pdf &> /dev/null; then
    ./convert_html_to_pdf.sh 2>&1 | grep -E "^(Converting:|Conversion|  Total|  Converted|  Failed)"
    INTRO_PDF_COUNT=$(find pdfs -name "*.pdf" 2>/dev/null | wc -l | tr -d ' ')
    echo "Output: pdfs/ ($INTRO_PDF_COUNT intro PDFs)"
else
    warn "Skipping - html2pdf not found"
    warn "Install with: brew install ilaborie/tap/html2pdf"
    mkdir -p pdfs
fi

# Step 10: Convert PBNs to PDFs (Mac version using bridge-wrangler)
step "10" "Convert PBNs to PDFs (using bridge-wrangler)"
python3 convert_pbns_to_pdfs.py --bridge-wrangler "$BRIDGE_WRANGLER_PATH"
PDF_COUNT=$(find pbns -name "*.pdf" | wc -l | tr -d ' ')
echo "Generated $PDF_COUNT PDF files alongside PBNs"

# Step 11: Package results
step "11" "Package Results"
mkdir -p "$REPO_ROOT/Package"
python3 package_results.py
# Copy titles.csv if it exists in the reference
if [[ -f "$REPO_ROOT/Package-windows/titles.csv" ]]; then
    cp "$REPO_ROOT/Package-windows/titles.csv" "$REPO_ROOT/Package/"
fi
PKG_COUNT=$(find "$REPO_ROOT/Package" -type f | wc -l | tr -d ' ')
echo "Output: Package/ ($PKG_COUNT files)"

# Step 12: Create presentation structure
step "12" "Create Presentation Structure"
cd "$REPO_ROOT"
python3 Tools/package_presentation.py
PRES_COUNT=$(find "$REPO_ROOT/Presentation" -type f | wc -l | tr -d ' ')
echo "Output: Presentation/ ($PRES_COUNT files)"

# Step 13: Generate rotations for multi-table play
if [[ "$SKIP_ROTATE" == true ]]; then
    step "13" "Skipping rotation generation (using existing Rotations/)"
    ROT_COUNT=$(find "$REPO_ROOT/Rotations" -type f 2>/dev/null | wc -l | tr -d ' ')
else
    step "13" "Generate Rotations (using bridge-wrangler)"
    cd "$REPO_ROOT"
    # Run rotation script with all lessons and standard board set sizes
    ./Tools/rotate_lesson_collection.sh "*" "*" 4 5 6
    ROT_COUNT=$(find "$REPO_ROOT/Rotations" -type f | wc -l | tr -d ' ')
    echo "Output: Rotations/ ($ROT_COUNT files)"
fi

# Summary
echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║       Build Complete                                       ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "Build artifacts:"
echo "  - Tools/pbns/          : $PBN_COUNT PBN files + $PDF_COUNT PDFs"
echo "  - Package/             : $PKG_COUNT files"
echo "  - Presentation/        : $PRES_COUNT files"
echo "  - Rotations/           : $ROT_COUNT files"
echo ""
echo "Reference artifacts (from Windows build):"
echo "  - Package-windows/"
echo "  - Presentation-windows/"
echo "  - Rotations-windows/"
echo "  - Tools/pbns-windows/"
echo ""

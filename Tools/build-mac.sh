#!/bin/bash
#
# build-mac.sh - Mac build pipeline for Baker Bridge lesson collection
#
# This script runs the complete build process using Rust tools (dealer3, bridge-wrangler)
# instead of Windows tools (dealer.exe, BridgeComposer).
#
# Usage:
#   ./build-mac.sh [phase] [options]
#
# Phases:
#   (none)         Show list of available phases
#   *              Run all phases
#   parse          Parse HTML and extract hands
#   validate       Validate card data
#   correct        Auto-correct duplicate cards
#   sme            Apply SME corrections (dealer, card exchanges)
#   missing        Identify hands with missing bidders
#   generate       Generate constrained hands
#   fill           Fill missing hands
#   pbn            Convert to PBN format
#   intro-pdf      Convert introduction pages to PDF
#   pbn-pdf        Convert PBNs to PDFs
#   package        Package results
#   presentation   Create presentation structure
#   rotate         Generate rotations for multi-table play
#
# Options:
#   --clean        Remove existing build artifacts before building
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

# Build phases: name|description
PHASES=(
    "parse|Parse HTML and extract hands"
    "validate|Validate card data"
    "correct|Auto-correct duplicate cards"
    "sme|Apply SME corrections"
    "missing|Identify hands with missing bidders"
    "generate|Generate constrained hands"
    "fill|Fill missing hands"
    "pbn|Convert to PBN format"
    "intro-pdf|Convert introduction pages to PDF"
    "pbn-pdf|Convert PBNs to PDFs"
    "package|Package results"
    "presentation|Create presentation structure"
    "rotate|Generate rotations for multi-table play"
)

# Parse arguments
CLEAN=false
PHASE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --clean)
            CLEAN=true
            shift
            ;;
        --help|-h)
            head -30 "$0" | tail -27
            exit 0
            ;;
        -*)
            echo "Unknown option: $1"
            exit 1
            ;;
        *)
            if [[ -z "$PHASE" ]]; then
                PHASE="$1"
            else
                echo "Error: Multiple phases specified"
                exit 1
            fi
            shift
            ;;
    esac
done

# Helper functions
step() {
    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}$1${NC}"
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

show_phases() {
    echo -e "${GREEN}Available build phases:${NC}"
    echo ""
    for entry in "${PHASES[@]}"; do
        local name="${entry%%|*}"
        local desc="${entry#*|}"
        printf "  %-14s %s\n" "$name" "$desc"
    done
    echo ""
    echo "Usage: ./build-mac.sh <phase>    Run a specific phase"
    echo "       ./build-mac.sh '*'        Run all phases"
    echo "       ./build-mac.sh --clean *  Clean and run all phases"
}

# Phase functions
phase_parse() {
    step "Parse HTML and Extract Hands"
    cd "$SCRIPT_DIR"
    python3 bbparse.py
    echo "Output: BakerBridge.csv"
}

phase_validate() {
    step "Validate Card Data"
    cd "$SCRIPT_DIR"
    if [[ ! -f "BakerBridge.csv" ]]; then
        error "BakerBridge.csv not found. Run 'parse' phase first."
    fi
    python3 bbcheck.py BakerBridge.csv > bbcheck.txt
    ERRORS=$(grep -c "ERROR" bbcheck.txt 2>/dev/null || true)
    ERRORS=${ERRORS:-0}
    echo "Output: bbcheck.txt (found $ERRORS errors)"
}

phase_correct() {
    step "Auto-Correct Duplicate Cards"
    cd "$SCRIPT_DIR"
    if [[ ! -f "BakerBridge.csv" ]]; then
        error "BakerBridge.csv not found. Run 'parse' phase first."
    fi
    python3 bb_correct.py BakerBridge.csv --apply 2>/dev/null || true
    echo "Applied corrections to BakerBridge.csv"
}

phase_sme() {
    step "Apply SME Corrections"
    cd "$SCRIPT_DIR"
    if [[ ! -f "BakerBridge.csv" ]]; then
        error "BakerBridge.csv not found. Run 'parse' phase first."
    fi
    if [[ -f "auction-fixes/sme_corrections.txt" ]]; then
        python3 auction-fixes/apply_sme_corrections.py
    else
        echo "No sme_corrections.txt found - skipping"
    fi
}

phase_missing() {
    step "Identify Hands with Missing Bidders"
    cd "$SCRIPT_DIR"
    if [[ ! -f "BakerBridge-sme.csv" ]]; then
        error "BakerBridge-sme.csv not found. Run 'sme' phase first."
    fi
    python3 check_missing_bids.py BakerBridge-sme.csv missing_bids.csv
    MISSING=$(wc -l < missing_bids.csv | tr -d ' ')
    echo "Output: missing_bids.csv ($((MISSING - 1)) hands need generation)"
}

phase_generate() {
    step "Generate Constrained Hands (using dealer3)"
    cd "$SCRIPT_DIR"
    check_tool "$DEALER_PATH" "dealer3"
    if [[ ! -f "missing_bids.csv" ]]; then
        error "missing_bids.csv not found. Run 'missing' phase first."
    fi
    python3 fill_hands.py --dealer "$DEALER_PATH"
    GENERATED=$(wc -l < constructed_hands.csv | tr -d ' ')
    echo "Output: constructed_hands.csv ($((GENERATED - 1)) hands generated)"
}

phase_fill() {
    step "Fill Missing Hands"
    cd "$SCRIPT_DIR"
    if [[ ! -f "BakerBridge-sme.csv" ]]; then
        error "BakerBridge-sme.csv not found. Run 'sme' phase first."
    fi
    if [[ ! -f "constructed_hands.csv" ]]; then
        error "constructed_hands.csv not found. Run 'generate' phase first."
    fi
    python3 bb_fill.py BakerBridge-sme.csv BakerBridgeFull.csv constructed_hands.csv
    TOTAL=$(wc -l < BakerBridgeFull.csv | tr -d ' ')
    echo "Output: BakerBridgeFull.csv ($((TOTAL - 1)) total hands)"
}

phase_pbn() {
    step "Convert to PBN Format"
    cd "$SCRIPT_DIR"
    if [[ ! -f "BakerBridgeFull.csv" ]]; then
        error "BakerBridgeFull.csv not found. Run 'fill' phase first."
    fi
    python3 CSV_to_PBN.py BakerBridgeFull.csv StandardHeader.pbn "Baker Bridge Collection"
    PBN_COUNT=$(find pbns -name "*.pbn" | wc -l | tr -d ' ')
    echo "Output: pbns/ ($PBN_COUNT PBN files)"
}

phase_intro_pdf() {
    step "Convert Introduction Pages to PDF (using html2pdf)"
    cd "$SCRIPT_DIR"
    if command -v html2pdf &> /dev/null; then
        ./convert_html_to_pdf.sh 2>&1 | grep -E "^(Converting:|Conversion|  Total|  Converted|  Failed)"
        INTRO_PDF_COUNT=$(find pdfs -name "*.pdf" 2>/dev/null | wc -l | tr -d ' ')
        echo "Output: pdfs/ ($INTRO_PDF_COUNT intro PDFs)"
    else
        warn "Skipping - html2pdf not found"
        warn "Install with: brew install ilaborie/tap/html2pdf"
        mkdir -p pdfs
    fi
}

phase_pbn_pdf() {
    step "Convert PBNs to PDFs (using bridge-wrangler)"
    cd "$SCRIPT_DIR"
    check_tool "$BRIDGE_WRANGLER_PATH" "bridge-wrangler"
    if [[ ! -d "pbns" ]]; then
        error "pbns/ not found. Run 'pbn' phase first."
    fi
    python3 convert_pbns_to_pdfs.py --bridge-wrangler "$BRIDGE_WRANGLER_PATH"
    PDF_COUNT=$(find pbns -name "*.pdf" | wc -l | tr -d ' ')
    echo "Generated $PDF_COUNT PDF files alongside PBNs"
}

phase_package() {
    step "Package Results"
    cd "$SCRIPT_DIR"
    mkdir -p "$REPO_ROOT/Package"
    python3 package_results.py
    # Copy titles.csv if it exists in the reference
    if [[ -f "$REPO_ROOT/Package-windows/titles.csv" ]]; then
        cp "$REPO_ROOT/Package-windows/titles.csv" "$REPO_ROOT/Package/"
    fi
    PKG_COUNT=$(find "$REPO_ROOT/Package" -type f | wc -l | tr -d ' ')
    echo "Output: Package/ ($PKG_COUNT files)"
}

phase_presentation() {
    step "Create Presentation Structure"
    cd "$REPO_ROOT"
    python3 Tools/package_presentation.py
    PRES_COUNT=$(find "$REPO_ROOT/Presentation" -type f | wc -l | tr -d ' ')
    echo "Output: Presentation/ ($PRES_COUNT files)"
}

phase_rotate() {
    step "Generate Rotations (using bridge-wrangler)"
    cd "$REPO_ROOT"
    check_tool "$BRIDGE_WRANGLER_PATH" "bridge-wrangler"
    # Run rotation script with all lessons and standard board set sizes
    ./Tools/rotate_lesson_collection.sh "*" "*" 4 5 6
    ROT_COUNT=$(find "$REPO_ROOT/Rotations" -type f | wc -l | tr -d ' ')
    echo "Output: Rotations/ ($ROT_COUNT files)"
}

do_clean() {
    step "Cleaning build artifacts"
    cd "$SCRIPT_DIR"
    rm -rf pbns pdfs constructed_hands.csv BakerBridgeFull.csv
    rm -rf "$REPO_ROOT/Package" "$REPO_ROOT/Presentation" "$REPO_ROOT/Rotations"
    echo "Cleaned: pbns/, pdfs/, Package/, Presentation/, Rotations/, intermediate CSVs"
}

run_phase() {
    local phase="$1"
    case "$phase" in
        parse)        phase_parse ;;
        validate)     phase_validate ;;
        correct)      phase_correct ;;
        sme)          phase_sme ;;
        missing)      phase_missing ;;
        generate)     phase_generate ;;
        fill)         phase_fill ;;
        pbn)          phase_pbn ;;
        intro-pdf)    phase_intro_pdf ;;
        pbn-pdf)      phase_pbn_pdf ;;
        package)      phase_package ;;
        presentation) phase_presentation ;;
        rotate)       phase_rotate ;;
        *)
            echo "Unknown phase: $phase"
            echo ""
            show_phases
            exit 1
            ;;
    esac
}

run_all_phases() {
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

    # Run all phases
    for entry in "${PHASES[@]}"; do
        local name="${entry%%|*}"
        run_phase "$name"
    done

    # Summary
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║       Build Complete                                       ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    PBN_COUNT=$(find "$SCRIPT_DIR/pbns" -name "*.pbn" 2>/dev/null | wc -l | tr -d ' ')
    PDF_COUNT=$(find "$SCRIPT_DIR/pbns" -name "*.pdf" 2>/dev/null | wc -l | tr -d ' ')
    PKG_COUNT=$(find "$REPO_ROOT/Package" -type f 2>/dev/null | wc -l | tr -d ' ')
    PRES_COUNT=$(find "$REPO_ROOT/Presentation" -type f 2>/dev/null | wc -l | tr -d ' ')
    ROT_COUNT=$(find "$REPO_ROOT/Rotations" -type f 2>/dev/null | wc -l | tr -d ' ')
    echo "Build artifacts:"
    echo "  - Tools/pbns/          : $PBN_COUNT PBN files + $PDF_COUNT PDFs"
    echo "  - Package/             : $PKG_COUNT files"
    echo "  - Presentation/        : $PRES_COUNT files"
    echo "  - Rotations/           : $ROT_COUNT files"
    echo ""
}

# Main execution
if [[ "$CLEAN" == true ]]; then
    do_clean
fi

if [[ -z "$PHASE" ]]; then
    show_phases
    exit 0
elif [[ "$PHASE" == "*" ]]; then
    run_all_phases
else
    run_phase "$PHASE"
fi

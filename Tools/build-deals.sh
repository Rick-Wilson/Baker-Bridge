#!/bin/bash
#
# build-deals.sh - the deal set: HTML lessons -> BakerBridgeFull.csv
#
# THIS HALF IS NOT REPRODUCIBLE, BY NATURE. `generate` deals fresh hands with dealer3, and
# `fill` assigns the leftover cards to E/W with an unseeded shuffle, so a re-run can produce
# a different deal set even from identical inputs. Different deals mean different
# [VersionToken]s, and Bridge Classroom keys mastery and problem reports off those -- so
# re-running this discards student history for every board that moves.
#
# Run it when the *deals* need to change. It is not a prerequisite for packaging changes:
# for those, run build-materials.sh, which is a pure function of the CSV this produces.
#
# The source HTML never changes, and parse/validate/correct/sme are deterministic -- a full
# re-run reproduces BakerBridge.csv, BakerBridge-sme.csv, constructed_hands.csv and
# passer_cache.csv byte for byte. Only `fill` moves.
#
# Usage:
#   ./build-deals.sh [phase] [options]
#
#   (none)         Show the available phases
#   *              Run every phase (reusing constructed_hands.csv unless --generate)
#   parse          Parse HTML and extract hands
#   validate       Validate card data
#   correct        Auto-correct duplicate cards
#   sme            Apply SME corrections (dealer, card exchanges)
#   missing        Identify hands with missing bidders
#   generate       Generate constrained hands (dealer3; slow)
#   fill           Fill missing hands
#   reroll         Re-roll quiet passers (BBA-reject, cached)
#
# Options:
#   --generate     Regenerate constrained hands (otherwise constructed_hands.csv is reused)
#   --help         Show this message
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/build-common.sh"

PHASES=(
    "parse|Parse HTML and extract hands"
    "validate|Validate card data"
    "correct|Auto-correct duplicate cards"
    "sme|Apply SME corrections"
    "missing|Identify hands with missing bidders"
    "generate|Generate constrained hands"
    "fill|Fill missing hands"
    "reroll|Re-roll quiet passers (BBA-reject, managed variety)"
)

GENERATE=false
PHASE=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --generate) GENERATE=true; shift ;;
        --help|-h)  head -34 "$0" | tail -31; exit 0 ;;
        -*)         echo "Unknown option: $1"; exit 1 ;;
        *)
            if [[ -z "$PHASE" ]]; then PHASE="$1"; else echo "Error: Multiple phases specified"; exit 1; fi
            shift ;;
    esac
done

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

phase_reroll() {
    step "Re-roll Passer Hands (BBA-reject, managed variety)"
    cd "$SCRIPT_DIR"
    if [[ ! -f "BakerBridgeFull.csv" ]]; then
        error "BakerBridgeFull.csv not found. Run 'fill' phase first."
    fi
    # Unified BBA-reject re-roll of the generated *quiet* passers (issue #21, Phase B).
    # Supersedes both auction_calm (fill_hands) and bb_fill's random E/W assignment.
    # Reuses the committed passer_cache.csv; pass --revalidate (via REROLL_ARGS) to
    # re-check cached fills.
    python3 passer_reroll.py BakerBridgeFull.csv --sme BakerBridge-sme.csv \
        --cache passer_cache.csv $REROLL_ARGS
    echo "Output: BakerBridgeFull.csv (quiet passers BBA-clean) + passer_cache.csv"
}

# Report how far the deal set moved, so identity churn announces itself here rather than
# being discovered downstream. Compares against the committed CSV, board by board.
report_deal_drift() {
    cd "$SCRIPT_DIR"
    git diff --quiet -- "$DEALS_CSV" 2>/dev/null && {
        echo -e "${GREEN}Deal set unchanged${NC} - no board identity moved."
        return 0
    }
    python3 - "$DEALS_CSV" <<'PYEOF'
import csv, io, subprocess, sys
path = sys.argv[1]
old = subprocess.run(["git", "show", f"HEAD:./{path.split('/')[-1]}"],
                     capture_output=True, text=True).stdout
if not old:
    print("  (no committed version to compare against)")
    raise SystemExit
def deals(text):
    out = {}
    for row in csv.DictReader(io.StringIO(text)):
        key = (row.get("Lesson", ""), row.get("Deal", row.get("Board", "")))
        out[key] = tuple(row.get(s, "") for s in ("North", "East", "South", "West"))
    return out
a, b = deals(old), deals(open(path, encoding="utf-8").read())
moved = [k for k in a if k in b and a[k] != b[k]]
print(f"  boards whose hands changed: {len(moved)} of {len(a)}")
lessons = sorted({k[0] for k in moved})
for l in lessons[:12]:
    print(f"    {l}: {sum(1 for k in moved if k[0] == l)}")
if len(lessons) > 12:
    print(f"    ... and {len(lessons) - 12} more lessons")
PYEOF
}

run_phase() {
    case "$1" in
        parse)    phase_parse ;;
        validate) phase_validate ;;
        correct)  phase_correct ;;
        sme)      phase_sme ;;
        missing)  phase_missing ;;
        generate) phase_generate ;;
        fill)     phase_fill ;;
        reroll)   phase_reroll ;;
        *)
            echo "Unknown phase: $1"; echo ""
            echo -e "${GREEN}Phases:${NC}"; show_phase_table "${PHASES[@]}"; exit 1 ;;
    esac
}

if [[ -z "$PHASE" ]]; then
    echo -e "${GREEN}build-deals.sh${NC} - regenerate the deal set (rarely needed)"
    echo ""
    echo -e "${YELLOW}Re-running this can change the deals, and so the board identity${NC}"
    echo -e "${YELLOW}Bridge Classroom tracks mastery with. For packaging changes use build-materials.sh.${NC}"
    echo ""
    echo -e "${GREEN}Phases:${NC}"
    show_phase_table "${PHASES[@]}"
    echo ""
    echo -e "${GREEN}Options:${NC}"
    printf "  %-14s %s\n" "--generate" "Regenerate constrained hands with dealer3 (slow)"
    exit 0
fi

if [[ "$PHASE" != "*" ]]; then
    run_phase "$PHASE"
    exit 0
fi

echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║       Baker Bridge - Deal Set Build                        ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

phase_parse
phase_validate
phase_correct
phase_sme
if [[ "$GENERATE" == true ]]; then
    check_tool "$DEALER_PATH" "dealer3"
    phase_missing
    phase_generate
else
    cd "$SCRIPT_DIR"
    if [[ ! -f "constructed_hands.csv" ]]; then
        error "constructed_hands.csv not found. Run with --generate to create it."
    fi
    echo -e "\n${YELLOW}Reusing existing constructed_hands.csv${NC}"
fi
phase_fill
phase_reroll

step "Deal Set Drift"
report_deal_drift
echo ""
echo -e "${GREEN}Deal set build complete.${NC} Package it with: ./build-materials.sh rotations"

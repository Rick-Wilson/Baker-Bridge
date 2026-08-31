#!/bin/bash
#
# build-common.sh - shared configuration and helpers for the Baker Bridge build.
#
# Sourced by both halves of the build; not runnable on its own.
#
#   build-deals.sh      the deal set   (HTML -> BakerBridgeFull.csv)
#   build-materials.sh  the packaging  (BakerBridgeFull.csv -> the published trees)
#
# The two are split because they have opposite characters. build-deals.sh generates and
# fills hands, so it can produce a *different deal set* on each run -- bb_fill's E/W
# assignment is an unseeded shuffle -- and changing the deals changes board identity
# ([VersionToken]), which Bridge Classroom keys mastery and problem reports off. It is
# therefore run rarely and deliberately. build-materials.sh is a pure function of the CSV:
# the same input yields byte-identical output, so it can be re-run freely whenever the
# packaging changes.

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

REPO_ROOT="$(dirname "$SCRIPT_DIR")"

# Build folder layout (issue #21, Phase B). The merge+stamp+manifest steps write the
# shared master, Collection/ (replacing Package/'s old role; Package/ is a frozen orphan).
# Two exports diverge from Collection/ — they are NOT chained through each other:
#   - bridge-classroom/  the app's contracted files (control-tag PBNs + manifest/toc/titles
#                        + optional intros), copied out of Collection/ by the `export` phase.
#   - Presentation/ -> Rotations/  the face-to-face teaching materials (tags stripped, table
#                        rotations), built from Collection/ by presentation/rotate.
# BB_PACKAGE_DIR points the package/stamp/manifest/toc/presentation/audit scripts at the
# master; override it to rebuild elsewhere.
COLLECTION_DIR="${BB_PACKAGE_DIR:-$REPO_ROOT/Collection}"
BRIDGE_CLASSROOM_DIR="$REPO_ROOT/bridge-classroom"
export BB_PACKAGE_DIR="$COLLECTION_DIR"
# Back-compat alias: several helpers below still say PACKAGE_DIR meaning the master.
PACKAGE_DIR="$COLLECTION_DIR"

# Publish target: the public-readable Google Drive copy of Rotations/ that teachers use
# (easier to access than GitHub). Override with BB_PUBLISH_DIR.
PUBLISH_DIR="${BB_PUBLISH_DIR:-/Users/rick/Library/CloudStorage/GoogleDrive-bridge.craftwork@gmail.com/My Drive/For Teachers/Lesson Collections/Baker Bridge Collection}"

# The deal set of record: the seam between the two halves of the build.
DEALS_CSV="$SCRIPT_DIR/BakerBridgeFull.csv"

# Tool paths
DEALER_PATH="$HOME/Development/GitHub/dealer3/target/release/dealer"
BRIDGE_WRANGLER_PATH="$HOME/Development/GitHub/bridge-wrangler/target/release/bridge-wrangler"
# Shared (collection-agnostic) tools from bridge-lesson-packaging: the mixed-use materials
# packager (rotate/slice/handouts — replaces the retired local rotate_lesson_collection.sh)
# and the lesson-statistics tool. Clone github.com/bridge-craftwork/bridge-lesson-packaging,
# or override these paths.
export BRIDGE_WRANGLER_PATH   # package.sh renders its PDFs with the binary we check here
PACKAGER="${PACKAGER:-$HOME/Development/GitHub/bridge-lesson-packaging/package.sh}"
STATS_TOOL="${STATS_TOOL:-$HOME/Development/GitHub/bridge-lesson-packaging/stats.py}"
MANIFEST_TOOL="${MANIFEST_TOOL:-$HOME/Development/GitHub/bridge-lesson-packaging/rotations_manifest.py}"

# Build timestamp. Pinned to the deal set rather than the clock so that re-running the
# packaging half reproduces byte-identical output; see resolve_build_time() in
# CSV_to_PBN.py, which uses the same rule for the PBN "%Created:" stamp.
resolve_build_date() {
    if [[ -n "$BB_BUILD_DATE" ]]; then
        echo "$BB_BUILD_DATE"; return
    fi
    local d
    d=$(cd "$SCRIPT_DIR" && git log -1 --format=%cd --date=format:'%Y-%m-%dT%H:%M:%SZ' \
        -- "$DEALS_CSV" 2>/dev/null || true)
    if [[ -n "$d" ]]; then echo "$d"; else date -u +%Y-%m-%dT%H:%M:%SZ; fi
}

# Build-duration accumulator (label<TAB>seconds), reset at the start of a full build and read
# by the `stats` phase. `timed <label> <cmd...>` runs a phase and records how long it took.
BUILD_DURATIONS_TSV="$SCRIPT_DIR/.build-durations.tsv"

timed() {
    local label="$1"; shift
    local t0=$SECONDS
    "$@"; local rc=$?
    printf '%s\t%d\n' "$label" "$((SECONDS - t0))" >> "$BUILD_DURATIONS_TSV"
    return $rc
}

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

# Print a "name|description" phase table. Takes the entries as arguments (macOS ships
# bash 3.2, which has no namerefs), so call it as: show_phase_table "${PHASES[@]}"
show_phase_table() {
    local entry
    for entry in "$@"; do
        printf "  %-14s %s\n" "${entry%%|*}" "${entry#*|}"
    done
}

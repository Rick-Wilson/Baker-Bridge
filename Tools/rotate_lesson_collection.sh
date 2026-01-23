#!/bin/bash
#
# rotate_lesson_collection.sh - Mac version of rotate_lesson_collection.ps1
#
# This script operates from the current directory and takes positional parameters:
#   - filter: A folder name filter (e.g., "*lesson*", "Baker*")
#   - actions: One or more actions separated by commas
#   - slices: (Optional) A list of integer values for board set sizes
#
# Available actions:
#   - create_folders    : Create folder structure in Rotations mirroring Presentation
#   - copy_presentation : Copy .pbn and .pdf files from Presentation to Rotations
#   - pdf_presentation  : Convert .pbn files in Presentation to PDF
#   - slice_deals       : Split .pbn files into smaller sets (4-board, 5-board, etc.)
#   - rotate_hands      : Rotate hands using bridge-wrangler (S, NS, NESW patterns)
#   - block_replicate   : Replicate boards for multi-table play + dealer summary PDFs
#   - bidding_sheets    : Generate bidding practice sheets using pbn-to-pdf
#   - aggregate         : Organize files into Full Table, North-South, South subfolders
#
# Usage:
#   ./rotate_lesson_collection.sh <filter> <actions> [slices...]
#
# Examples:
#   ./rotate_lesson_collection.sh "*" create_folders,copy_presentation
#   ./rotate_lesson_collection.sh "Baker*" slice_deals,rotate_hands 4 5 6
#   ./rotate_lesson_collection.sh "*Finesse*" "*"   # Run all actions
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Tool paths
BRIDGE_WRANGLER_PATH="${BRIDGE_WRANGLER_PATH:-$HOME/Development/GitHub/bridge-wrangler/target/release/bridge-wrangler}"
PBN_TO_PDF_PATH="${PBN_TO_PDF_PATH:-$HOME/Development/GitHub/pbn-to-pdf/target/release/pbn-to-pdf}"

# Trace mode (set TRACE=1 to enable)
TRACE=${TRACE:-0}

trace() {
    if [[ "$TRACE" == "1" ]]; then
        echo -e "${BLUE}[Trace]${NC} $1"
    fi
}

warn() {
    echo -e "${YELLOW}Warning:${NC} $1"
}

error() {
    echo -e "${RED}Error:${NC} $1"
    exit 1
}

# Show usage
show_usage() {
    echo ""
    echo "Usage: $0 <filter> <actions> [slices...]"
    echo ""
    echo "Parameters:"
    echo "  filter   : A folder name filter (e.g., '*lesson*', 'Baker*', '*')"
    echo "  actions  : One or more actions (comma-separated or use shortcuts):"
    echo "             - create_folders"
    echo "             - copy_presentation"
    echo "             - pdf_presentation"
    echo "             - slice_deals"
    echo "             - rotate_hands"
    echo "             - block_replicate"
    echo "             - bidding_sheets"
    echo "             - aggregate"
    echo "             Shortcuts:"
    echo "             - '*' : Run all actions (except pdf_presentation)"
    echo "             - '+action' : Run from start through action"
    echo "             - 'action+' : Run from action through end"
    echo "  slices   : (Optional) Board set sizes (e.g., 4 5 6)"
    echo ""
    echo "Examples:"
    echo "  $0 '*' create_folders,copy_presentation"
    echo "  $0 'Baker*' slice_deals,rotate_hands 4 5 6"
    echo "  $0 '*Finesse*' '*' 4 5 6"
    echo ""
    exit 0
}

# Parse arguments
if [[ $# -lt 2 ]] || [[ "$1" == "-h" ]] || [[ "$1" == "--help" ]]; then
    show_usage
fi

FILTER="$1"
ACTIONS_ARG="$2"
shift 2
SLICES=("$@")

# All available actions (in order)
ALL_ACTIONS=(
    "create_folders"
    "copy_presentation"
    "pdf_presentation"
    "slice_deals"
    "rotate_hands"
    "block_replicate"
    "bidding_sheets"
    "aggregate"
)

# Actions included in wildcard expansion (excluding pdf_presentation)
EXPANDABLE_ACTIONS=(
    "create_folders"
    "copy_presentation"
    "slice_deals"
    "rotate_hands"
    "block_replicate"
    "bidding_sheets"
    "aggregate"
)

# Expand action shortcuts
expand_actions() {
    local input="$1"
    local -a result=()

    IFS=',' read -ra action_list <<< "$input"

    for action in "${action_list[@]}"; do
        action=$(echo "$action" | tr '[:upper:]' '[:lower:]' | xargs)

        if [[ "$action" == "*" ]]; then
            result+=("${EXPANDABLE_ACTIONS[@]}")
        elif [[ "$action" == +* ]]; then
            # +action means from start through action
            local target="${action:1}"
            local found=0
            for a in "${EXPANDABLE_ACTIONS[@]}"; do
                result+=("$a")
                if [[ "$a" == "$target" ]]; then
                    found=1
                    break
                fi
            done
            if [[ $found -eq 0 ]]; then
                error "Unknown action: $action"
            fi
        elif [[ "$action" == *+ ]]; then
            # action+ means from action through end
            local target="${action%+}"
            local started=0
            for a in "${EXPANDABLE_ACTIONS[@]}"; do
                if [[ "$a" == "$target" ]]; then
                    started=1
                fi
                if [[ $started -eq 1 ]]; then
                    result+=("$a")
                fi
            done
            if [[ $started -eq 0 ]]; then
                error "Unknown action: $action"
            fi
        else
            # Check if it's a valid action
            local valid=0
            for a in "${ALL_ACTIONS[@]}"; do
                if [[ "$a" == "$action" ]]; then
                    valid=1
                    break
                fi
            done
            if [[ $valid -eq 0 ]]; then
                error "Unknown action: $action"
            fi
            result+=("$action")
        fi
    done

    # Remove duplicates while preserving order
    printf '%s\n' "${result[@]}" | awk '!seen[$0]++'
}

# Get leaf folders from Presentation that match the filter
filter_folders() {
    local filter="$1"
    local base_dir="Presentation"

    if [[ ! -d "$base_dir" ]]; then
        error "'Presentation' folder not found in current directory."
    fi

    local exclude=0
    local pattern="$filter"

    if [[ "$pattern" == -* ]]; then
        exclude=1
        pattern="${pattern:1}"
    fi

    # Wrap pattern with wildcards
    if [[ -z "$pattern" ]]; then
        pattern="*"
    else
        pattern="*${pattern}*"
    fi

    # Find leaf folders (folders with no subdirectories)
    local -a leaf_folders=()
    while IFS= read -r -d '' dir; do
        # Check if this is a leaf folder (no subdirectories)
        if [[ -z "$(find "$dir" -mindepth 1 -maxdepth 1 -type d 2>/dev/null)" ]]; then
            leaf_folders+=("$dir")
        fi
    done < <(find "$base_dir" -type d -print0 2>/dev/null)

    # Filter by pattern
    local -a result=()
    for folder in "${leaf_folders[@]}"; do
        local rel_path="${folder#$base_dir/}"
        local folder_name=$(basename "$folder")

        # Case-insensitive pattern match (using shopt for bash 3 compatibility)
        local matches=0
        local folder_lower=$(echo "$folder_name" | tr '[:upper:]' '[:lower:]')
        local pattern_lower=$(echo "$pattern" | tr '[:upper:]' '[:lower:]')
        if [[ "$folder_lower" == $pattern_lower ]]; then
            matches=1
        fi

        if [[ ($exclude -eq 1 && $matches -eq 0) || ($exclude -eq 0 && $matches -eq 1) ]]; then
            result+=("$rel_path")
        fi
    done

    printf '%s\n' "${result[@]}" | sort
}

# Count boards in a PBN file
get_hand_count() {
    local file="$1"
    grep -c '^\[Board' "$file" 2>/dev/null || echo "0"
}

#---------------------------------------------------
# Action: create_folders
#---------------------------------------------------
action_create_folders() {
    local file="$1"
    trace "Executing create_folders for: $file"

    local src="Presentation/$file"
    local dst="Rotations/$file"

    if [[ ! -d "$src" ]]; then
        warn "Source folder not found: $src"
        return
    fi

    mkdir -p "$dst"
    trace "Created folder: $dst"
}

#---------------------------------------------------
# Action: copy_presentation
#---------------------------------------------------
action_copy_presentation() {
    local file="$1"
    trace "Executing copy_presentation for: $file"

    local src="Presentation/$file"
    local dst="Rotations/$file"

    if [[ ! -d "$src" ]]; then
        warn "Source folder not found: $src"
        return
    fi

    if [[ ! -d "$dst" ]]; then
        warn "Destination folder not found: $dst (run create_folders first)"
        return
    fi

    # Copy all .pbn files
    for pbn in "$src"/*.pbn; do
        [[ -f "$pbn" ]] || continue
        cp "$pbn" "$dst/"
        trace "Copied: $(basename "$pbn")"
    done

    # Copy .pdf files that don't have matching .pbn files
    for pdf in "$src"/*.pdf; do
        [[ -f "$pdf" ]] || continue
        local base=$(basename "$pdf" .pdf)
        if [[ ! -f "$src/$base.pbn" ]]; then
            cp "$pdf" "$dst/"
            trace "Copied PDF (no matching PBN): $(basename "$pdf")"

            # Also copy to board set folders if they exist
            for board_folder in "$dst"/*-Board\ Sets; do
                [[ -d "$board_folder" ]] || continue
                cp "$pdf" "$board_folder/"
            done
        fi
    done
}

#---------------------------------------------------
# Action: pdf_presentation
#---------------------------------------------------
action_pdf_presentation() {
    local file="$1"
    trace "Executing pdf_presentation for: $file"

    local folder="Presentation/$file"

    if [[ ! -d "$folder" ]]; then
        warn "Folder not found: $folder"
        return
    fi

    if [[ ! -x "$BRIDGE_WRANGLER_PATH" ]]; then
        warn "bridge-wrangler not found at $BRIDGE_WRANGLER_PATH"
        return
    fi

    for pbn in "$folder"/*.pbn; do
        [[ -f "$pbn" ]] || continue
        local pdf="${pbn%.pbn}.pdf"
        trace "Converting to PDF: $pbn"
        "$BRIDGE_WRANGLER_PATH" to-pdf -i "$pbn" -o "$pdf" || warn "Failed to convert: $pbn"
    done
}

#---------------------------------------------------
# Action: slice_deals
#---------------------------------------------------
action_slice_deals() {
    local file="$1"
    shift
    local slices=("$@")

    trace "Executing slice_deals for: $file with slices: ${slices[*]}"

    local folder="Rotations/$file"

    if [[ ! -d "$folder" ]]; then
        warn "Folder not found: $folder"
        return
    fi

    # Find the first .pbn file
    local pbn_file=$(find "$folder" -maxdepth 1 -name "*.pbn" -type f | head -1)

    if [[ -z "$pbn_file" ]]; then
        warn "No .pbn file found in $folder"
        return
    fi

    trace "Processing file: $pbn_file"

    local total_boards=$(get_hand_count "$pbn_file")
    local base_name=$(basename "$pbn_file" .pbn)

    trace "Found $total_boards boards"

    # Create All folder and copy with hand count in name
    local all_folder="$folder/All"
    mkdir -p "$all_folder"

    local new_name="$base_name ($total_boards hands).pbn"
    cp "$pbn_file" "$all_folder/$new_name"
    trace "Created: $all_folder/$new_name"

    # If no slices specified, we're done
    if [[ ${#slices[@]} -eq 0 ]]; then
        return
    fi

    # Extract header (everything before first [Board])
    local header=$(sed -n '1,/^\[Board/p' "$pbn_file" | head -n -1)

    # Process each slice size
    for slice_size in "${slices[@]}"; do
        if [[ $slice_size -le 0 ]]; then
            warn "Invalid slice size: $slice_size"
            continue
        fi

        if [[ $total_boards -le $slice_size ]]; then
            trace "Skipping slice $slice_size: not enough boards ($total_boards)"
            continue
        fi

        trace "Slicing into sets of $slice_size..."

        local slice_folder="$folder/$slice_size-Board Sets"
        mkdir -p "$slice_folder"

        local total_sets=$(( (total_boards + slice_size - 1) / slice_size ))

        # Use awk to split the file
        for ((set_num=1; set_num<=total_sets; set_num++)); do
            local start_board=$(( (set_num - 1) * slice_size + 1 ))
            local end_board=$(( set_num * slice_size ))
            if [[ $end_board -gt $total_boards ]]; then
                end_board=$total_boards
            fi
            local boards_in_set=$(( end_board - start_board + 1 ))

            local set_file="$slice_folder/$base_name Set $set_num ($boards_in_set hands).pbn"

            # Extract boards and renumber them
            awk -v start="$start_board" -v end="$end_board" -v header="$header" '
                BEGIN {
                    print header
                    board_num = 0
                    new_board = 0
                    in_board = 0
                }
                /^\[Board/ {
                    board_num++
                    if (board_num >= start && board_num <= end) {
                        in_board = 1
                        new_board++
                        sub(/\[Board "[0-9]+"/, "[Board \"" new_board "\"")
                        print
                        next
                    } else {
                        in_board = 0
                    }
                }
                in_board { print }
            ' "$pbn_file" > "$set_file"

            trace "Created: $set_file"
        done
    done
}

#---------------------------------------------------
# Action: rotate_hands
#---------------------------------------------------
action_rotate_hands() {
    local file="$1"
    shift
    local slices=("$@")

    trace "Executing rotate_hands for: $file with slices: ${slices[*]}"

    if [[ ! -x "$BRIDGE_WRANGLER_PATH" ]]; then
        error "bridge-wrangler not found at $BRIDGE_WRANGLER_PATH"
    fi

    local folder="Rotations/$file"

    if [[ ! -d "$folder" ]]; then
        warn "Folder not found: $folder"
        return
    fi

    # Build list of folders to process: All + each slice folder
    local -a folders_to_process=()

    if [[ -d "$folder/All" ]]; then
        folders_to_process+=("$folder/All")
    fi

    for slice in "${slices[@]}"; do
        local slice_folder="$folder/$slice-Board Sets"
        if [[ -d "$slice_folder" ]]; then
            folders_to_process+=("$slice_folder")
        fi
    done

    for target_folder in "${folders_to_process[@]}"; do
        trace "Processing folder: $target_folder"

        for pbn in "$target_folder"/*.pbn; do
            [[ -f "$pbn" ]] || continue

            # Skip already rotated files
            if [[ "$pbn" == *" - S.pbn" ]] || [[ "$pbn" == *" - NS.pbn" ]] || [[ "$pbn" == *" - NESW.pbn" ]]; then
                continue
            fi

            trace "Rotating: $pbn"

            # Run rotation with multiple patterns: S, NS, NESW
            # bridge-wrangler will create separate output files for each pattern
            "$BRIDGE_WRANGLER_PATH" rotate-deals -i "$pbn" -p "S,NS,NESW" -b declarer --standard-vul || warn "Failed to rotate: $pbn"

            # Convert rotated PBNs to PDFs
            for rotated in "${pbn%.pbn}"\ -\ *.pbn; do
                [[ -f "$rotated" ]] || continue
                local pdf="${rotated%.pbn}.pdf"
                trace "Converting to PDF: $rotated"
                "$BRIDGE_WRANGLER_PATH" to-pdf -i "$rotated" -o "$pdf" || warn "Failed to convert: $rotated"
            done
        done
    done
}

#---------------------------------------------------
# Action: block_replicate
#---------------------------------------------------
action_block_replicate() {
    local file="$1"
    shift
    local slices=("$@")

    trace "Executing block_replicate for: $file with slices: ${slices[*]}"

    if [[ ! -x "$BRIDGE_WRANGLER_PATH" ]]; then
        error "bridge-wrangler not found at $BRIDGE_WRANGLER_PATH"
    fi

    local folder="Rotations/$file"

    if [[ ! -d "$folder" ]]; then
        warn "Folder not found: $folder"
        return
    fi

    for slice in "${slices[@]}"; do
        local slice_folder="$folder/$slice-Board Sets"

        if [[ ! -d "$slice_folder" ]]; then
            trace "Skipping missing slice folder: $slice_folder"
            continue
        fi

        trace "Processing block_replicate in: $slice_folder"

        # Find NESW rotated files
        for nesw_file in "$slice_folder"/*\ -\ NESW.pbn; do
            [[ -f "$nesw_file" ]] || continue

            trace "Block replicating: $nesw_file"

            # Run block-replicate with PDF generation
            "$BRIDGE_WRANGLER_PATH" block-replicate -i "$nesw_file" --pdf || warn "Failed to block-replicate: $nesw_file"

            # Generate dealer summary PDF using pbn-to-pdf
            if [[ -x "$PBN_TO_PDF_PATH" ]]; then
                local base_name="${nesw_file%.pbn}"
                local summary_pdf="${base_name} Dealer Summary.pdf"
                trace "Generating dealer summary: $summary_pdf"
                "$PBN_TO_PDF_PATH" "$nesw_file" -o "$summary_pdf" --layout dealer-summary || warn "Failed to generate dealer summary: $nesw_file"
            fi
        done
    done
}

#---------------------------------------------------
# Action: bidding_sheets
#---------------------------------------------------
action_bidding_sheets() {
    local file="$1"
    shift
    local slices=("$@")

    trace "Executing bidding_sheets for: $file with slices: ${slices[*]}"

    if [[ ! -x "$PBN_TO_PDF_PATH" ]]; then
        error "pbn-to-pdf not found at $PBN_TO_PDF_PATH"
    fi

    local folder="Rotations/$file"

    if [[ ! -d "$folder" ]]; then
        warn "Folder not found: $folder"
        return
    fi

    for slice in "${slices[@]}"; do
        local slice_folder="$folder/$slice-Board Sets"

        if [[ ! -d "$slice_folder" ]]; then
            trace "Skipping missing slice folder: $slice_folder"
            continue
        fi

        trace "Processing bidding_sheets in: $slice_folder"

        # Find NS rotated files (bidding sheets are for North-South practice)
        for ns_file in "$slice_folder"/*\ -\ NS.pbn; do
            [[ -f "$ns_file" ]] || continue

            local base_name="${ns_file%.pbn}"
            local sheets_pdf="${base_name} Bidding Sheets.pdf"

            trace "Generating bidding sheets: $sheets_pdf"
            "$PBN_TO_PDF_PATH" "$ns_file" -o "$sheets_pdf" --layout bidding-sheets || warn "Failed to generate bidding sheets: $ns_file"
        done
    done
}

#---------------------------------------------------
# Action: aggregate
#---------------------------------------------------
action_aggregate() {
    local file="$1"
    shift
    local slices=("$@")

    trace "Executing aggregate for: $file with slices: ${slices[*]}"

    local folder="Rotations/$file"

    if [[ ! -d "$folder" ]]; then
        warn "Folder not found: $folder"
        return
    fi

    for slice in "${slices[@]}"; do
        local bs_folder="$folder/$slice-Board Sets"

        if [[ ! -d "$bs_folder" ]]; then
            trace "Skipping missing board set folder: $bs_folder"
            continue
        fi

        trace "Aggregating in: $bs_folder"

        # Create subfolders
        local full_table="$bs_folder/Full Table"
        local north_south="$bs_folder/North-South"
        local south="$bs_folder/South"

        mkdir -p "$full_table" "$north_south" "$south"

        # Move files based on patterns
        for f in "$bs_folder"/*; do
            [[ -f "$f" ]] || continue
            local fname=$(basename "$f")

            if [[ "$fname" == *NESW* ]] || [[ "$fname" == *"Bidding Sheets"* ]] || [[ "$fname" == *"Dealer Summary"* ]]; then
                mv "$f" "$full_table/" 2>/dev/null || true
            elif [[ "$fname" == *" - NS"* ]]; then
                mv "$f" "$north_south/" 2>/dev/null || true
            elif [[ "$fname" == *" - S"* ]] && [[ "$fname" != *" - NS"* ]]; then
                mv "$f" "$south/" 2>/dev/null || true
            fi
        done

        # Rename files in Full Table
        for f in "$full_table"/*; do
            [[ -f "$f" ]] || continue
            local old_name=$(basename "$f")
            local new_name="$old_name"

            # Remove "(n hands) - NS Bidding Sheets" -> "Bidding Sheets"
            new_name=$(echo "$new_name" | sed -E 's/ *\([0-9]+ hands\) - NS Bidding Sheets/ Bidding Sheets/g')
            # Remove "(n hands) - NESW Standard " -> " "
            new_name=$(echo "$new_name" | sed -E 's/ *\([0-9]+ hands\) - NESW Standard / /g')
            # Remove "(n hands) - NESW Nonstandard" -> " Nonstandard"
            new_name=$(echo "$new_name" | sed -E 's/ *\([0-9]+ hands\) - NESW Nonstandard/ Nonstandard/g')
            # Remove "(n hands) - NESW - " -> " - "
            new_name=$(echo "$new_name" | sed -E 's/ *\([0-9]+ hands\) - NESW - / - /g')
            # Replace ") -" with ") "
            new_name=$(echo "$new_name" | sed 's/) -/) /g')

            if [[ "$new_name" != "$old_name" ]]; then
                trace "Renaming: $old_name -> $new_name"
                mv "$f" "$full_table/$new_name" 2>/dev/null || true
            fi
        done

        # Rename files in North-South
        for f in "$north_south"/*; do
            [[ -f "$f" ]] || continue
            local old_name=$(basename "$f")
            local new_name=$(echo "$old_name" | sed 's/hands) - NS/hands) NS/g')

            if [[ "$new_name" != "$old_name" ]]; then
                trace "Renaming: $old_name -> $new_name"
                mv "$f" "$north_south/$new_name" 2>/dev/null || true
            fi
        done

        # Rename files in South
        for f in "$south"/*; do
            [[ -f "$f" ]] || continue
            local old_name=$(basename "$f")
            local new_name=$(echo "$old_name" | sed 's/hands) - S/hands) South/g')

            if [[ "$new_name" != "$old_name" ]]; then
                trace "Renaming: $old_name -> $new_name"
                mv "$f" "$south/$new_name" 2>/dev/null || true
            fi
        done

        # Delete original slice-level .pbn files (those with "hands).pbn")
        for f in "$bs_folder"/*hands\).pbn; do
            [[ -f "$f" ]] || continue
            trace "Deleting: $f"
            rm "$f"
        done
    done
}

#---------------------------------------------------
# Main
#---------------------------------------------------
echo -e "${GREEN}Rotation Lesson Collection Script (Mac)${NC}"
echo "Current directory: $(pwd)"
echo "Filter: $FILTER"
echo "Slices: ${SLICES[*]:-none}"
echo ""

# Check bridge-wrangler
if [[ ! -x "$BRIDGE_WRANGLER_PATH" ]]; then
    warn "bridge-wrangler not found at $BRIDGE_WRANGLER_PATH"
    warn "Some actions may not work. Set BRIDGE_WRANGLER_PATH environment variable."
fi

# Check pbn-to-pdf
if [[ ! -x "$PBN_TO_PDF_PATH" ]]; then
    warn "pbn-to-pdf not found at $PBN_TO_PDF_PATH"
    warn "bidding_sheets and dealer_summary will be skipped. Set PBN_TO_PDF_PATH environment variable."
fi

# Expand actions
ACTIONS=$(expand_actions "$ACTIONS_ARG")
echo "Actions: $ACTIONS"
echo ""

# Get filtered folders
FILTERED_FOLDERS=$(filter_folders "$FILTER")

if [[ -z "$FILTERED_FOLDERS" ]]; then
    error "No matching folders found for filter: $FILTER"
fi

echo "Matched folders:"
echo "$FILTERED_FOLDERS" | while read -r f; do echo "  - $f"; done
echo ""

START_TIME=$(date +%s)

# Process each action
for action in $ACTIONS; do
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}Action: $action${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    while IFS= read -r folder; do
        [[ -z "$folder" ]] && continue
        echo "Processing: $folder"

        case "$action" in
            create_folders)
                action_create_folders "$folder"
                ;;
            copy_presentation)
                action_copy_presentation "$folder"
                ;;
            pdf_presentation)
                action_pdf_presentation "$folder"
                ;;
            slice_deals)
                action_slice_deals "$folder" "${SLICES[@]}"
                ;;
            rotate_hands)
                action_rotate_hands "$folder" "${SLICES[@]}"
                ;;
            block_replicate)
                action_block_replicate "$folder" "${SLICES[@]}"
                ;;
            bidding_sheets)
                action_bidding_sheets "$folder" "${SLICES[@]}"
                ;;
            aggregate)
                action_aggregate "$folder" "${SLICES[@]}"
                ;;
            *)
                warn "Unknown action: $action"
                ;;
        esac
    done <<< "$FILTERED_FOLDERS"
done

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))
MINS=$((ELAPSED / 60))
SECS=$((ELAPSED % 60))

echo ""
echo -e "${GREEN}Rotation Lesson Collection Script completed in ${MINS}m ${SECS}s.${NC}"

#!/bin/bash
#
# convert_html_to_pdf.sh - Convert deal00.html intro pages to PDF using html2pdf
#
# This replaces Convert_deal00_to_PDF.py and uses the Rust-based html2pdf tool
# which leverages headless Chrome for rendering.
#
# Usage:
#   ./convert_html_to_pdf.sh [--source DIR] [--dest DIR]
#

set -e

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Default paths
SOURCE_ROOT="$SCRIPT_DIR/../Website/Baker Bridge/bakerbridge.coffeecup.com"
DEST_FOLDER="$SCRIPT_DIR/pdfs"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --source)
            SOURCE_ROOT="$2"
            shift 2
            ;;
        --dest)
            DEST_FOLDER="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: $0 [--source DIR] [--dest DIR]"
            echo ""
            echo "Options:"
            echo "  --source DIR  Source directory containing deal00.html files"
            echo "  --dest DIR    Destination directory for PDF output"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Check html2pdf is installed
if ! command -v html2pdf &> /dev/null; then
    echo "Error: html2pdf not found. Install with: brew install ilaborie/tap/html2pdf"
    exit 1
fi

# Check source directory exists
if [[ ! -d "$SOURCE_ROOT" ]]; then
    echo "Error: Source directory not found: $SOURCE_ROOT"
    exit 1
fi

# Create destination folder
mkdir -p "$DEST_FOLDER"

echo "Converting HTML intro pages to PDF..."
echo "  Source: $SOURCE_ROOT"
echo "  Dest:   $DEST_FOLDER"
echo ""

# Track statistics
total=0
converted=0
failed=0

# Find all deal00.html files
while IFS= read -r -d '' html_file; do
    total=$((total + 1))

    # Get relative path from source root
    rel_path="${html_file#$SOURCE_ROOT/}"
    rel_dir="$(dirname "$rel_path")"

    # Generate PDF name from relative directory path
    if [[ "$rel_dir" == "." ]]; then
        pdf_name="root.pdf"
    else
        # Replace path separators with underscores
        pdf_name="${rel_dir//\//_}.pdf"
    fi

    pdf_path="$DEST_FOLDER/$pdf_name"

    echo "Converting: $rel_dir/deal00.html -> $pdf_name"

    # Convert using html2pdf with background printing enabled
    if html2pdf "$html_file" -o "$pdf_path" --background --paper Letter 2>/dev/null; then
        converted=$((converted + 1))
    else
        echo "  Warning: Failed to convert $html_file"
        failed=$((failed + 1))
    fi

done < <(find "$SOURCE_ROOT" -name "deal00.html" -type f -print0)

echo ""
echo "Conversion complete:"
echo "  Total files: $total"
echo "  Converted:   $converted"
echo "  Failed:      $failed"

#!/usr/bin/env python3
"""
convert_pbns_to_pdfs.py - Mac replacement for convert_pbns_to_pdfs.ps1

Converts all PBN files in the pbns folder to PDFs using bridge-wrangler.

Usage:
    python3 convert_pbns_to_pdfs.py [--bridge-wrangler PATH] [--source DIR] [--dest DIR]

Output:
    PDF files in the pdfs/ folder (or specified destination)
"""

import os
import subprocess
import sys
from pathlib import Path

# Default paths - adjust if needed
BRIDGE_WRANGLER_PATH = Path.home() / "Development/GitHub/bridge-wrangler/target/release/bridge-wrangler"
SOURCE_FOLDER = "pbns"
DEST_FOLDER = "pbns"  # Output PDFs alongside PBNs (matching BridgeComposer behavior)


def convert_pbn_to_pdf(pbn_path: Path, pdf_path: Path, bridge_wrangler: Path) -> bool:
    """Convert a single PBN file to PDF using bridge-wrangler."""
    try:
        result = subprocess.run(
            [
                str(bridge_wrangler),
                "to-pdf",
                "-i", str(pbn_path),
                "-o", str(pdf_path),
            ],
            capture_output=True,
            text=True,
            timeout=120
        )

        if result.returncode != 0:
            print(f"  Error: {result.stderr.strip()}", file=sys.stderr)
            return False
        return True

    except subprocess.TimeoutExpired:
        print(f"  Timeout converting {pbn_path}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"  Exception: {e}", file=sys.stderr)
        return False


def main():
    # Parse command line args
    bridge_wrangler = BRIDGE_WRANGLER_PATH
    source_folder = Path(SOURCE_FOLDER)
    dest_folder = Path(DEST_FOLDER)

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == '--bridge-wrangler' and i + 1 < len(args):
            bridge_wrangler = Path(args[i + 1])
            i += 2
        elif args[i] == '--source' and i + 1 < len(args):
            source_folder = Path(args[i + 1])
            i += 2
        elif args[i] == '--dest' and i + 1 < len(args):
            dest_folder = Path(args[i + 1])
            i += 2
        elif args[i] in ['-h', '--help']:
            print(__doc__)
            sys.exit(0)
        else:
            i += 1

    # Check bridge-wrangler exists
    if not bridge_wrangler.exists():
        print(f"Error: bridge-wrangler binary not found at {bridge_wrangler}", file=sys.stderr)
        print("Use --bridge-wrangler PATH to specify the location", file=sys.stderr)
        sys.exit(1)

    # Check source folder exists
    if not source_folder.exists():
        print(f"Error: Source folder '{source_folder}' not found", file=sys.stderr)
        sys.exit(1)

    # Create destination folder if needed
    dest_folder.mkdir(parents=True, exist_ok=True)

    # Track statistics
    total_files = 0
    converted = 0
    failed = 0

    # Get all folders (root + subfolders), sorted alphabetically
    folders = sorted([source_folder] + list(source_folder.rglob('*/')))
    folders = [f for f in [source_folder] + list(source_folder.iterdir()) if f.is_dir()]
    folders = sorted(set([source_folder] + [p for p in source_folder.rglob('*') if p.is_dir()]))

    for folder in folders:
        # Get relative path from source for subfolder structure
        rel_path = folder.relative_to(source_folder) if folder != source_folder else Path('.')

        # Get all .pbn files in this folder (not recursive within each iteration)
        pbn_files = sorted(folder.glob('*.pbn'))

        if not pbn_files:
            continue

        print(f"Processing folder: {folder}")

        # Create corresponding destination subfolder
        if rel_path != Path('.'):
            (dest_folder / rel_path).mkdir(parents=True, exist_ok=True)

        for pbn_file in pbn_files:
            total_files += 1

            # Determine output PDF path
            if rel_path == Path('.'):
                pdf_path = dest_folder / pbn_file.with_suffix('.pdf').name
            else:
                pdf_path = dest_folder / rel_path / pbn_file.with_suffix('.pdf').name

            print(f"  Converting {pbn_file.name} -> {pdf_path.name}")

            if convert_pbn_to_pdf(pbn_file, pdf_path, bridge_wrangler):
                converted += 1
            else:
                failed += 1

    # Report statistics
    print(f"\nConversion complete:")
    print(f"  Total files: {total_files}")
    print(f"  Converted: {converted}")
    print(f"  Failed: {failed}")


if __name__ == '__main__':
    main()

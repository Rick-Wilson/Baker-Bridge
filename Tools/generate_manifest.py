#!/usr/bin/env python3
"""Emit Package/manifest.json -- the build-generated collection manifest.

Producer-contract obligation R5 (ADR-0002): every build publishes a JSON
manifest that is the authoritative description of the collection's shape. Bridge
Classroom fetches it directly to learn how many boards a lesson has and which are
stable -- it does not re-parse the PBNs for sizing.

This runs as the FINAL build step, AFTER stamp_board_tokens.py, because it reads
the per-board [VersionToken] (R3) that only exists once the tokens are
stamped onto the released Package/*.pbn (post curated-merge). Same reason the
token stamp itself can't live in CSV_to_PBN.py.

Schema (shared v2 format; see Bridge-Classroom design/collection-manifest doc):

    {
      "schemaVersion": 2,
      "generatedAtCommit": "<commit of the deal set>",
      "generatedAt": "<ISO 8601, pinned to the deal set>",
      "lessons": {
        "<PbnBasename>": {                 # key = PBN basename = deal_subfolder
          "skillPath": "...",              # lesson-level default
          "boardCount": 25,               # = len(boards)
          "stableBoardCount": 25,
          "boards": [
            {"number": 1, "stable": true,
             "boardVersionToken": "...", "skillPath": "..."}
          ]
        }
      }
    }

Per contract R5/§7 the manifest carries only producer-owned facts (stable,
tokens, skill paths, board numbers). It deliberately does NOT carry BC's
`collection` id, the `report` flag, or a `prerelease` column (BC derives
prerelease = !stable). There is no `tier` field -- tiers are a PBS client-side
concern, not a producer obligation.
"""

import datetime
import glob
import json
import os
import re
import subprocess
import sys

SCHEMA_VERSION = 3  # v3: optional per-lesson "intro" (companion _Intro.pdf), additive


# Provenance is taken from the *deal set* that produced this manifest, not from the clock or
# from HEAD. The packaging build is idempotent -- the same deal set yields byte-identical
# output -- and wall-clock provenance would break that, rewriting manifest.json on every run
# and burying real changes. Describing the input is also the more useful fact: it says which
# deals these boards came from, not which minute the build happened to run.
DEALS_CSV = "BakerBridgeFull.csv"


def _git(repo_dir, *args):
    try:
        out = subprocess.run(["git", "-C", repo_dir, *args],
                             capture_output=True, text=True, check=True)
        return out.stdout.strip() or None
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return None


def deals_commit(repo_dir):
    """The commit that last touched the deal set, or HEAD if it has never been committed."""
    return (_git(repo_dir, "log", "-1", "--format=%H", "--", f"Tools/{DEALS_CSV}")
            or _git(repo_dir, "rev-parse", "HEAD"))


def build_timestamp(repo_dir):
    """BB_BUILD_DATE, else the deal set's last commit date, else now.

    Mirrors resolve_build_time() in CSV_to_PBN.py and resolve_build_date() in
    build-common.sh -- one rule, so every generated artifact agrees.
    """
    override = os.environ.get("BB_BUILD_DATE")
    if override:
        return override
    stamp = _git(repo_dir, "log", "-1", "--format=%cd",
                 "--date=format:%Y-%m-%dT%H:%M:%S", "--", f"Tools/{DEALS_CSV}")
    return stamp or datetime.datetime.now().isoformat()


def file_stable_default(preamble):
    """File-level release status from the %bridge-classroom-stable header.

    Present-and-true => True; explicit false or absent => False (prerelease).
    """
    m = re.search(r'^%bridge-classroom-stable:\s*(\S+)', preamble, re.MULTILINE)
    return bool(m) and m.group(1).strip().lower() == "true"


def board_stable(board_text, file_default):
    """Resolve a board's stable status: board-level [Stable] overrides the file."""
    m = re.search(r'\[Stable "([^"]*)"\]', board_text)
    if m:
        return m.group(1).strip().lower() == "true"
    return file_default


def parse_file(path):
    """Return (basename, [board dicts]) for one released PBN."""
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    first_event = content.find('[Event "')
    preamble = content[:first_event] if first_event >= 0 else content
    default_stable = file_stable_default(preamble)

    basename = os.path.splitext(os.path.basename(path))[0]
    boards = []
    for part in re.split(r'(?=\[Event ")', content):
        if "[Board " not in part:
            continue
        num_m = re.search(r'\[Board "([^"]*)"\]', part)
        tok_m = re.search(r'\[VersionToken "([^"]*)"\]', part)
        skill_m = re.search(r'\[SkillPath "([^"]*)"\]', part)
        number = num_m.group(1).strip() if num_m else None
        try:
            number = int(number)
        except (TypeError, ValueError):
            pass  # keep raw string if not an integer
        boards.append({
            "number": number,
            "stable": board_stable(part, default_stable),
            "boardVersionToken": tok_m.group(1) if tok_m else None,
            "skillPath": skill_m.group(1) if skill_m else None,
        })
    # Sort by number; integer boards first (in order), then any non-integer or
    # missing numbers last (kept, but flagged by the integrity check downstream).
    boards.sort(key=lambda b: (not isinstance(b["number"], int),
                               b["number"] if isinstance(b["number"], int) else 0,
                               str(b["number"])))
    return basename, boards


def lesson_skill_path(boards):
    """Lesson-level default skillPath = the most common non-empty board path."""
    counts = {}
    for b in boards:
        sp = b["skillPath"]
        if sp:
            counts[sp] = counts.get(sp, 0) + 1
    if not counts:
        return None
    return max(counts, key=counts.get)


def build_manifest(package_dir):
    pbn_files = sorted(glob.glob(os.path.join(package_dir, "*.pbn")))
    lessons = {}
    for path in pbn_files:
        basename, boards = parse_file(path)
        if not boards:
            continue
        lesson = {
            "skillPath": lesson_skill_path(boards),
            "boardCount": len(boards),
            "stableBoardCount": sum(1 for b in boards if b["stable"]),
            "boards": boards,
        }
        # Companion lesson introduction (shown in the app when present). Schema v3.
        intro = f"{basename}_Intro.pdf"
        if os.path.exists(os.path.join(package_dir, intro)):
            lesson["intro"] = intro
        lessons[basename] = lesson
    # Deterministic ordering of lessons by basename.
    lessons = {k: lessons[k] for k in sorted(lessons)}

    repo_dir = os.path.dirname(os.path.abspath(package_dir.rstrip("/")))
    return {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAtCommit": deals_commit(repo_dir),
        "generatedAt": build_timestamp(repo_dir),
        "lessons": lessons,
    }


def main():
    target = (sys.argv[1] if len(sys.argv) > 1 else None) \
        or os.environ.get("BB_PACKAGE_DIR") \
        or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Package")
    if not os.path.isdir(target):
        print(f"Package directory not found: {target}")
        return 1

    manifest = build_manifest(target)
    if not manifest["lessons"]:
        print(f"No PBN lessons found in {target}")
        return 1

    # Fail loudly if any released board is missing a token or skill path -- both
    # are R3/R4 prerequisites the manifest must faithfully report.
    problems = []
    for name, lesson in manifest["lessons"].items():
        for b in lesson["boards"]:
            if not isinstance(b["number"], int):
                problems.append(f"{name}: board with missing/non-integer number "
                                f"({b['number']!r})")
            if not b["boardVersionToken"]:
                problems.append(f"{name} board {b['number']}: missing VersionToken")
            if not b["skillPath"]:
                problems.append(f"{name} board {b['number']}: missing SkillPath")

    out_path = os.path.join(target, "manifest.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
        f.write("\n")

    total_boards = sum(l["boardCount"] for l in manifest["lessons"].values())
    total_stable = sum(l["stableBoardCount"] for l in manifest["lessons"].values())
    print(f"Wrote {out_path}: {len(manifest['lessons'])} lessons, "
          f"{total_boards} boards ({total_stable} stable)")

    if problems:
        print(f"\nManifest integrity FAILED ({len(problems)} issue(s)):")
        for p in problems:
            print(f"  {p}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

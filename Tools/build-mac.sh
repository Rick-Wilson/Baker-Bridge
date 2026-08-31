#!/bin/bash
#
# build-mac.sh - compatibility shim.
#
# The build is now two scripts, split at BakerBridgeFull.csv (the deal set of record):
#
#   ./build-deals.sh      HTML -> BakerBridgeFull.csv.  NOT reproducible (dealer3 deals
#                         fresh hands; bb_fill's E/W assignment is an unseeded shuffle), so
#                         re-running it can move board identity and cost Bridge Classroom
#                         its mastery history. Run it when the deals must change.
#
#   ./build-materials.sh  BakerBridgeFull.csv -> Collection/, bridge-classroom/,
#                         Presentation/, Rotations/.  Idempotent: same CSV in, byte-identical
#                         output. Run it freely for any packaging change.
#
# They used to be one script whose classroom/rotations shortcuts ran both halves -- so a
# packaging change silently re-dealt hands. This forwards the old commands to the packaging
# half, which is what those shortcuts were almost always wanted for.
#
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cat >&2 <<'NOTE'
Note: build-mac.sh has been split.
  ./build-deals.sh      regenerate the deal set (rare; changes board identity)
  ./build-materials.sh  package the existing deal set (idempotent; use this for packaging)
Forwarding to build-materials.sh ...

NOTE

exec "$SCRIPT_DIR/build-materials.sh" "$@"

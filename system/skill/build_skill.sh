#!/usr/bin/env bash
# Rebuilds sunday-scaries.skill from source after edits.
#
# Layout the .skill file needs (a zip archive with this structure):
#   sunday-scaries/
#     SKILL.md              <- copy of system/skill/SKILL.md
#     reference/*.md        <- copy of system/skill/reference/*.md
#     bundle/system/...     <- a full copy of the runtime (weekly.js, state_builder.py,
#                              players_cache.py, analysis/, league_config.json,
#                              players_cache.json, raw/, state/, fetch_manifest.md,
#                              weekly_README.md) so a cold-start chat can rebuild
#                              everything from this one file.
#
# Run this from anywhere; paths below are absolute.
#
# Usage: bash system/skill/build_skill.sh

set -euo pipefail

ROOT="/home/claude/sunday_scaries"
SKILL_SRC="$ROOT/system/skill"
STAGE="$(mktemp -d)"
OUT="$ROOT/sunday-scaries.skill"

echo "Staging in $STAGE"

mkdir -p "$STAGE/sunday-scaries/reference"
mkdir -p "$STAGE/sunday-scaries/bundle/system"

# 1. Skill instructions + reference set
cp "$SKILL_SRC/SKILL.md" "$STAGE/sunday-scaries/SKILL.md"
cp "$SKILL_SRC"/reference/*.md "$STAGE/sunday-scaries/reference/"

# 2. Bundle the entire runtime so a cold start can rebuild from this file alone.
#    Exclude the skill/ dir itself (it's not part of the runtime) and any
#    __pycache__/.pyc cruft. (Plain cp+find; no rsync in this environment.)
cp -r "$ROOT/system/." "$STAGE/sunday-scaries/bundle/system/"
rm -rf "$STAGE/sunday-scaries/bundle/system/skill"
find "$STAGE/sunday-scaries/bundle/system" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
find "$STAGE/sunday-scaries/bundle/system" -name '*.pyc' -delete 2>/dev/null || true
# Drop Playwright test screenshots — verification artifacts, not runtime.
rm -f "$STAGE/sunday-scaries/bundle/system/ui"/screenshot_*.png

# 3. Zip it up (skill files are just zip archives with this internal layout)
rm -f "$OUT"
( cd "$STAGE" && zip -rq "$OUT" sunday-scaries )

rm -rf "$STAGE"

echo "Rebuilt: $OUT"
unzip -l "$OUT" | tail -5

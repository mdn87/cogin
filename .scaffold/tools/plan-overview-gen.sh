#!/usr/bin/env bash
# plan-overview-gen.sh — Regenerate PLAN-OVERVIEW.md from milestone files
# Usage: bash .scaffold/tools/plan-overview-gen.sh [docs/plans]
# Scans PLAN-M*.md files and rebuilds the overview table.

set -euo pipefail

PLANS_DIR="${1:-docs/plans}"

if [ ! -d "$PLANS_DIR" ]; then
  echo "Plans directory not found: $PLANS_DIR"
  exit 1
fi

if [ ! -f "$PLANS_DIR/PLAN.md" ]; then
  echo "No PLAN.md found in $PLANS_DIR"
  exit 1
fi

# Extract project name from PLAN.md first line
PROJECT_NAME="$(head -1 "$PLANS_DIR/PLAN.md" | sed 's/^# //' | sed 's/ — Master Plan//')"

echo "# Plan Overview — $PROJECT_NAME"
echo ""
echo "## Metadata"
echo "- **Last Updated:** $(date +%Y-%m-%d)"
echo ""
echo "## Milestones"
echo ""
echo "| # | Title | Status | Dependencies |"
echo "|---|-------|--------|-------------|"

# Parse each milestone file
for mfile in "$PLANS_DIR"/PLAN-M*.md; do
  [ -f "$mfile" ] || continue

  BASENAME="$(basename "$mfile" .md)"
  NUM="$(echo "$BASENAME" | grep -oP 'M\d+(-BE\d+)?')"

  TITLE="$(head -1 "$mfile" | sed "s/^# PLAN-M[0-9]*\(-BE[0-9]*\)\?: //")"
  STATUS="$(grep -oP '(?<=\*\*Status:\*\* ).*' "$mfile" | head -1)" || STATUS="Unknown"
  DEPS="$(grep -oP '(?<=\*\*Dependencies:\*\* ).*' "$mfile" | head -1)" || DEPS="None"

  echo "| $NUM | $TITLE | $STATUS | $DEPS |"
done

echo ""
echo "## Tool-Milestone Matrix"
echo ""
echo "_(Regenerate with tool-config.json data when available)_"

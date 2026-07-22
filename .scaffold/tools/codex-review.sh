#!/usr/bin/env bash
# codex-review.sh — Invoke Codex CLI for cross-agent milestone review
# Usage: bash .scaffold/tools/codex-review.sh --dimension KISS --milestone PLAN-M1.md --files "src/foo.py src/bar.py"

set -euo pipefail

DIMENSION=""
MILESTONE=""
FILES=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dimension) DIMENSION="$2"; shift 2 ;;
    --milestone) MILESTONE="$2"; shift 2 ;;
    --files) FILES="$2"; shift 2 ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

if [ -z "$DIMENSION" ] || [ -z "$MILESTONE" ]; then
  echo "Usage: codex-review.sh --dimension <KISS|style|correctness|goals> --milestone <path> [--files <paths>]"
  exit 1
fi

# Build the review prompt based on dimension
case "$DIMENSION" in
  KISS|kiss)
    PROMPT="Review the implementation for this milestone. Focus ONLY on simplicity: Is anything over-engineered? Are there simpler approaches that achieve the same result? Are there unnecessary abstractions, indirections, or future-proofing? Answer: PASS (no issues) or OBJECTION (with specific concerns and simpler alternatives)."
    ;;
  style)
    PROMPT="Review the implementation for this milestone. Focus ONLY on codebase consistency: Does the new code follow existing patterns and conventions? Are naming conventions, file organization, and code structure consistent? Does it feel like it belongs in this codebase? Answer: PASS (no issues) or OBJECTION (with specific inconsistencies)."
    ;;
  correctness)
    PROMPT="Review the implementation for this milestone. Focus ONLY on correctness: Are there bugs, logic errors, or unhandled edge cases? Are there race conditions, resource leaks, or security issues? Do the tests actually test the right things? Answer: PASS (no issues) or OBJECTION (with specific bugs or concerns)."
    ;;
  goals)
    PROMPT="Review the implementation for this milestone. Focus ONLY on goal fulfillment: Does the implementation achieve what the milestone's acceptance criteria defined? Is anything missing from the acceptance criteria? Is anything implemented that wasn't in scope? Answer: PASS (no issues) or OBJECTION (with specific gaps or scope creep)."
    ;;
  *)
    echo "Unknown dimension: $DIMENSION (expected: KISS, style, correctness, goals)"
    exit 1
    ;;
esac

# Read milestone file for context
if [ ! -f "$MILESTONE" ]; then
  echo "Milestone file not found: $MILESTONE"
  exit 1
fi

MILESTONE_CONTENT="$(cat "$MILESTONE")"

# Build file context
FILE_CONTEXT=""
if [ -n "$FILES" ]; then
  for f in $FILES; do
    if [ -f "$f" ]; then
      FILE_CONTEXT="$FILE_CONTEXT

--- $f ---
$(cat "$f")
"
    fi
  done
fi

# Check if codex CLI is available
if ! command -v codex &>/dev/null; then
  echo "=== CODEX CLI NOT AVAILABLE — MANUAL REVIEW PROMPT ==="
  echo ""
  echo "=== REVIEW REQUEST: $DIMENSION ==="
  echo "Milestone: $MILESTONE"
  echo "Files changed: $FILES"
  echo ""
  echo "$PROMPT"
  echo ""
  echo "Context:"
  echo "$MILESTONE_CONTENT"
  if [ -n "$FILE_CONTEXT" ]; then
    echo ""
    echo "=== FILES ==="
    echo "$FILE_CONTEXT"
  fi
  echo "==="
  exit 0
fi

# Invoke Codex CLI
FULL_PROMPT="$PROMPT

Milestone context:
$MILESTONE_CONTENT"

if [ -n "$FILE_CONTEXT" ]; then
  FULL_PROMPT="$FULL_PROMPT

Changed files:
$FILE_CONTEXT"
fi

codex --approval-mode full-auto -q "$FULL_PROMPT"

#!/usr/bin/env bash
# lane-stignore-block.sh — single source of truth for the .stignore block
# that the lanes workflow requires at the Syncthing folder root.
#
# Expose two functions:
#   stignore_block       — prints the full block with comments, suitable for append
#   stignore_rules_list  — prints just the rule lines (no comments), one per line,
#                          used by `lane adopt harden` to detect missing rules and
#                          by `lane doctor` to verify presence.

stignore_block() {
  cat <<'EOF'
// Git internals and operational state — never sync
(?d)**/.git
(?d)**/.worktrees

// Per-host environments
(?d)**/.venv
(?d)**/venv
(?d)**/.venv-*
(?d)**/node_modules

// IDE / editor state
(?d)**/.vscode
(?d)**/.idea
(?d)**/.history

// Scratch/debug dirs
(?d)**/.tmp-debug*
EOF
}

stignore_rules_list() {
  stignore_block | grep -v '^//' | grep -v '^$'
}

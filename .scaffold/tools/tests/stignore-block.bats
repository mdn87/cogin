#!/usr/bin/env bats

load 'helpers.bash'

setup() {
  TMPDIR="$(mktemp -d)"
  export TMPDIR
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../../../" && pwd)"
  source "$REPO_ROOT/runtime/tools/lane-stignore-block.sh"
}

teardown() {
  rm -rf "$TMPDIR"
}

@test "stignore_block outputs the required .git rule" {
  run stignore_block
  [ "$status" -eq 0 ]
  echo "$output" | grep -qF "(?d)**/.git"
}

@test "stignore_block outputs the required .worktrees rule" {
  run stignore_block
  echo "$output" | grep -qF "(?d)**/.worktrees"
}

@test "stignore_block outputs per-host env rules" {
  run stignore_block
  echo "$output" | grep -qF "(?d)**/.venv"
  echo "$output" | grep -qF "(?d)**/venv"
  echo "$output" | grep -qF "(?d)**/node_modules"
}

@test "stignore_rules_list returns every rule token on its own line" {
  run stignore_rules_list
  [ "$status" -eq 0 ]
  # Each line is a literal (?d)**/... token.
  echo "$output" | grep -qF "(?d)**/.git"
  echo "$output" | grep -qF "(?d)**/.tmp-debug*"
  # No comments should be in the list form.
  echo "$output" | grep -vqF "//"
}

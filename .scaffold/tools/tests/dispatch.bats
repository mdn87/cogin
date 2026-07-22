#!/usr/bin/env bats

load 'helpers.bash'

setup() {
  TMPDIR="$(mktemp -d)"
  export TMPDIR
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../../../" && pwd)"
  export LANE_SH_PATH="$REPO_ROOT/runtime/tools/lane.sh"
}

teardown() {
  rm -rf "$TMPDIR"
}

@test "lane.sh with no args prints usage and exits non-zero" {
  run lane_sh
  [ "$status" -ne 0 ]
  [[ "$output" =~ Usage: ]]
  [[ "$output" =~ "lane new" ]]
  [[ "$output" =~ "lane adopt" ]]
}

@test "lane.sh --help prints usage and exits zero" {
  run lane_sh --help
  [ "$status" -eq 0 ]
  [[ "$output" =~ Usage: ]]
}

@test "lane.sh with unknown subcommand exits non-zero" {
  run lane_sh fizzbuzz
  [ "$status" -ne 0 ]
  [[ "$output" =~ [Uu]nknown ]]
}

@test "lane.sh adopt with no sub prints three-step flow and exits zero" {
  run lane_sh adopt
  [ "$status" -eq 0 ]
  [[ "$output" =~ harden ]]
  [[ "$output" =~ cleanup ]]
  [[ "$output" =~ rename ]]
}

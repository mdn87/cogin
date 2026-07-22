#!/usr/bin/env bats

load 'helpers.bash'

setup() {
  TMPDIR="$(mktemp -d)"
  export TMPDIR
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../../../" && pwd)"
  export LANE_SH_PATH="$REPO_ROOT/runtime/tools/lane.sh"
  make_fake_repo "$TMPDIR/repo"
  cd "$TMPDIR/repo"
}

teardown() { rm -rf "$TMPDIR"; }

@test "lane list prints header and empty list when no lanes" {
  run lane_sh list
  [ "$status" -eq 0 ]
  echo "$output" | grep -qi "no lane"
}

@test "lane list shows lane/* branches with age" {
  git switch -c lane/alpha; git commit --allow-empty -m "alpha"; git switch main
  git switch -c lane/codex/beta; git commit --allow-empty -m "beta"; git switch main
  run lane_sh list
  [ "$status" -eq 0 ]
  echo "$output" | grep -qF "lane/alpha"
  echo "$output" | grep -qF "lane/codex/beta"
}

@test "lane list does not show main or safety/*" {
  git switch -c safety/2026-04-20-test; git commit --allow-empty -m "snap"; git switch main
  run lane_sh list
  [ "$status" -eq 0 ]
  echo "$output" | grep -qvF "safety/2026-04-20-test"
  echo "$output" | grep -qvF "^main$"
}

@test "lane list flags merged lanes" {
  git switch -c lane/merged
  git commit --allow-empty -m "done"
  git switch main
  git merge --ff-only lane/merged
  run lane_sh list
  [ "$status" -eq 0 ]
  echo "$output" | grep -qi "merged"
}

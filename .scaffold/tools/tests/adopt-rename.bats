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

@test "adopt rename lists non-conforming branches" {
  git switch -c codex/extract
  git switch -c feature/foo
  git switch main
  run bash -c "set +e; set +o pipefail; printf 'n\n' | $LANE_SH_PATH adopt rename 2>&1"
  [ "$status" -eq 0 ]
  echo "$output" | grep -qF "codex/extract"
  echo "$output" | grep -qF "feature/foo"
}

@test "adopt rename does not list main or safety/*" {
  git switch -c safety/2026-04-20-snap
  git switch main
  run bash -c "set +e; set +o pipefail; printf 'n\n' | $LANE_SH_PATH adopt rename 2>&1"
  [ "$status" -eq 0 ]
  echo "$output" | grep -qvF "safety/"
  echo "$output" | grep -qvxF "main"
}

@test "adopt rename renames a branch when user provides new name" {
  git switch -c codex/extract
  git push -u origin codex/extract
  git switch main
  # answer: 'y' to rename, then 'lane/codex/extract' as new name
  run bash -c "set +e; set +o pipefail; printf 'y\nlane/codex/extract\n' | $LANE_SH_PATH adopt rename 2>&1"
  [ "$status" -eq 0 ]
  git show-ref --verify --quiet refs/heads/lane/codex/extract
  ! git show-ref --verify --quiet refs/heads/codex/extract
}

@test "adopt rename 'skip' leaves branch alone" {
  git switch -c codex/extract
  git push -u origin codex/extract
  git switch main
  run bash -c "set +e; set +o pipefail; printf 'n\n' | $LANE_SH_PATH adopt rename 2>&1"
  [ "$status" -eq 0 ]
  git show-ref --verify --quiet refs/heads/codex/extract
}

@test "adopt rename no-op when nothing non-conforming" {
  git switch -c lane/conforming
  git switch main
  run lane_sh adopt rename
  [ "$status" -eq 0 ]
  echo "$output" | grep -qi "nothing"
}

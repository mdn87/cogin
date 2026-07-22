#!/usr/bin/env bats

load 'helpers.bash'

setup() {
  TMPDIR="$(mktemp -d)"
  export TMPDIR
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../../../" && pwd)"
  export LANE_SH_PATH="$REPO_ROOT/runtime/tools/lane.sh"
}

teardown() { rm -rf "$TMPDIR"; }

@test "lane doctor passes on a clean repo inside hardened sync root" {
  make_fake_syncthing_root "$TMPDIR/sync"
  bash -c "source '$REPO_ROOT/runtime/tools/lane-stignore-block.sh' && stignore_block" >> "$TMPDIR/sync/.stignore"
  make_fake_repo "$TMPDIR/sync/repo"
  cd "$TMPDIR/sync/repo"
  run lane_sh doctor
  [ "$status" -eq 0 ]
}

@test "lane doctor fails when .stignore missing rules" {
  make_fake_syncthing_root "$TMPDIR/sync"
  make_fake_repo "$TMPDIR/sync/repo"
  cd "$TMPDIR/sync/repo"
  run lane_sh doctor
  [ "$status" -ne 0 ]
  echo "$output" | grep -qi "stignore"
}

@test "lane doctor fails when .worktrees/ present" {
  make_fake_syncthing_root "$TMPDIR/sync"
  bash -c "source '$REPO_ROOT/runtime/tools/lane-stignore-block.sh' && stignore_block" >> "$TMPDIR/sync/.stignore"
  make_fake_repo "$TMPDIR/sync/repo"
  mkdir -p "$TMPDIR/sync/repo/.worktrees/xyz"
  cd "$TMPDIR/sync/repo"
  run lane_sh doctor
  [ "$status" -ne 0 ]
  echo "$output" | grep -qi "worktrees"
}

@test "lane doctor fails on non-conforming branch name" {
  make_fake_syncthing_root "$TMPDIR/sync"
  bash -c "source '$REPO_ROOT/runtime/tools/lane-stignore-block.sh' && stignore_block" >> "$TMPDIR/sync/.stignore"
  make_fake_repo "$TMPDIR/sync/repo"
  cd "$TMPDIR/sync/repo"
  git switch -c feature/nope
  run lane_sh doctor
  [ "$status" -ne 0 ]
  echo "$output" | grep -qi "branch"
}

@test "lane doctor skips .stignore check when no .stfolder found" {
  make_fake_repo "$TMPDIR/standalone"
  cd "$TMPDIR/standalone"
  run lane_sh doctor
  # Should still run other checks; .stignore check is skipped with info note.
  echo "$output" | grep -qi "no syncthing folder root"
}

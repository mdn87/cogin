#!/usr/bin/env bats

load 'helpers.bash'

setup() {
  TMPDIR="$(mktemp -d)"
  export TMPDIR
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../../../" && pwd)"
  export LANE_SH_PATH="$REPO_ROOT/runtime/tools/lane.sh"
}

teardown() { rm -rf "$TMPDIR"; }

@test "adopt harden appends full block when .stignore has none of the rules" {
  make_fake_syncthing_root "$TMPDIR/sync"
  make_fake_repo "$TMPDIR/sync/repo"
  cd "$TMPDIR/sync/repo"
  run lane_sh adopt harden
  [ "$status" -eq 0 ]
  assert_file_contains "$TMPDIR/sync/.stignore" "(?d)**/.git"
  assert_file_contains "$TMPDIR/sync/.stignore" "(?d)**/.worktrees"
  assert_file_contains "$TMPDIR/sync/.stignore" "(?d)**/.tmp-debug*"
}

@test "adopt harden is idempotent (no duplicate block on re-run)" {
  make_fake_syncthing_root "$TMPDIR/sync"
  make_fake_repo "$TMPDIR/sync/repo"
  cd "$TMPDIR/sync/repo"
  lane_sh adopt harden
  local first; first="$(wc -l < "$TMPDIR/sync/.stignore")"
  run lane_sh adopt harden
  [ "$status" -eq 0 ]
  local second; second="$(wc -l < "$TMPDIR/sync/.stignore")"
  [ "$first" = "$second" ]
}

@test "adopt harden does not touch .stignore when all rules already present" {
  make_fake_syncthing_root "$TMPDIR/sync"
  bash -c "source '$REPO_ROOT/runtime/tools/lane-stignore-block.sh' && stignore_block" > "$TMPDIR/sync/.stignore"
  make_fake_repo "$TMPDIR/sync/repo"
  cd "$TMPDIR/sync/repo"
  local before; before="$(checksum_file "$TMPDIR/sync/.stignore")"
  run lane_sh adopt harden
  [ "$status" -eq 0 ]
  local after; after="$(checksum_file "$TMPDIR/sync/.stignore")"
  [ "$before" = "$after" ]
}

@test "adopt harden fails when no Syncthing folder root found" {
  make_fake_repo "$TMPDIR/standalone"
  cd "$TMPDIR/standalone"
  run lane_sh adopt harden
  [ "$status" -ne 0 ]
  echo "$output" | grep -qi "stfolder"
}

@test "adopt harden prints next-step instructions" {
  make_fake_syncthing_root "$TMPDIR/sync"
  make_fake_repo "$TMPDIR/sync/repo"
  cd "$TMPDIR/sync/repo"
  run lane_sh adopt harden
  echo "$output" | grep -qi "lane adopt cleanup"
  echo "$output" | grep -qi "syncthing"
}

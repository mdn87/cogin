#!/usr/bin/env bats

load 'helpers.bash'

setup() {
  TMPDIR="$(mktemp -d)"
  export TMPDIR
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../../../" && pwd)"
  export LANE_SH_PATH="$REPO_ROOT/runtime/tools/lane.sh"
}

teardown() { rm -rf "$TMPDIR"; }

@test "adopt cleanup refuses when .stignore lacks rules (propagation not possible)" {
  make_fake_syncthing_root "$TMPDIR/sync"
  make_fake_repo "$TMPDIR/sync/repo"
  mkdir -p "$TMPDIR/sync/repo/.worktrees/stale"
  cd "$TMPDIR/sync/repo"
  run bash -c "set +e; set +o pipefail; printf 'YES\n' | $LANE_SH_PATH adopt cleanup 2>&1"
  [ "$status" -ne 0 ]
  echo "$output" | grep -qi "harden"
  [ -d "$TMPDIR/sync/repo/.worktrees/stale" ]
}

@test "adopt cleanup with --assume-propagated removes .worktrees/" {
  make_fake_syncthing_root "$TMPDIR/sync"
  bash -c "source '$REPO_ROOT/runtime/tools/lane-stignore-block.sh' && stignore_block" >> "$TMPDIR/sync/.stignore"
  make_fake_repo "$TMPDIR/sync/repo"
  mkdir -p "$TMPDIR/sync/repo/.worktrees/stale-a"
  mkdir -p "$TMPDIR/sync/repo/.worktrees/stale-b"
  cd "$TMPDIR/sync/repo"
  run lane_sh adopt cleanup --assume-propagated
  [ "$status" -eq 0 ]
  [ ! -d "$TMPDIR/sync/repo/.worktrees" ]
}

@test "adopt cleanup interactive requires typed YES" {
  make_fake_syncthing_root "$TMPDIR/sync"
  bash -c "source '$REPO_ROOT/runtime/tools/lane-stignore-block.sh' && stignore_block" >> "$TMPDIR/sync/.stignore"
  make_fake_repo "$TMPDIR/sync/repo"
  mkdir -p "$TMPDIR/sync/repo/.worktrees/stale"
  cd "$TMPDIR/sync/repo"
  # 'y' alone is not enough — we require literal YES.
  run bash -c "set +e; set +o pipefail; printf 'y\n' | $LANE_SH_PATH adopt cleanup 2>&1"
  [ "$status" -ne 0 ]
  [ -d "$TMPDIR/sync/repo/.worktrees/stale" ]
}

@test "adopt cleanup interactive with YES proceeds" {
  make_fake_syncthing_root "$TMPDIR/sync"
  bash -c "source '$REPO_ROOT/runtime/tools/lane-stignore-block.sh' && stignore_block" >> "$TMPDIR/sync/.stignore"
  make_fake_repo "$TMPDIR/sync/repo"
  mkdir -p "$TMPDIR/sync/repo/.worktrees/stale"
  cd "$TMPDIR/sync/repo"
  run bash -c "set +e; set +o pipefail; printf 'YES\n' | $LANE_SH_PATH adopt cleanup 2>&1"
  [ "$status" -eq 0 ]
  [ ! -d "$TMPDIR/sync/repo/.worktrees" ]
}

@test "adopt cleanup is a no-op when nothing to remove" {
  make_fake_syncthing_root "$TMPDIR/sync"
  bash -c "source '$REPO_ROOT/runtime/tools/lane-stignore-block.sh' && stignore_block" >> "$TMPDIR/sync/.stignore"
  make_fake_repo "$TMPDIR/sync/repo"
  cd "$TMPDIR/sync/repo"
  run lane_sh adopt cleanup --assume-propagated
  [ "$status" -eq 0 ]
  echo "$output" | grep -qi "nothing"
}

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

@test "lane prune deletes local lane whose origin branch is gone" {
  git switch -c lane/gone
  git push -u origin lane/gone
  git switch main
  git push origin :lane/gone  # delete on origin
  git fetch --prune
  run bash -c "set +e; set +o pipefail; printf 'y\n' | $LANE_SH_PATH prune 2>&1"
  [ "$status" -eq 0 ]
  ! git show-ref --verify --quiet refs/heads/lane/gone
}

@test "lane prune deletes local lane merged into origin/main" {
  git switch -c lane/merged
  git commit --allow-empty -m "m"
  git push -u origin lane/merged
  git switch main
  git merge --ff-only lane/merged
  run bash -c "set +e; set +o pipefail; printf 'y\n' | $LANE_SH_PATH prune 2>&1"
  [ "$status" -eq 0 ]
  ! git show-ref --verify --quiet refs/heads/lane/merged
}

@test "lane prune never touches main or safety/*" {
  git switch -c safety/2026-04-20-snap
  git commit --allow-empty -m "snap"
  git switch main
  run bash -c "set +e; set +o pipefail; printf 'y\n' | $LANE_SH_PATH prune 2>&1"
  [ "$status" -eq 0 ]
  git show-ref --verify --quiet refs/heads/main
  git show-ref --verify --quiet refs/heads/safety/2026-04-20-snap
}

@test "lane prune no-op when nothing to prune" {
  git switch -c lane/active
  git commit --allow-empty -m "active"
  git push -u origin lane/active
  git switch main
  run bash -c "set +e; set +o pipefail; printf 'y\n' | $LANE_SH_PATH prune 2>&1"
  [ "$status" -eq 0 ]
  echo "$output" | grep -qi "nothing"
  git show-ref --verify --quiet refs/heads/lane/active
}

@test "lane prune answered 'n' deletes nothing" {
  git switch -c lane/gone
  git push -u origin lane/gone
  git switch main
  git push origin :lane/gone
  git fetch --prune
  run bash -c "set +e; set +o pipefail; printf 'n\n' | $LANE_SH_PATH prune 2>&1"
  [ "$status" -eq 0 ]
  git show-ref --verify --quiet refs/heads/lane/gone
}

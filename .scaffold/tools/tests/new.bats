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

@test "lane new <slug> creates lane/<slug> and switches to it" {
  run lane_sh new feature-x
  [ "$status" -eq 0 ]
  [ "$(git rev-parse --abbrev-ref HEAD)" = "lane/feature-x" ]
}

@test "lane new <slug> --agent codex creates lane/codex/<slug>" {
  run lane_sh new extract --agent codex
  [ "$status" -eq 0 ]
  [ "$(git rev-parse --abbrev-ref HEAD)" = "lane/codex/extract" ]
}

@test "lane new pushes upstream" {
  run lane_sh new feature-y
  [ "$status" -eq 0 ]
  git branch -vv | grep -qF "lane/feature-y" | grep -q "origin/lane/feature-y" || \
    git rev-parse --abbrev-ref --symbolic-full-name '@{upstream}' | grep -qF "origin/lane/feature-y"
}

@test "lane new rejects empty slug" {
  run lane_sh new ""
  [ "$status" -ne 0 ]
  echo "$output" | grep -qi "slug"
}

@test "lane new rejects slug with slash" {
  run lane_sh new "foo/bar"
  [ "$status" -ne 0 ]
  echo "$output" | grep -qi "slash"
}

@test "lane new is idempotent if lane already exists (switches to it)" {
  lane_sh new already-there
  git switch main
  run lane_sh new already-there
  [ "$status" -eq 0 ]
  [ "$(git rev-parse --abbrev-ref HEAD)" = "lane/already-there" ]
}

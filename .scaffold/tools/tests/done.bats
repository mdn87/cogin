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

@test "lane done merges current lane to main and deletes it" {
  git switch -c lane/feature
  git commit --allow-empty -m "lane work"
  git push -u origin lane/feature
  run lane_sh done
  [ "$status" -eq 0 ]
  [ "$(git rev-parse --abbrev-ref HEAD)" = "main" ]
  ! git show-ref --verify --quiet refs/heads/lane/feature
  ! git ls-remote --exit-code --heads origin lane/feature
}

@test "lane done --branch accepts full branch name" {
  git switch -c lane/codex/x
  git commit --allow-empty -m "x"
  git push -u origin lane/codex/x
  git switch main
  run lane_sh done --branch lane/codex/x
  [ "$status" -eq 0 ]
  ! git show-ref --verify --quiet refs/heads/lane/codex/x
}

@test "lane done refuses when working tree is dirty" {
  git switch -c lane/feature
  echo dirty > new-file
  run lane_sh done
  [ "$status" -ne 0 ]
  echo "$output" | grep -qi "clean"
}

@test "lane done refuses on non-lane branch" {
  run lane_sh done --branch main
  [ "$status" -ne 0 ]
  echo "$output" | grep -qi "lane/"
}

@test "lane done prompts on non-ff and aborts on 'no'" {
  git switch -c lane/feature
  git commit --allow-empty -m "feat"
  git switch main
  git commit --allow-empty -m "main-advanced"
  run bash -c "echo n | $LANE_SH_PATH done --branch lane/feature"
  [ "$status" -ne 0 ]
  # Lane not deleted, main not advanced past its own commit.
  git show-ref --verify --quiet refs/heads/lane/feature
}

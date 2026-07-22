#!/usr/bin/env bats

load 'helpers.bash'

setup() {
  TMPDIR="$(mktemp -d)"
  export TMPDIR
}

teardown() {
  rm -rf "$TMPDIR"
}

@test "make_fake_repo creates a working repo with origin" {
  make_fake_repo "$TMPDIR/repo"
  [ -d "$TMPDIR/repo/.git" ]
  ( cd "$TMPDIR/repo" && git log --oneline | grep -q "init" )
  ( cd "$TMPDIR/repo" && git remote -v | grep -q "origin" )
}

@test "make_fake_syncthing_root creates .stfolder and .stignore" {
  make_fake_syncthing_root "$TMPDIR/sync"
  [ -d "$TMPDIR/sync/.stfolder" ]
  [ -f "$TMPDIR/sync/.stignore" ]
}

@test "assert_file_contains passes on match" {
  echo "hello world" > "$TMPDIR/file"
  run assert_file_contains "$TMPDIR/file" "hello"
  [ "$status" -eq 0 ]
}

@test "assert_file_contains fails on miss" {
  echo "hello world" > "$TMPDIR/file"
  run assert_file_contains "$TMPDIR/file" "goodbye"
  [ "$status" -ne 0 ]
}

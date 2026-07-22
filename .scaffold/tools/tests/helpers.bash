# Test helpers for lane.sh. Source from .bats files.

# make_fake_repo <dir>
# Creates a minimal git repo at <dir> with a single commit on main and a fake origin.
make_fake_repo() {
  local dir="$1"
  mkdir -p "$dir"
  ( cd "$dir"
    git init -q -b main
    git config user.email "test@local"
    git config user.name "Test"
    echo "init" > README.md
    git add README.md
    git commit -q -m "init"
    # Create a bare "origin" so push operations work.
    mkdir -p ../origin.git
    ( cd ../origin.git && git init -q --bare )
    git remote add origin "../origin.git"
    git push -q -u origin main
  )
}

# make_fake_synthing_root <dir>
# Creates <dir> as a Syncthing folder root (contains .stfolder marker).
make_fake_syncthing_root() {
  local dir="$1"
  mkdir -p "$dir/.stfolder"
  touch "$dir/.stignore"
}

# assert_file_contains <file> <string>
assert_file_contains() {
  local file="$1" needle="$2"
  grep -qF -- "$needle" "$file" || {
    echo "Expected $file to contain: $needle" >&2
    echo "Actual contents:" >&2
    cat "$file" >&2
    return 1
  }
}

# checksum_file <file>
# Emit a stable checksum string that works across macOS and Linux.
checksum_file() {
  local file="$1"
  if command -v md5sum >/dev/null 2>&1; then
    md5sum "$file"
  elif command -v md5 >/dev/null 2>&1; then
    md5 -q "$file"
  else
    cksum "$file"
  fi
}

# lane_sh
# Invoke the lane.sh under test with a clean env.
lane_sh() {
  bash "$LANE_SH_PATH" "$@"
}

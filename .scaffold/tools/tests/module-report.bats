#!/usr/bin/env bats

# Tests for runtime/tools/module-report.sh — Contract 1 (aeta v2 contract bundle).

setup() {
  TMPDIR="$(mktemp -d)"
  export TMPDIR
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../../../" && pwd)"
  TOOL="$REPO_ROOT/runtime/tools/module-report.sh"
  export TOOL
}

teardown() { rm -rf "$TMPDIR"; }

# Build a minimal fake parent (with .gitmodules) plus a module dir with the
# given lugos-module.toml content. Echoes the module path.
make_fake_module() {
  local parent="$TMPDIR/parent"
  local module="$parent/$1"
  mkdir -p "$module"
  cat > "$parent/.gitmodules" <<EOF
[submodule "$1"]
	path = $1
	url = https://example.com/$1.git
[submodule "other"]
	path = other
	url = https://example.com/other.git
EOF
  echo "$module"
}

write_minimal_toml() {
  local module="$1"
  cat > "$module/lugos-module.toml" <<'EOF'
[identity]
name = "demo"
version = "0.1.0"
owner = "alice"
schema_version = "1.0.0"

[risk]
security_boundary = false
network_egress = false
command_exec = false

[provenance]
generated_by = "hand"
last_validated = "2026-05-02T00:00:00Z"
EOF
}

@test "validate passes on a minimal valid toml" {
  module="$(make_fake_module demo)"
  write_minimal_toml "$module"
  run bash "$TOOL" --validate --module "$module"
  [ "$status" -eq 0 ]
  echo "$output" | grep -q "validation OK"
}

@test "validate fails when lugos-module.toml is missing" {
  module="$(make_fake_module demo)"
  run bash "$TOOL" --validate --module "$module"
  [ "$status" -ne 0 ]
  echo "$output" | grep -qi "missing"
}

@test "validate fails on missing required identity field" {
  module="$(make_fake_module demo)"
  cat > "$module/lugos-module.toml" <<'EOF'
[identity]
name = "demo"
version = "0.1.0"
schema_version = "1.0.0"

[risk]
security_boundary = false
network_egress = false
command_exec = false

[provenance]
generated_by = "hand"
last_validated = "2026-05-02T00:00:00Z"
EOF
  run bash "$TOOL" --validate --module "$module"
  [ "$status" -ne 0 ]
  echo "$output" | grep -q "owner missing"
}

@test "validate fails when identity.name is not in parent .gitmodules" {
  module="$(make_fake_module demo)"
  write_minimal_toml "$module"
  # Now tamper: rename module folder; identity.name 'demo' no longer in .gitmodules.
  rm "$module/../.gitmodules"
  cat > "$module/../.gitmodules" <<EOF
[submodule "other"]
	path = other
	url = https://example.com/other.git
EOF
  run bash "$TOOL" --validate --module "$module"
  [ "$status" -ne 0 ]
  echo "$output" | grep -qi "does not resolve to a submodule"
}

@test "validate rejects dep_type outside the closed vocab" {
  module="$(make_fake_module demo)"
  write_minimal_toml "$module"
  cat >> "$module/lugos-module.toml" <<'EOF'

[deps.bad]
type = "made-up-type"
target = "other"
source = "x.py:1"
EOF
  run bash "$TOOL" --validate --module "$module"
  [ "$status" -ne 0 ]
  echo "$output" | grep -qi "closed vocab"
}

@test "validate accepts all 5 dep_type values from the closed vocab" {
  module="$(make_fake_module demo)"
  write_minimal_toml "$module"
  cat >> "$module/lugos-module.toml" <<'EOF'

[deps.a]
type = "code-import"
target = "other"
source = "a.py:1"

[deps.b]
type = "config-link"
target = "other"
source = "b.py:1"

[deps.c]
type = "catalog-ref"
target = "other"
source = "c.py:1"

[deps.d]
type = "doc-ref"
target = "other"
source = "d.md:1"

[deps.e]
type = "runtime-call"
target = "other"
source = "e.py:1"
EOF
  run bash "$TOOL" --validate --module "$module"
  [ "$status" -eq 0 ]
}

@test "validate fails when dep target is not a real submodule" {
  module="$(make_fake_module demo)"
  write_minimal_toml "$module"
  cat >> "$module/lugos-module.toml" <<'EOF'

[deps.x]
type = "code-import"
target = "ghost-module"
source = "x.py:1"
EOF
  run bash "$TOOL" --validate --module "$module"
  [ "$status" -ne 0 ]
  echo "$output" | grep -qi "does not resolve to a submodule"
}

@test "validate rejects surface type outside closed vocab" {
  module="$(make_fake_module demo)"
  write_minimal_toml "$module"
  cat >> "$module/lugos-module.toml" <<'EOF'

[surfaces.weird]
type = "webhook"
path = "x"
EOF
  run bash "$TOOL" --validate --module "$module"
  [ "$status" -ne 0 ]
  echo "$output" | grep -qi "closed vocab"
}

@test "validate fails when surface path does not exist" {
  module="$(make_fake_module demo)"
  write_minimal_toml "$module"
  cat >> "$module/lugos-module.toml" <<'EOF'

[surfaces.cli]
type = "entry-point"
path = "does/not/exist.sh"
EOF
  run bash "$TOOL" --validate --module "$module"
  [ "$status" -ne 0 ]
  echo "$output" | grep -qi "does not exist"
}

@test "validate fails on unparseable last_validated" {
  module="$(make_fake_module demo)"
  write_minimal_toml "$module"
  sed -i.bak 's/last_validated = .*/last_validated = "not-a-date"/' "$module/lugos-module.toml"
  rm "$module/lugos-module.toml.bak"
  run bash "$TOOL" --validate --module "$module"
  [ "$status" -ne 0 ]
  echo "$output" | grep -qi "not a parseable"
}

@test "validate warns (but passes) on stale last_validated" {
  module="$(make_fake_module demo)"
  write_minimal_toml "$module"
  # set last_validated to a clearly-stale date
  sed -i.bak 's/last_validated = .*/last_validated = "2000-01-01T00:00:00Z"/' "$module/lugos-module.toml"
  rm "$module/lugos-module.toml.bak"
  run bash "$TOOL" --validate --module "$module" --freshness-days 30
  [ "$status" -eq 0 ]
  echo "$output" | grep -qi "stale"
}

@test "stamp updates last_validated and is idempotent" {
  module="$(make_fake_module demo)"
  write_minimal_toml "$module"
  run bash "$TOOL" --stamp --module "$module"
  [ "$status" -eq 0 ]
  grep -v "2026-05-02T00:00:00Z" "$module/lugos-module.toml" >/dev/null
  grep -E 'last_validated = "[0-9]{4}-[0-9]{2}-[0-9]{2}T' "$module/lugos-module.toml"
}

@test "validate does NOT mutate last_validated" {
  module="$(make_fake_module demo)"
  write_minimal_toml "$module"
  before="$(grep last_validated "$module/lugos-module.toml")"
  run bash "$TOOL" --validate --module "$module"
  [ "$status" -eq 0 ]
  after="$(grep last_validated "$module/lugos-module.toml")"
  [ "$before" = "$after" ]
}

@test "regenerate preserves identity, risk, and docs sections" {
  module="$(make_fake_module demo)"
  write_minimal_toml "$module"
  mkdir -p "$module/docs"
  echo "x" > "$module/docs/readme.md"
  cat >> "$module/lugos-module.toml" <<'EOF'

[docs.readme]
path = "docs/readme.md"
post_pass_eligible = true
EOF
  run bash "$TOOL" --regenerate --module "$module"
  [ "$status" -eq 0 ]
  grep -q 'name = "demo"' "$module/lugos-module.toml"
  grep -q 'security_boundary = false' "$module/lugos-module.toml"
  grep -q 'docs/readme.md' "$module/lugos-module.toml"
  grep -q 'post_pass_eligible = true' "$module/lugos-module.toml"
}

@test "regenerate stamps last_validated after writing" {
  module="$(make_fake_module demo)"
  write_minimal_toml "$module"
  run bash "$TOOL" --regenerate --module "$module"
  [ "$status" -eq 0 ]
  grep -v "2026-05-02T00:00:00Z" "$module/lugos-module.toml" >/dev/null
}

@test "help flag exits zero" {
  run bash "$TOOL" --help
  [ "$status" -eq 0 ]
  echo "$output" | grep -qi "module-report"
}

@test "no mode flag is a usage error" {
  run bash "$TOOL"
  [ "$status" -ne 0 ]
}

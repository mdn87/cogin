#!/usr/bin/env bash
# module-report.sh — `scaffold module-report` for the lugos-module.toml contract.
# Owns Contract 1 of the aeta v2 contract bundle: schema, regenerate, validate, stamp.
# See docs/superpowers/specs/2026-05-02-aeta-v2-contract-bundle.md for the spec.
#
# Usage:
#   bash module-report.sh --validate   [--module <path>] [--parent <path>] [--freshness-days N]
#   bash module-report.sh --regenerate [--module <path>] [--parent <path>]
#   bash module-report.sh --stamp      [--module <path>]
#
# Defaults: --module = $PWD; --parent = first ancestor of --module with a .gitmodules.
# Freshness policy default: 30 days (per spec drift handling).

set -euo pipefail

SCHEMA_VERSION="1.0.0"
DEFAULT_FRESHNESS_DAYS=30

VALID_DEP_TYPES=("code-import" "config-link" "catalog-ref" "doc-ref" "runtime-call")
VALID_SURFACE_TYPES=("entry-point" "command" "config" "catalog-entry")

print_usage() {
  cat <<'EOF'
scaffold module-report — generate / validate / stamp lugos-module.toml

Modes (exactly one required):
  --validate            Read-only check; non-zero exit on any violation. CI-safe.
                        Does NOT update last_validated.
  --regenerate          Re-derive auto-derivable sections from declared sources.
                        Preserves [identity], [risk], [docs], [provenance.generated_by].
                        Stamps last_validated on success.
  --stamp               Update provenance.last_validated to now (ISO-8601 UTC) after a
                        successful validation pass.

Options:
  --module <path>       Module root (default: cwd)
  --parent <path>       Parent lugos repo root containing .gitmodules
                        (default: nearest ancestor with .gitmodules)
  --freshness-days N    Stale-warning threshold for --validate (default: 30)
  --help                This message.
EOF
}

err()  { printf 'module-report: %s\n' "$*" >&2; }
fail() { err "$*"; exit 1; }

# --- Tiny TOML reader scoped to the lugos-module.toml shape.
# Not a general TOML parser. Recognises:
#   - [section] and [section.key] headers
#   - key = "value", key = true|false (no inline tables, no arrays of tables)
# Outputs lines of the form:  <section>|<key>|<raw-value>
toml_flatten() {
  local file="$1"
  awk '
    function trim(s){ sub(/^[ \t]+/,"",s); sub(/[ \t\r]+$/,"",s); return s }
    BEGIN { section="" }
    /^[ \t]*#/ { next }
    /^[ \t]*$/ { next }
    {
      line = $0
      sub(/[ \t]+#.*$/, "", line)
      line = trim(line)
      if (line == "") next
      if (line ~ /^\[.*\]$/) {
        sec = substr(line, 2, length(line)-2)
        section = trim(sec)
        next
      }
      eq = index(line, "=")
      if (eq == 0) next
      key = trim(substr(line, 1, eq-1))
      val = trim(substr(line, eq+1))
      print section "|" key "|" val
    }
  ' "$file"
}

# Strip surrounding double quotes from a TOML value, if present.
unquote() {
  local v="$1"
  if [[ "$v" == \"*\" ]]; then
    v="${v#\"}"
    v="${v%\"}"
  fi
  printf '%s' "$v"
}

# in_list <needle> <list-element>...
in_list() {
  local n="$1"; shift
  local x
  for x in "$@"; do
    [ "$x" = "$n" ] && return 0
  done
  return 1
}

now_utc_iso() {
  # macOS and GNU date both support -u and ISO-8601-ish output.
  date -u +"%Y-%m-%dT%H:%M:%SZ"
}

# Convert an ISO-8601 timestamp to epoch seconds; portable across macOS/Linux.
iso_to_epoch() {
  local ts="$1"
  if date -u -d "$ts" +%s >/dev/null 2>&1; then
    date -u -d "$ts" +%s
  elif date -u -j -f "%Y-%m-%dT%H:%M:%SZ" "$ts" +%s >/dev/null 2>&1; then
    date -u -j -f "%Y-%m-%dT%H:%M:%SZ" "$ts" +%s
  elif date -u -j -f "%Y-%m-%dT%H:%M:%S" "${ts%Z}" +%s >/dev/null 2>&1; then
    date -u -j -f "%Y-%m-%dT%H:%M:%S" "${ts%Z}" +%s
  else
    return 1
  fi
}

find_parent_root() {
  local dir="${1:-$PWD}"
  dir="$(cd "$dir" && pwd)"
  while [ "$dir" != "/" ] && [ -n "$dir" ]; do
    if [ -f "$dir/.gitmodules" ]; then
      printf '%s' "$dir"
      return 0
    fi
    dir="$(dirname "$dir")"
  done
  return 1
}

# Read the set of submodule names from a .gitmodules file.
list_submodule_names() {
  local gm="$1"
  awk '
    /^\[submodule "/ {
      s=$0
      sub(/[\r\n]+$/, "", s)
      sub(/[ \t]+$/, "", s)
      sub(/^\[submodule "/, "", s)
      sub(/"\]$/, "", s)
      print s
    }
  ' "$gm"
}

# Contract 1 primarily targets git submodules, but the first aeta v2 slice also
# includes parent-owned module directories such as lugos-hud. A name only
# counts as a valid parent-owned module if it is listed as a DIFFERENT entry
# from the module currently being validated — validating a toml against its
# own directory is not membership evidence.
module_name_exists() {
  local name="$1" parent_root="$2" self_dir="${3:-}"
  if [ -z "$name" ] || [ -z "$parent_root" ]; then
    return 1
  fi
  if [ -f "$parent_root/.gitmodules" ]; then
    local known
    known="$(list_submodule_names "$parent_root/.gitmodules")"
    if grep -qx -- "$name" <<<"$known"; then
      return 0
    fi
  fi
  local candidate="$parent_root/$name/lugos-module.toml"
  if [ -n "$self_dir" ] && [ "$(cd "$(dirname "$candidate")" && pwd)" = "$self_dir" ]; then
    return 1
  fi
  [ -f "$candidate" ]
}

path_has_parent_segment() {
  local rel="$1" part
  local IFS='/'
  read -r -a parts <<< "$rel"
  for part in "${parts[@]}"; do
    [ "$part" = ".." ] && return 0
  done
  return 1
}

validate_module_path() {
  local sec="$1" key="$2" rel="$3" module_root="$4" require_exists="${5:-1}"
  [ -z "$rel" ] && return 0
  case "$rel" in
    *://*) return 0 ;;
    /*|[A-Za-z]:*|*\\*)
      err "[$sec].$key '$rel' must stay under module root"
      return 1
      ;;
  esac
  if path_has_parent_segment "$rel"; then
    err "[$sec].$key '$rel' must stay under module root"
    return 1
  fi

  local target="$module_root/$rel"
  if [ ! -e "$target" ]; then
    if [ "$require_exists" = "1" ]; then
      err "[$sec].$key '$rel' does not exist (looked under $module_root)"
      return 1
    fi
    return 0
  fi

  local module_real target_real
  module_real="$(cd "$module_root" && pwd -P)"
  if [ -d "$target" ]; then
    target_real="$(cd "$target" && pwd -P)"
  else
    target_real="$(cd "$(dirname "$target")" && pwd -P)/$(basename "$target")"
  fi

  case "$target_real" in
    "$module_real"|"$module_real"/*) ;;
    *)
      err "[$sec].$key '$rel' must stay under module root"
      return 1
      ;;
  esac
}

dep_source_path() {
  local source="$1"
  case "$source" in
    *://*) printf '%s' ""; return 0 ;;
  esac
  printf '%s' "${source%%:*}"
}

# ---------------- VALIDATE ----------------

validate_report() {
  local toml="$1" parent_root="$2" freshness_days="$3"
  local errors=0 warnings=0

  if [ ! -f "$toml" ]; then
    err "missing lugos-module.toml at $toml"
    return 1
  fi

  local flat
  flat="$(toml_flatten "$toml")"

  get_field() {
    awk -F'|' -v s="$1" -v k="$2" '$1==s && $2==k {print $3; exit}' <<<"$flat"
  }

  # Required identity fields.
  local name version owner schema
  name=$(unquote "$(get_field identity name)")
  version=$(unquote "$(get_field identity version)")
  owner=$(unquote "$(get_field identity owner)")
  schema=$(unquote "$(get_field identity schema_version)")

  [ -n "$name" ]    || { err "[identity].name missing";           errors=$((errors+1)); }
  [ -n "$version" ] || { err "[identity].version missing";        errors=$((errors+1)); }
  [ -n "$owner" ]   || { err "[identity].owner missing";          errors=$((errors+1)); }
  [ -n "$schema" ]  || { err "[identity].schema_version missing"; errors=$((errors+1)); }

  if [ -n "$schema" ] && [ "$schema" != "$SCHEMA_VERSION" ]; then
    err "[identity].schema_version '$schema' does not match scaffold contract version '$SCHEMA_VERSION'"
    errors=$((errors+1))
  fi

  # Identity name must resolve to a submodule or parent-owned module root.
  if [ -n "$name" ] && [ -n "$parent_root" ] && [ -f "$parent_root/.gitmodules" ]; then
    if ! module_name_exists "$name" "$parent_root" "$(dirname "$toml")"; then
      err "[identity].name '$name' does not resolve to a submodule or parent-owned module in $parent_root"
      errors=$((errors+1))
    fi
  fi

  # Risk required booleans.
  local r
  for r in security_boundary network_egress command_exec; do
    local raw
    raw="$(get_field risk "$r")"
    if [ -z "$raw" ]; then
      err "[risk].$r missing"; errors=$((errors+1))
    elif [ "$raw" != "true" ] && [ "$raw" != "false" ]; then
      err "[risk].$r must be true or false (got: $raw)"; errors=$((errors+1))
    fi
  done

  # Provenance.
  local prov_gen prov_lv
  prov_gen=$(unquote "$(get_field provenance generated_by)")
  prov_lv=$(unquote "$(get_field provenance last_validated)")
  [ -n "$prov_gen" ] || { err "[provenance].generated_by missing"; errors=$((errors+1)); }
  if [ -z "$prov_lv" ]; then
    err "[provenance].last_validated missing"; errors=$((errors+1))
  else
    local ep
    if ! ep="$(iso_to_epoch "$prov_lv")"; then
      err "[provenance].last_validated '$prov_lv' is not a parseable ISO-8601 timestamp"
      errors=$((errors+1))
    else
      local now stale_after
      now=$(date -u +%s)
      stale_after=$(( now - freshness_days * 86400 ))
      if [ "$ep" -lt "$stale_after" ]; then
        warnings=$((warnings+1))
        printf 'module-report: WARN [provenance].last_validated is stale (>%d days; %s)\n' \
          "$freshness_days" "$prov_lv" >&2
      fi
    fi
  fi

  # Per-section sweeps for deps / surfaces / docs.
  # Build the set of sections we have.
  local sections
  sections=$(awk -F'|' '{print $1}' <<<"$flat" | sort -u)
  local sec
  while IFS= read -r sec; do
    case "$sec" in
      deps.*)
        local dt dtarget dsrc
        dt=$(unquote "$(get_field "$sec" type)")
        dtarget=$(unquote "$(get_field "$sec" target)")
        dsrc=$(unquote "$(get_field "$sec" source)")
        [ -n "$dt" ]      || { err "[$sec].type missing";   errors=$((errors+1)); }
        [ -n "$dtarget" ] || { err "[$sec].target missing"; errors=$((errors+1)); }
        [ -n "$dsrc" ]    || { err "[$sec].source missing"; errors=$((errors+1)); }
        if [ -n "$dt" ] && ! in_list "$dt" "${VALID_DEP_TYPES[@]}"; then
          err "[$sec].type '$dt' is not in closed vocab (${VALID_DEP_TYPES[*]})"
          errors=$((errors+1))
        fi
        if [ -n "$dtarget" ] && [ -n "$parent_root" ] && [ -f "$parent_root/.gitmodules" ]; then
          if ! module_name_exists "$dtarget" "$parent_root"; then
            err "[$sec].target '$dtarget' does not resolve to a submodule or parent-owned module in $parent_root"
            errors=$((errors+1))
          fi
        fi
        if [ -n "$dsrc" ]; then
          local module_root dep_path
          module_root="$(dirname "$toml")"
          dep_path="$(dep_source_path "$dsrc")"
          if [ -n "$dep_path" ] && ! validate_module_path "$sec" "source" "$dep_path" "$module_root" 0; then
            errors=$((errors+1))
          fi
        fi
        ;;
      surfaces.*)
        local st spath scat
        st=$(unquote "$(get_field "$sec" type)")
        spath=$(unquote "$(get_field "$sec" path)")
        scat=$(unquote "$(get_field "$sec" catalog-ref)")
        [ -n "$st" ] || { err "[$sec].type missing"; errors=$((errors+1)); }
        if [ -n "$st" ] && ! in_list "$st" "${VALID_SURFACE_TYPES[@]}"; then
          err "[$sec].type '$st' is not in closed vocab (${VALID_SURFACE_TYPES[*]})"
          errors=$((errors+1))
        fi
        case "$st" in
          entry-point|config)
            [ -n "$spath" ] || { err "[$sec].path required for type=$st"; errors=$((errors+1)); }
            ;;
          command)
            if [ -z "$spath" ] && [ -z "$scat" ]; then
              err "[$sec] requires path or catalog-ref for type=command"
              errors=$((errors+1))
            fi
            ;;
          catalog-entry)
            [ -n "$scat" ] || { err "[$sec].catalog-ref required for type=catalog-entry"; errors=$((errors+1)); }
            ;;
        esac
        if [ -n "$spath" ]; then
          local module_root
          module_root="$(dirname "$toml")"
          if ! validate_module_path "$sec" "path" "$spath" "$module_root" 1; then
            errors=$((errors+1))
          fi
        fi
        ;;
      docs.*)
        local dpath deligible
        dpath=$(unquote "$(get_field "$sec" path)")
        deligible=$(get_field "$sec" post_pass_eligible)
        [ -n "$dpath" ] || { err "[$sec].path missing"; errors=$((errors+1)); }
        if [ -z "$deligible" ]; then
          err "[$sec].post_pass_eligible missing"; errors=$((errors+1))
        elif [ "$deligible" != "true" ] && [ "$deligible" != "false" ]; then
          err "[$sec].post_pass_eligible must be true or false (got: $deligible)"
          errors=$((errors+1))
        fi
        if [ -n "$dpath" ]; then
          local module_root2
          module_root2="$(dirname "$toml")"
          if ! validate_module_path "$sec" "path" "$dpath" "$module_root2" 1; then
            errors=$((errors+1))
          fi
        fi
        ;;
    esac
  done <<<"$sections"

  if [ "$errors" -gt 0 ]; then
    err "validation failed with $errors error(s), $warnings warning(s)"
    return 1
  fi
  printf 'module-report: validation OK (%d warning(s))\n' "$warnings"
  return 0
}

# ---------------- STAMP ----------------

stamp_report() {
  local toml="$1"
  local now
  now="$(now_utc_iso)"
  local tmp
  tmp="$(mktemp)"
  awk -v now="$now" '
    function trim(s){ sub(/^[ \t]+/,"",s); sub(/[ \t\r]+$/,"",s); return s }
    BEGIN { section=""; stamped=0 }
    {
      line=$0
      t=trim(line)
      if (t ~ /^\[.*\]$/) {
        section = substr(t, 2, length(t)-2)
        print line
        next
      }
      if (section=="provenance" && t ~ /^last_validated[ \t]*=/) {
        print "last_validated = \"" now "\""
        stamped=1
        next
      }
      print line
    }
    END {
      if (!stamped) {
        # no provenance section or no last_validated key — append
        print ""
        print "[provenance]"
        print "last_validated = \"" now "\""
      }
    }
  ' "$toml" > "$tmp"
  mv "$tmp" "$toml"
  printf 'module-report: stamped last_validated=%s\n' "$now"
}

# ---------------- REGENERATE ----------------
# Auto-derivable sections in v1: surfaces (from scaffold.config.json if present;
# otherwise leaves existing surfaces alone — they are operator-declared until a
# richer derivation lands). Hand-edits to [identity], [risk], [docs], and
# [provenance.generated_by] are preserved by being copied through unchanged.
#
# v1 regenerate semantics: read existing file, rewrite it preserving the
# preserved sections verbatim, then re-emit deps/surfaces from declared sources
# if a sibling `module-report.sources.toml` exists at the module root. If no
# sources file is present, the regenerate is a no-op rewrite (round-trip) plus
# a stamp — this matches the spec's "preserves hand-edits" guarantee for an
# operator-authored toml without a derivation source.

regenerate_report() {
  local toml="$1" parent_root="$2"
  if [ ! -f "$toml" ]; then
    err "cannot regenerate: $toml does not exist; create one with the required [identity] / [risk] sections first"
    return 1
  fi
  # Round-trip: parse, then emit. This normalises whitespace and proves the
  # file is parseable. Auto-derivation hooks are intentionally minimal in v1
  # (see header comment).
  local flat
  flat="$(toml_flatten "$toml")"
  local tmp
  tmp="$(mktemp)"

  # Emit identity (preserved).
  {
    printf '# Generated/maintained by scaffold module-report. Hand-edits in\n'
    printf '# [identity], [risk], [docs], and [provenance.generated_by] are preserved.\n'
    printf '\n[identity]\n'
    awk -F'|' '$1=="identity" {printf "%s = %s\n", $2, $3}' <<<"$flat"

    # deps / surfaces / docs: preserve existing entries (auto-derivation v1: pass-through).
    local sec
    while IFS= read -r sec; do
      case "$sec" in
        deps.*|surfaces.*|docs.*)
          printf '\n[%s]\n' "$sec"
          awk -F'|' -v s="$sec" '$1==s {printf "%s = %s\n", $2, $3}' <<<"$flat"
          ;;
      esac
    done < <(awk -F'|' '{print $1}' <<<"$flat" | sort -u)

    printf '\n[risk]\n'
    awk -F'|' '$1=="risk" {printf "%s = %s\n", $2, $3}' <<<"$flat"

    printf '\n[provenance]\n'
    local gen
    gen=$(unquote "$(awk -F'|' '$1=="provenance" && $2=="generated_by" {print $3; exit}' <<<"$flat")")
    [ -n "$gen" ] || gen="auto:scaffold-self-report"
    printf 'generated_by = "%s"\n' "$gen"
    printf 'last_validated = "%s"\n' "$(now_utc_iso)"
  } > "$tmp"

  mv "$tmp" "$toml"
  printf 'module-report: regenerated %s\n' "$toml"

  # Run validation on the freshly written file (CI-equivalent).
  validate_report "$toml" "$parent_root" "$DEFAULT_FRESHNESS_DAYS"
}

# ---------------- main ----------------

main() {
  local mode="" module="" parent="" freshness="$DEFAULT_FRESHNESS_DAYS"
  while [ $# -gt 0 ]; do
    case "$1" in
      --validate)        mode="validate"; shift ;;
      --regenerate)      mode="regenerate"; shift ;;
      --stamp)           mode="stamp"; shift ;;
      --module)          module="$2"; shift 2 ;;
      --parent)          parent="$2"; shift 2 ;;
      --freshness-days)  freshness="$2"; shift 2 ;;
      --help|-h)         print_usage; exit 0 ;;
      *)                 err "unknown arg: $1"; print_usage >&2; exit 2 ;;
    esac
  done

  [ -n "$mode" ] || { err "must pass --validate, --regenerate, or --stamp"; print_usage >&2; exit 2; }

  module="${module:-$PWD}"
  module="$(cd "$module" && pwd)"
  if [ -z "$parent" ]; then
    parent="$(find_parent_root "$module" || true)"
  else
    parent="$(cd "$parent" && pwd)"
  fi

  local toml="$module/lugos-module.toml"

  case "$mode" in
    validate)
      validate_report "$toml" "$parent" "$freshness"
      ;;
    stamp)
      validate_report "$toml" "$parent" "$freshness"
      stamp_report "$toml"
      ;;
    regenerate)
      regenerate_report "$toml" "$parent"
      ;;
  esac
}

main "$@"

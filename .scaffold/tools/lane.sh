#!/usr/bin/env bash
# lane.sh — git "lanes" workflow tool.
# Usage: bash .scaffold/tools/lane.sh <subcommand> [args]
# See runtime/rules/git-lanes.md for the convention.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=lane-stignore-block.sh
source "$SCRIPT_DIR/lane-stignore-block.sh"

find_syncthing_root() {
  local dir="${1:-$PWD}"
  while [ "$dir" != "/" ] && [ "$dir" != "." ]; do
    if [ -d "$dir/.stfolder" ]; then
      echo "$dir"
      return 0
    fi
    dir="$(dirname "$dir")"
  done
  return 1
}

print_usage() {
  cat <<'EOF'
lane — git lanes workflow tool

Usage:
  lane new <slug> [--agent <name>]      Create & switch to lane/<slug> (or lane/<agent>/<slug>).
  lane list                              List lanes for this repo with age and merge status.
  lane done [--branch <full-name>]       Merge current (or specified) lane to trunk; delete it.
  lane prune                             Delete local lane branches gone or merged on origin.
  lane doctor                            Read-only diagnostic of current repo's lane hygiene.
  lane adopt                             Show the three-step phased retrofit flow.
  lane adopt harden                      Phase 3: append .stignore rules at Syncthing folder root.
  lane adopt cleanup [--assume-propagated]
                                         Phase 5: remove .worktrees/ and host-local dirs; gated.
  lane adopt rename                      Phase 6: interactive branch rename pass.
  lane --help                            This message.
EOF
}

print_adopt_flow() {
  cat <<'EOF'
`lane adopt` is phased for safety. Run in this order, with Syncthing-propagation between:

  1. lane adopt harden    (Phase 3 — edits .stignore only, non-destructive)

  2. Pause Syncthing on every host; resume Windows first; wait for .stignore
     to propagate everywhere. Verify on each host:  cat <sync-root>/.stignore

  3. lane adopt cleanup   (Phase 5 — deletes .worktrees/ and host-local dirs.
                           Requires propagation confirmation. Run once per host.)

  4. lane adopt rename    (Phase 6 — interactive renames of non-conforming branches)

Bare `lane adopt` prints this flow and exits without acting. Run each subcommand explicitly.
EOF
}

trunk_branch() {
  local configured origin_head
  if [ -n "${SCAFFOLD_TRUNK_BRANCH:-}" ]; then
    printf '%s\n' "$SCAFFOLD_TRUNK_BRANCH"
    return 0
  fi
  configured="$(git config --get scaffold.trunk 2>/dev/null || true)"
  if [ -n "$configured" ]; then
    printf '%s\n' "$configured"
    return 0
  fi
  origin_head="$(git symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null || true)"
  if [ -n "$origin_head" ]; then
    printf '%s\n' "${origin_head#origin/}"
    return 0
  fi
  if git show-ref --verify --quiet refs/heads/main \
     || git show-ref --verify --quiet refs/remotes/origin/main; then
    printf '%s\n' "main"
    return 0
  fi
  if git show-ref --verify --quiet refs/heads/master \
     || git show-ref --verify --quiet refs/remotes/origin/master; then
    printf '%s\n' "master"
    return 0
  fi
  printf '%s\n' "main"
}

branch_is_merged_to_trunk() {
  local branch="$1" trunk="$2"
  if git rev-parse --verify --quiet "$trunk^{commit}" >/dev/null \
     && git merge-base --is-ancestor "$branch" "$trunk" 2>/dev/null; then
    return 0
  fi
  if git rev-parse --verify --quiet "origin/$trunk^{commit}" >/dev/null \
     && git merge-base --is-ancestor "$branch" "origin/$trunk" 2>/dev/null; then
    return 0
  fi
  return 1
}

archive_branch() {
  local branch="$1" tag="archive/$branch"
  local target existing
  target="$(git rev-parse "$branch")"
  if git show-ref --verify --quiet "refs/tags/$tag"; then
    existing="$(git rev-parse "refs/tags/$tag")"
    if [ "$existing" = "$target" ]; then
      echo "lane prune: archive tag already exists for $branch"
      return 0
    fi
    echo "lane prune: archive tag $tag exists but points at a different commit; skipping $branch" >&2
    return 1
  fi
  git tag "$tag" "$branch"
  if git remote get-url origin >/dev/null 2>&1; then
    git push origin "refs/tags/$tag"
  fi
}

cmd_new() {
  local slug="" agent=""
  while [ $# -gt 0 ]; do
    case "$1" in
      --agent) agent="$2"; shift 2 ;;
      --) shift; break ;;
      -*) echo "lane new: unknown flag $1" >&2; return 2 ;;
      *) if [ -z "$slug" ]; then slug="$1"; shift; else echo "lane new: unexpected arg $1" >&2; return 2; fi ;;
    esac
  done

  if [ -z "$slug" ]; then
    echo "lane new: slug is required (usage: lane new <slug> [--agent <name>])" >&2
    return 2
  fi
  case "$slug" in
    */*) echo "lane new: slug must not contain a slash (use --agent for namespacing)" >&2; return 2 ;;
  esac

  local branch
  if [ -n "$agent" ]; then
    branch="lane/$agent/$slug"
  else
    branch="lane/$slug"
  fi

  if git show-ref --verify --quiet "refs/heads/$branch"; then
    echo "lane new: $branch already exists — switching to it" >&2
    git switch "$branch"
    return 0
  fi

  git switch -c "$branch"
  git push -u origin "$branch"
  echo "lane new: created and pushed $branch"
}
cmd_list() {
  local trunk
  trunk="$(trunk_branch)"
  local lanes
  lanes="$(git for-each-ref --format='%(refname:short)|%(committerdate:unix)|%(committerdate:relative)' refs/heads/lane/ 2>/dev/null || true)"
  if [ -z "$lanes" ]; then
    echo "No lanes in this repo."
    return 0
  fi

  # Compute merged lanes once.
  local merged=""
  if git rev-parse --verify --quiet "$trunk^{commit}" >/dev/null; then
    merged="$(git branch --merged "$trunk" --format='%(refname:short)' 2>/dev/null | grep '^lane/' || true)"
  elif git rev-parse --verify --quiet "origin/$trunk^{commit}" >/dev/null; then
    merged="$(git branch --merged "origin/$trunk" --format='%(refname:short)' 2>/dev/null | grep '^lane/' || true)"
  fi

  printf '%-40s  %-15s  %s\n' "BRANCH" "LAST COMMIT" "STATUS"
  local now; now="$(date +%s)"
  while IFS='|' read -r name ts relative; do
    [ -z "$name" ] && continue
    local age_days=$(( (now - ts) / 86400 ))
    local status=""
    if echo "$merged" | grep -qxF "$name"; then
      status="merged"
    elif [ "$age_days" -gt 14 ]; then
      status="stale (${age_days}d)"
    fi
    printf '%-40s  %-15s  %s\n' "$name" "$relative" "$status"
  done <<< "$lanes"
}
cmd_done() {
  local trunk
  trunk="$(trunk_branch)"
  local branch=""
  while [ $# -gt 0 ]; do
    case "$1" in
      --branch) branch="$2"; shift 2 ;;
      -*) echo "lane done: unknown flag $1" >&2; return 2 ;;
      *) echo "lane done: unexpected arg $1" >&2; return 2 ;;
    esac
  done
  if [ -z "$branch" ]; then
    branch="$(git rev-parse --abbrev-ref HEAD)"
  fi

  case "$branch" in
    lane/*) ;;
    *) echo "lane done: $branch is not a lane/* branch" >&2; return 2 ;;
  esac

  if [ -n "$(git status --porcelain)" ]; then
    echo "lane done: working tree is not clean — commit or stash first" >&2
    return 1
  fi

  echo "lane done: finishing $branch"

  git switch "$trunk"
  git pull --ff-only origin "$trunk" 2>/dev/null || true

  if git merge --ff-only "$branch" 2>/dev/null; then
    :
  else
    echo "lane done: $branch is not fast-forward into $trunk."
    read -r -p "Merge non-ff anyway (creates merge commit)? [y/N] " ans
    case "$ans" in
      [yY]|[yY][eE][sS])
        git merge --no-ff "$branch" -m "Merge $branch"
        ;;
      *)
        echo "lane done: aborted — resolve manually."
        return 1
        ;;
    esac
  fi

  git push origin "$trunk"
  git branch -D "$branch"
  git push origin ":$branch" 2>/dev/null || true
  echo "lane done: $branch merged and removed"
}
cmd_prune() {
  git fetch --prune --quiet origin

  local to_prune=()
  local line name trunk
  trunk="$(trunk_branch)"
  while IFS= read -r line; do
    name="${line##refs/heads/}"
    if [ "$name" = "$trunk" ]; then
      continue
    fi
    case "$name" in
      safety/*) continue ;;
      lane/*) ;;
      *) continue ;;
    esac
    # Merged into trunk?
    if branch_is_merged_to_trunk "$name" "$trunk"; then
      to_prune+=("$name|merged")
      continue
    fi
    # Origin tracking branch gone?
    if [ -z "$(git for-each-ref --format='%(upstream:short)' "refs/heads/$name")" ] \
       || ! git show-ref --verify --quiet "refs/remotes/$(git for-each-ref --format='%(upstream:short)' "refs/heads/$name")"; then
      to_prune+=("$name|gone")
    fi
  done < <(git for-each-ref --format='%(refname)' refs/heads/)

  if [ "${#to_prune[@]}" -eq 0 ]; then
    echo "lane prune: nothing to prune."
    return 0
  fi

  echo "Will delete:"
  local entry branch reason
  for entry in "${to_prune[@]}"; do
    IFS='|' read -r branch reason <<<"$entry"
    printf '  %s (%s)\n' "$branch" "$reason"
  done
  read -r -p "Proceed? [y/N] " ans
  case "$ans" in
    [yY]|[yY][eE][sS]) ;;
    *) echo "lane prune: aborted."; return 0 ;;
  esac

  for entry in "${to_prune[@]}"; do
    IFS='|' read -r branch reason <<<"$entry"
    if [ "$reason" = "gone" ]; then
      if ! archive_branch "$branch"; then
        echo "lane prune: skipped $branch because archive failed" >&2
        continue
      fi
    fi
    git branch -D "$branch" || true
  done
  echo "lane prune: done."
}
cmd_doctor() {
  local trunk
  trunk="$(trunk_branch)"
  local failed=0

  # 1. Repo has .git/
  if ! git rev-parse --git-dir >/dev/null 2>&1; then
    echo "FAIL: no git repo found (cwd=$PWD)"
    return 1
  fi

  # 2. .stignore check (if under a Syncthing folder root)
  local sync_root
  if sync_root="$(find_syncthing_root "$PWD")"; then
    echo "Syncthing folder root: $sync_root"
    local stignore="$sync_root/.stignore"
    if [ ! -f "$stignore" ]; then
      echo "FAIL: $stignore does not exist"
      failed=1
    else
      local missing=()
      local rule
      while IFS= read -r rule; do
        [ -z "$rule" ] && continue
        grep -qxF -- "$rule" "$stignore" || missing+=("$rule")
      done < <(stignore_rules_list)
      if [ "${#missing[@]}" -gt 0 ]; then
        echo "FAIL: $stignore missing rules:"
        printf '  %s\n' "${missing[@]}"
        failed=1
      fi
    fi
  else
    echo "INFO: no Syncthing folder root found above $PWD — skipping .stignore check"
  fi

  # 3. No .worktrees/ in repo root
  local repo_top
  repo_top="$(git rev-parse --show-toplevel)"
  if [ -d "$repo_top/.worktrees" ]; then
    echo "FAIL: $repo_top/.worktrees exists — must be removed (lane adopt cleanup)"
    failed=1
  fi

  # 4. Origin reachable
  if ! git remote show origin >/dev/null 2>&1; then
    echo "FAIL: origin is not configured or not reachable"
    failed=1
  fi

  # 5. Current branch matches convention
  local cur; cur="$(git rev-parse --abbrev-ref HEAD)"
  if [ "$cur" = "$trunk" ]; then
    :
  else
    case "$cur" in
      safety/*|lane/*) ;;
      *) echo "FAIL: current branch '$cur' does not match $trunk | safety/* | lane/*"; failed=1 ;;
    esac
  fi

  if [ "$failed" -eq 0 ]; then
    echo "OK: lane doctor passed."
  fi
  return "$failed"
}
cmd_adopt_harden() {
  local sync_root
  if ! sync_root="$(find_syncthing_root "$PWD")"; then
    echo "lane adopt harden: no .stfolder found walking up from $PWD — not a Syncthing folder root" >&2
    return 1
  fi
  local stignore="$sync_root/.stignore"
  touch "$stignore"

  local missing=() rule
  while IFS= read -r rule; do
    [ -z "$rule" ] && continue
    grep -qxF -- "$rule" "$stignore" || missing+=("$rule")
  done < <(stignore_rules_list)

  if [ "${#missing[@]}" -eq 0 ]; then
    echo "lane adopt harden: $stignore already contains all required rules."
  else
    {
      # Ensure there's a blank line separating prior content.
      [ -s "$stignore" ] && echo ""
      stignore_block
    } >> "$stignore"
    echo "lane adopt harden: appended ${#missing[@]} missing rule(s) to $stignore."
  fi

  cat <<'EOF'

Next steps (Phase 4 of migration — propagation):
  1. Pause Syncthing on every host.
  2. Resume Syncthing on THIS host first so the new .stignore propagates.
  3. Resume each other host one at a time; wait for idle between.
  4. Verify on each host: cat <sync-root>/.stignore contains the new rules.
  5. Then on each host, from a repo inside the sync root, run:
        lane adopt cleanup
     (or: bash .scaffold/tools/lane.sh adopt cleanup)
EOF
}
cmd_adopt_cleanup() {
  local assume_propagated=0
  while [ $# -gt 0 ]; do
    case "$1" in
      --assume-propagated) assume_propagated=1; shift ;;
      -*) echo "lane adopt cleanup: unknown flag $1" >&2; return 2 ;;
      *) echo "lane adopt cleanup: unexpected arg $1" >&2; return 2 ;;
    esac
  done

  local sync_root
  if ! sync_root="$(find_syncthing_root "$PWD")"; then
    echo "lane adopt cleanup: no Syncthing folder root above $PWD" >&2
    return 1
  fi
  local stignore="$sync_root/.stignore"
  if [ ! -f "$stignore" ]; then
    echo "lane adopt cleanup: $stignore does not exist — run 'lane adopt harden' first" >&2
    return 1
  fi
  local rule
  while IFS= read -r rule; do
    [ -z "$rule" ] && continue
    if ! grep -qxF -- "$rule" "$stignore"; then
      echo "lane adopt cleanup: $stignore missing rule: $rule — run 'lane adopt harden' first" >&2
      return 1
    fi
  done < <(stignore_rules_list)

  local repo_top
  repo_top="$(git rev-parse --show-toplevel 2>/dev/null)" || {
    echo "lane adopt cleanup: not inside a git repo" >&2
    return 1
  }

  # Find targets to remove: any .worktrees/ dirs in the repo, plus host-local env dirs at the repo top.
  local targets=()
  [ -d "$repo_top/.worktrees" ] && targets+=("$repo_top/.worktrees")
  # Additional host-local dirs that .stignore now ignores — candidates to sweep at repo top.
  local candidate
  for candidate in ".venv" "venv" "node_modules" ".vscode" ".idea" ".history" ".tmp-debug"; do
    [ -e "$repo_top/$candidate" ] && targets+=("$repo_top/$candidate")
  done
  # .venv-* and .tmp-debug* globs
  local g
  for g in "$repo_top"/.venv-* "$repo_top"/.tmp-debug*; do
    [ -e "$g" ] && targets+=("$g")
  done

  if [ "${#targets[@]}" -eq 0 ]; then
    echo "lane adopt cleanup: nothing to remove."
    return 0
  fi

  echo "About to delete:"
  printf '  %s\n' "${targets[@]}"
  echo ""
  echo "These deletions will NOT propagate via Syncthing because .stignore ignores them."
  echo "Confirm that the hardened .stignore has fully propagated to ALL other hosts."

  if [ "$assume_propagated" -ne 1 ]; then
    read -r -p "Type YES to proceed: " ans
    if [ "$ans" != "YES" ]; then
      echo "lane adopt cleanup: aborted."
      return 1
    fi
  fi

  local t
  for t in "${targets[@]}"; do
    rm -rf -- "$t"
  done
  echo "lane adopt cleanup: done."
}
cmd_adopt_rename() {
  local non_conforming=()
  local ref name trunk
  trunk="$(trunk_branch)"
  while IFS= read -r ref; do
    name="${ref##refs/heads/}"
    [ "$name" = "$trunk" ] && continue
    case "$name" in
      safety/*|lane/*) continue ;;
    esac
    non_conforming+=("$name")
  done < <(git for-each-ref --format='%(refname)' refs/heads/)

  if [ "${#non_conforming[@]}" -eq 0 ]; then
    echo "lane adopt rename: nothing to rename — all branches conform."
    return 0
  fi

  echo "Non-conforming branches:"
  printf '  %s\n' "${non_conforming[@]}"
  echo ""

  local old new
  for old in "${non_conforming[@]}"; do
    read -r -p "Rename '$old'? (y=prompt for new name / n=skip) " ans || true
    case "$ans" in
      [yY]|[yY][eE][sS]) ;;
      *) continue ;;
    esac
    read -r -p "  New name (must start with lane/): " new || true
    case "$new" in
      lane/*) ;;
      *) echo "  skipped: '$new' does not start with lane/"; continue ;;
    esac
    if git show-ref --verify --quiet "refs/heads/$new"; then
      echo "  skipped: '$new' already exists"
      continue
    fi
    git branch -m "$old" "$new"
    git push origin "$new"         2>/dev/null || true
    git push origin ":$old"        2>/dev/null || true
    echo "  renamed: $old -> $new"
  done
}

cmd="${1:-}"
if [ -z "$cmd" ]; then
  print_usage >&2
  exit 2
fi

case "$cmd" in
  -h|--help|help)
    print_usage; exit 0 ;;
  new)         shift; cmd_new "$@" ;;
  list)        shift; cmd_list "$@" ;;
  done)        shift; cmd_done "$@" ;;
  prune)       shift; cmd_prune "$@" ;;
  doctor)      shift; cmd_doctor "$@" ;;
  adopt)
    shift
    sub="${1:-}"
    case "$sub" in
      "")         print_adopt_flow; exit 0 ;;
      harden)     shift; cmd_adopt_harden "$@" ;;
      cleanup)    shift; cmd_adopt_cleanup "$@" ;;
      rename)     shift; cmd_adopt_rename "$@" ;;
      *)          echo "Unknown adopt subcommand: $sub" >&2; exit 2 ;;
    esac
    ;;
  *)
    echo "Unknown subcommand: $cmd" >&2
    print_usage >&2
    exit 2 ;;
esac

# Git Lanes — Convention

**Scope:** This rule applies to every repo that is scaffolded via `apply-scaffold.ps1` and to every repo under a Syncthing-synced directory managed by this user. Agents working in a scaffolded repo must follow this convention.

## Primitives

- **Trunk:** the repo default branch. `lane.sh` resolves it from `SCAFFOLD_TRUNK_BRANCH`,
  then `git config scaffold.trunk`, then `origin/HEAD`, and falls back to `main`.
- **Lane:** a branch named `lane/<slug>` (or `lane/<agent>/<slug>`). One lane = one intent.
- **Safety snapshot:** `safety/YYYY-MM-DD-<topic>` — preserved as-is, never pruned by tooling.
- **No other prefixes.** Do not create `feature/`, `fix/`, `chore/`, `wip/` branches. If found, run `lane adopt rename`.

## What must NOT be in the synced tree

- `.git/` — enforced by root `.stignore` rule `(?d)**/.git`.
- `.worktrees/` — enforced by `(?d)**/.worktrees`.
- Per-host environments: `.venv`, `venv`, `.venv-*`, `node_modules`.
- IDE state: `.vscode`, `.idea`, `.history`.
- Scratch/debug: `.tmp-debug*`.

## Where worktrees may live (if needed)

Rarely needed — use branch switching by default. When a true parallel checkout is genuinely required on one host, place it at `~/work/wt/<repo>/<lane>` — outside the Syncthing-synced tree. Never inside a synced project directory.

## Cross-host continuity

GitHub is the source of truth. `git push` on host A; `git fetch && git switch lane/<slug>` on host B. Do not rely on Syncthing to transport git state.

## Tooling

Lane operations are scripted; see `runtime/skills/lane-workflow.md` for procedural guidance and `runtime/tools/lane.sh` for the implementation. Subcommands:

- `lane new <slug> [--agent <name>]`
- `lane list`
- `lane done [--branch <full-name>]`
- `lane prune`
- `lane doctor`
- `lane adopt harden` / `cleanup` / `rename` (phased retrofit)

## `.stignore` block

The single source of truth is `runtime/tools/lane-stignore-block.sh` (function `stignore_block`). The block, as a reference:

```
// Git internals and operational state — never sync
(?d)**/.git
(?d)**/.worktrees

// Per-host environments
(?d)**/.venv
(?d)**/venv
(?d)**/.venv-*
(?d)**/node_modules

// IDE / editor state
(?d)**/.vscode
(?d)**/.idea
(?d)**/.history

// Scratch/debug dirs
(?d)**/.tmp-debug*
```

Nested `.stignore` files are ignored by Syncthing — only the folder-root file matters.

## Red flags for agents

- Creating `.worktrees/<name>/` inside the repo — always wrong; use a branch or an out-of-sync worktree under `~/work/`.
- Committing `.venv`, `node_modules`, or other host-local env state.
- Naming a branch anything other than the resolved trunk / `safety/*` / `lane/*`.
- Running `lane adopt cleanup` before `lane adopt harden` has propagated.

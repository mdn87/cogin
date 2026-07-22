# Lane Workflow — Procedural Skill

**When to use:** Any time you're starting, merging, or cleaning up work in a scaffolded repo. Also whenever you need to retrofit a non-scaffolded repo into the lanes convention.

**Reference rule:** `.scaffold/rules/git-lanes.md`.

## Starting work

1. `bash .scaffold/tools/lane.sh doctor` — verify the repo is hygienic.
2. Decide on a slug (one intent, kebab-case). If this is agent work, include `--agent <name>`.
3. `bash .scaffold/tools/lane.sh new <slug> [--agent <name>]` — creates, switches, pushes.
4. Work. Commit. Push often.

## Resuming on another host

1. `git fetch`
2. `git switch lane/<slug>` (or `lane/<agent>/<slug>`)
3. Continue. Push when done.

## Finishing a lane

1. `git status` — must be clean. Commit or stash WIP first.
2. `bash .scaffold/tools/lane.sh done` — merges to the resolved trunk ff-only; prompts if non-ff. Pushes trunk and deletes the branch locally and on origin.

## Periodic cleanup

1. `bash .scaffold/tools/lane.sh list` — review lanes; spot stale ones.
2. `bash .scaffold/tools/lane.sh prune` — removes local lanes whose origin is gone or already merged.

## Retrofitting an unmanaged repo

This is the **phased** migration. Do **not** skip steps or reorder.

### Phase 3 — harden .stignore

On the host with the live `.git/` (or wherever you start):
```
bash .scaffold/tools/lane.sh adopt harden
```
This edits the Syncthing folder root's `.stignore`. It does **not** delete anything.

### Phase 4 — propagate (manual)

1. Pause Syncthing on every host.
2. Resume on the host that ran `harden` first. Wait for idle.
3. Resume each other host one at a time. Wait for idle between each.
4. Verify on each host: `cat <sync-root>/.stignore` contains the new rules.

### Phase 5 — cleanup (per host, local)

On each host, inside the repo:
```
bash .scaffold/tools/lane.sh adopt cleanup
```
Prompts for the literal string `YES` unless `--assume-propagated` is passed. Refuses if the `.stignore` isn't hardened. Removes `.worktrees/`, `.venv*`, `.tmp-debug*`, IDE dirs.

### Phase 6 — rename lanes

```
bash .scaffold/tools/lane.sh adopt rename
```
Interactive. Lists non-conforming branches; for each, prompts to rename to `lane/...` or skip.

### Verify

```
bash .scaffold/tools/lane.sh doctor
```
Must print `OK: lane doctor passed.` on every host.

## Troubleshooting

- **`lane doctor` says .stignore missing rules:** run `lane adopt harden`, then follow Phase 4 propagation.
- **`lane new` fails with "fatal: --set-upstream":** origin branch already exists; run `git fetch && git switch lane/<slug>` instead.
- **`lane done` prompts non-ff:** trunk has advanced. Rebase your lane onto the resolved trunk, or answer `y` to create a merge commit.
- **Two agents created the same slug under different namespaces:** that's fine — `lane/codex/foo` and `lane/claude/foo` are distinct. Use `--branch <full-name>` with `lane done`.

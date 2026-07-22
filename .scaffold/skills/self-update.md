# Self-Update Skill

> Last updated: 2026-03-23

## Purpose

Check the upstream scaffold repo for updates on every session start. Keeps orchestration, skills, tools, references, and rules in sync across all projects.

## When to Run

- **Every session start**, before any other work
- After the handoff skill reads session state

## Instructions for Agent

On session start, perform these steps:

1. Check if `.scaffold/upstream.json` exists. If not, skip — this project is not scaffold-managed.

2. Run the sync script:
   ```bash
   bash .scaffold/sync.sh
   ```
   Use `bash .scaffold/sync.sh --dry-run` when you need a read-only change summary.

3. Read the output:
   - "Up to date" → proceed normally
   - "Updated: N files changed" → note the changed files, they may affect current work
   - "WARNING: Could not reach upstream" → log the warning, proceed with local copy
   - "ERROR: upstream ... is not allowed" → do not change `upstream.json`; surface the mismatch

4. If orchestration files changed, re-read any milestone files relevant to current work.

## Failure Handling

If sync fails, **do not block the session**. Log a warning and continue. The local copy is always functional — sync just keeps it current.

- Exit code 0: sync completed (whether updated or already current)
- Non-zero exit code: sync encountered an error — log the exit code and continue with local copy
- "ERROR" in output: a required dependency is missing (python3 or node) — note for the user but do not block

## upstream.json Format

```json
{
  "repo_url": "git@github.com:{owner}/scaffold.git",
  "branch": "main",
  "allowed_repo_url": "git@github.com:{owner}/scaffold.git",
  "allowed_branch": "main",
  "last_synced_commit": "{commit_hash}",
  "last_synced_date": "{ISO 8601 timestamp}"
}
```

`sync.sh` rejects `repo_url` or `branch` changes unless they match the allowlist fields
or an explicit operator override in `SCAFFOLD_ALLOWED_UPSTREAM_REPO` /
`SCAFFOLD_ALLOWED_UPSTREAM_BRANCH`.

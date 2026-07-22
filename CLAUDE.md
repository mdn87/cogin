# cogin

## Project

- **Type**: Python project
- **Stack**: python
- **Root**: `C:\Users\Matt\Desktop\MyDocs\cogin`

## Purpose

Taxonomy Bench converts the [Marble Skill Taxonomy](https://github.com/withmarbleapp/os-taxonomy) into a deterministic, progressively difficult AI benchmark. It tests how far a model gets, how quickly it gets there, and how much it improves when allowed to retry.

## Key Commands

- None detected

## Workflow Notes

- **Base session strength** - what the model gets exactly right on its first attempt.
- **Recovery strength** - which first-attempt failures it fixes with blind or diagnostic retries.
- `base_strength_0_100`: difficulty-weighted exact correctness on first attempts
- `eventual_strength_0_100`: the same score after allowed retries
- `reliable_frontier_first`: highest consecutive tier with at least two-thirds exact passes
- `retry_lift_points`: eventual minus first-attempt weighted score
- `retry_recovery_rate`: fraction of retried first-attempt failures corrected
- All eight task tiers were generated and exactly scored with an oracle provider.

## Operating Rules

- Use the Read tool to read files — do not use `cat` or `head` via Bash.
- Search with Grep and Glob tools, not `grep` or `find` via Bash.
- Use the Edit tool for targeted changes; Write only for new files or full rewrites.
- Prefer small, reviewable changes over large rewrites.
- Match existing path, naming, and runtime conventions.
- Treat README.md, plan files, and architecture docs as authoritative project context.
- Do not add features, comments, or error handling beyond what was asked.

## Permissions

Safe auto-run commands are configured in `.claude/settings.json`. Normal project-scoped execution may autorun for listed non-destructive commands, including trusted Git, GitHub CLI, and repo script operations. Destructive commands remain explicitly denied.

## Git Safe Order

- If work spans submodules or nested repos, commit and push each child repo first, then commit and push the parent repo last so parent references never point at unpushed commits.

---
trigger: always_on
---

# cogin Agent Rules

## Project Context

- **Type**: Python project
- **Root**: `C:\Users\Matt\Desktop\MyDocs\cogin`
- **Primary language**: Python
- **Derivation mode**: project-docs

## Purpose

Taxonomy Bench converts the [Marble Skill Taxonomy](https://github.com/withmarbleapp/os-taxonomy) into a deterministic, progressively difficult AI benchmark. It tests how far a model gets, how quickly it gets there, and how much it improves when allowed to retry.

## Rule Source

This rule set was derived from existing project markdown plus detected manifests and structure.

## Source Docs

- src\taxonomy-bench\README.md
- src\taxonomy-bench\BENCHMARK_SPEC.md
- docs\concept-doc.md
- src\taxonomy-bench\NOTICE.md
- src\taxonomy-bench\VALIDATION.md

## Code Inference Sources

- src\taxonomy-bench\sample_data\dependencies.json
- src\taxonomy-bench\sample_data\manifest.json
- src\taxonomy-bench\sample_data\topics.json
- src\taxonomy-bench\taxonomy_bench.py
- src\taxonomy-bench\tests\test_taxonomy_bench.py

## Local Git Signals

- GitHub remote configured locally
- Repository name: cogin
- Remote: https://github.com/mdn87/cogin.git

## Remote GitHub Signals

- None detected

## Detected Stack Hints

- python

## Detected Manifests

- pyproject.toml

## Workflow Hints

- **Base session strength** - what the model gets exactly right on its first attempt.
- **Recovery strength** - which first-attempt failures it fixes with blind or diagnostic retries.
- `base_strength_0_100`: difficulty-weighted exact correctness on first attempts
- `eventual_strength_0_100`: the same score after allowed retries
- `reliable_frontier_first`: highest consecutive tier with at least two-thirds exact passes
- `retry_lift_points`: eventual minus first-attempt weighted score
- `retry_recovery_rate`: fraction of retried first-attempt failures corrected
- All eight task tiers were generated and exactly scored with an oracle provider.

## External Systems / Runtime Notes

- API or routed interface surface
- Packaged artifact generation/import workflow
- UNC path / file share dependency

## Safe Auto-Run Whitelist

Set safe autorun for the following commands when they match the current workspace and request:

- bash
- brew info
- brew list
- cat
- curl
- echo
- env
- Get-ChildItem
- Get-Content
- gh auth
- gh issue
- gh pr
- gh repo
- git add
- git branch
- git clone
- git commit
- git config
- git diff
- git fetch
- git init
- git log --oneline
- git ls-tree
- git merge
- git pull
- git push
- git rebase --continue
- git remote
- git restore --staged
- git status
- git submodule
- git switch
- git worktree
- ls
- ls -la
- pwsh -File scripts/apply-scaffold.ps1
- pwsh -File scripts/generate-architecture-context.ps1
- pwsh -File scripts/generate-migration-map.ps1
- python -m pip list
- python -m pytest
- Select-String
- sh
- which

Non-destructive project-scoped execution may autorun when it matches the allowlist above. Destructive commands remain excluded even when related command families are otherwise allowed.

## Operating Defaults

- Prefer small, reviewable changes.
- Preserve project-owned rules and conventions before applying scaffold defaults.
- Match existing path and runtime conventions instead of forcing a new layout mid-change.
- Treat project docs such as README.md, plan files, and architecture notes as authoritative inputs for future updates to .agents.
- If docs are missing, use entry points, filenames, comments, and local Git metadata as fallback signals before defaulting to generic rules.
- Remote GitHub enrichment is best-effort only and must never block scaffold application.

## Git Safe Order

- Prefer the main checkout for routine changes; use git worktrees only when there is a specific isolation or parallel-edit reason.
- If work spans submodules or nested repos, commit and push each child repo first, then commit and push the parent repo last so parent references never point at unpushed commits.

## Quota / Compute Rules

### Default: LOW COMPUTE

- Only analyze the minimum necessary code.
- Avoid workspace-wide scans unless the user explicitly asks for deeper analysis.
- Reuse existing reports and context before re-reading large files.

### HIGH COMPUTE triggers (ask first)

Respond with: "Estimated quota impact: HIGH. Proceed? (yes/no)" before:
- Reading many files
- Generating multi-phase plans
- Deep debugging across multiple modules
- Running workspace-wide searches

### ULTRA COMPUTE triggers (ask first)

Respond with: "Estimated quota impact: EXTREMELY HIGH. Ultra compute mode. Proceed? (yes/no)" before:
- Full codebase analysis
- Large refactors across multiple files
- Architectural redesign

## API Host Rule

Remember to restart the API host or local dev server if route, handler, or API-facing changes need to be reflected live.

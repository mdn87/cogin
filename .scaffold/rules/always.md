# Universal Rules

These rules apply to every scaffold-managed project regardless of stack or platform.

## Operating Principles

- Read and understand existing code before suggesting modifications
- Prefer small, reviewable changes over large rewrites
- Match existing path, naming, and runtime conventions
- Do not add features, comments, or error handling beyond what was asked
- Documentation updates are a completion requirement for every milestone

## Scaffold Awareness

- `.scaffold/` contains upstream-managed orchestration, skills, tools, references, and rules
- `.scaffold/project/` contains project-specific overrides — never modify upstream-owned paths for local customizations
- Check `.scaffold/upstream.json` for sync status on session start
- Read `.scaffold/tools/manifest.json` before each milestone to review available tools

## Session Lifecycle

- On session start: run self-update check, read handoff state
- On session end: refresh documentation for completed/identified tasks, then write handoff state with a documentation update notice
- Before implementation: review tool manifest, confirm milestone scope
- After implementation: update documentation, run tool audit

## Compute Budget

- **LOW (default):** Read only files necessary for the task. Reuse loaded context.
- **HIGH:** Confirm before reading many files or running broad searches. Say: "Estimated quota impact: HIGH. Proceed?"
- **ULTRA:** Confirm before full codebase analysis or large refactors. Say: "Estimated quota impact: EXTREMELY HIGH. Ultra compute mode. Proceed?"

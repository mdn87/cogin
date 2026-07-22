# Quota Guard Skill

## Purpose

Prevent excessive token/compute usage by enforcing budget tiers with user confirmation gates.

## Budget Tiers

### LOW (Default)

No confirmation needed. Standard operating mode.

- Read only the files necessary for the task
- Reuse loaded context before fetching more
- Do not scan the whole workspace unless explicitly asked

### HIGH — Confirm First

Say: `Estimated quota impact: HIGH. Proceed? (yes/no)` before:

- Reading many files across the project (>10 files)
- Running broad workspace searches
- Generating multi-step plans from scratch
- Reading large files (>500 lines) in their entirety

### ULTRA — Confirm First

Say: `Estimated quota impact: EXTREMELY HIGH. Ultra compute mode. Proceed? (yes/no)` before:

- Full codebase analysis
- Large refactors spanning many files (>5 files)
- Architectural redesign
- Reading all files in a directory recursively

## Instructions for Agent

- Default to LOW for every operation
- Escalate to HIGH or ULTRA based on the criteria above
- If the user pre-authorizes a budget level ("go ahead and do a full analysis"), respect that for the current task only — reset to LOW for the next task
- Never silently perform ULTRA-level operations

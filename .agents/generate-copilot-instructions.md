---
trigger: always_on
---

# GitHub Copilot Instructions Generation

When applying scaffold to a project, generate .github/copilot-instructions.md if it does not already exist.

## What to Include

Synthesize content from AGENTS.md and CLAUDE.md (or equivalent project context files) into a single file in Copilot's native format:

- **Project table** — active directories and what they contain
- **Skip lists** — directories and file types to ignore
- **Operating rules** — always-ask-before guardrails and safe auto-run defaults
- **Per-project quick-reference** — install, run, and architecture summary

## Rules

- Create .github/ if it does not exist.
- Never overwrite an existing .github/copilot-instructions.md without user confirmation.
- Keep the file concise — Copilot reads it on every request; avoid redundant or verbose sections.
- Mirror the same guardrails from .agents/always-approve-whitelisted-commands.md and quota-drain-prevention.md so all agents share consistent operating boundaries.

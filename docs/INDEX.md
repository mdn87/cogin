# Documentation Index — Cogin

## Metadata
- **Last Updated:** 2026-10-28

## Documents

| File | Purpose | Status | Last Updated |
|------|---------|--------|-------------|
| project-brief.md | Project concept and goals | Draft | 2026-07-21 |
| architecture.md | System boundaries and decisions | Draft | 2026-07-21 |
| NEXT-STEPS.md | Subscription CLI Wave 1 implementation ledger | Complete | 2026-08-02 |
| decisions/ | Architecture Decision Records | — | — |
| runplans/README.md | Subscription CLI experiment runplan index | Executable | 2026-08-02 |
| runplans/OPERATOR-PROMPT.md | Reusable top-level run operator prompt | Pair 1 calibrated; primary repeats next | 2026-10-22 |
| superpowers/specs/2026-07-25-subscription-cli-benchmark-design.md | Wave 1 experiment design | Ready for review | 2026-07-25 |
| evidence/wave-1-cli-characterization.md | Claude Code and Codex CLI output characterization | Evidence | 2026-08-01 |
| evidence/agy-cli-characterization.md | Antigravity CLI (`agy`) characterization for the Google lanes | Evidence | 2026-10-22 |
| [evidence/google-lanes-2026-10-23.md](evidence/google-lanes-2026-10-23.md) | Completed Google lanes and verified pair report | Complete | 2026-10-23 |
| plans/agent-cli-comparison-harness.md | Agentic repo-work comparison across Claude, Codex, and agy | Implemented | 2026-10-24 |

## Plans

| File | Status |
|------|--------|
| superpowers/plans/2026-08-02-wave-1-completion.md | Complete |

## Experiment Runplans

| Pair | Claude | Codex |
|------|--------|-------|
| 1 | [Claude Opus 5](./runplans/claude-opus-5.md) | [GPT-5.6 Sol](./runplans/codex-gpt-5.6-sol.md) |
| 2 | [Claude Sonnet 5](./runplans/claude-sonnet-5.md) | [GPT-5.6 Terra](./runplans/codex-gpt-5.6-terra.md) |
| 3 | [Claude Fable 5](./runplans/claude-fable-5.md) | [GPT-5.6 Luna](./runplans/codex-gpt-5.6-luna.md) |

The separate Google lane set (`wave prepare --lanes google-1`) runs
`gemini-4-argon-medium` and `gemini-3.8-flash-medium` through agy under the same
protocol and suite; see the Wave section of `src/taxonomy-bench/README.md`.

## Reviews

No milestone reviews are filed in this repository.


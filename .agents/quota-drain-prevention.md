---
trigger: always_on
---

# Quota Protection Rules

## Default Operating Mode: LOW COMPUTE

- Analyze only the minimum code needed for the task.
- Prefer incremental implementation over broad planning.
- Do not repeat large scans or re-read unchanged files without a reason.
- Reuse project docs and generated context before widening scope.

## HIGH COMPUTE MODE

Ask first with: "Estimated quota impact: HIGH. Proceed? (yes/no)"

Use this before:
- Reading many files
- Running broad searches
- Producing multi-step architecture plans
- Deep debugging across several modules

## ULTRA COMPUTE MODE

Ask first with: "Estimated quota impact: EXTREMELY HIGH. Ultra compute mode. Proceed? (yes/no)"

Use this before:
- Full repo analysis
- Large refactors
- Architectural redesign

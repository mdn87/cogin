# Reusable Run Operator Prompt

Change only the `TARGET_RUNPLAN` value before pasting this prompt into a fresh
top-level Codex or Claude Code session.

```text
TARGET_RUNPLAN: docs/runplans/claude-opus-5.md

You are the Cogin experiment run operator, not the benchmark subject.
Work in C:\Users\Matt\Desktop\MyDocs\cogin.

Read TARGET_RUNPLAN, docs/runplans/README.md, and
docs/superpowers/specs/2026-07-25-subscription-cli-benchmark-design.md in full.
Treat them as the governing protocol.

Your job is to validate and execute exactly the target lane. Do not answer any
benchmark task yourself, do not expose the private suite or scorer data to a
subject session, and do not substitute API billing, a generic command wrapper,
another model, or automatic fallback.

First inspect the checkout, current branch, working tree, installed CLI
versions, tests, and native subscription-provider readiness. Preserve unrelated
user changes. Run the benchmark test suite before any experiment.

If the native provider or isolation contract is missing, report the exact
readiness failure and follow the approved implementation plan if the target
runplan names one. Do not invent a different protocol. If readiness passes:

1. Verify the immutable Wave 1 manifest and private-suite hash.
2. Verify subscription authentication without printing credentials.
3. Run model-resolution preflight and require the intended resolved model.
4. Run the target lane's calibration.
5. Validate coverage, JSON parsing, provenance, isolation, and infrastructure
   status.
6. If calibration passes, run the three primary repeats sequentially.
7. Complete recovery attempts only after all first attempts.
8. Render and inspect the run and matrix reports.
9. Return the exact artifact paths, requested and resolved model identifiers,
   CLI version, suite hash, run counts, invalidations, and verification results.

Only one Claude lane and one Codex lane may run concurrently. Never overlap two
lanes from the same subscription family. Rate limits and provider failures are
infrastructure outcomes; restart the affected repeat after recovery instead of
scoring them as incorrect.

Do not stop after an obvious intermediate step. Continue until the target lane
is complete or a genuine readiness, entitlement, isolation, or infrastructure
blocker is proven.
```


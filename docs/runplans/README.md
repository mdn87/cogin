# Subscription CLI Runplans

These runplans define Wave 1 of Cogin's subscription-backed Taxonomy Bench
study.

## Pair Schedule

| Pair | Claude lane | Codex lane | Run concurrently |
|---|---|---|---|
| 1 | [Claude Opus 5](./claude-opus-5.md) | [GPT-5.6 Sol](./codex-gpt-5.6-sol.md) | Yes |
| 2 | [Claude Sonnet 5](./claude-sonnet-5.md) | [GPT-5.6 Terra](./codex-gpt-5.6-terra.md) | Yes |
| 3 | [Claude Fable 5](./claude-fable-5.md) | [GPT-5.6 Luna](./codex-gpt-5.6-luna.md) | Yes |

Do not overlap two Claude lanes or two Codex lanes. Each family shares a
subscription usage pool. Finish both lanes and the pair report before starting
the next pair.

## Shared Condition

All six lanes use:

- one locked Wave 1 manifest and full private-suite SHA-256;
- seed 42;
- medium reasoning effort;
- isolated subject sessions;
- prompt-mode JSON;
- no subject tools, web access, plugins, MCP servers, or project instructions;
- zero transport retries;
- a calibration run using the first two task IDs in ascending lexical order
  from each of tiers 1-4 in the full suite, with those eight IDs recorded in the
  manifest and no cognitive retries;
- three full 32-task repeats;
- up to two diagnostic, continued-context cognitive retries for each
  first-attempt failure, stopping after exact success.

Within each independent primary repeat, all 32 first attempts complete before
recovery attempts for that repeat begin. Recovery for one repeat finishes
before the next repeat starts.

## Operator And Subject Roles

The CLI session receiving the reusable prompt is the **operator**. It may read
the repository, private suite, and scorer because it coordinates the run.

The benchmark **subject** is a fresh subscription-backed CLI session launched
by Cogin for an attempt. It receives only the current public prompt and response
shape. The operator must not answer tasks, reveal scorer feedback beyond the
configured retry diagnostic, or put the private suite in the subject's
workspace.

## Required Readiness

Do not begin a lane until native `claude-cli` and `codex-cli` providers satisfy
the readiness gate in the
[design specification](../superpowers/specs/2026-07-25-subscription-cli-benchmark-design.md).
The current generic command provider is not an acceptable substitute.
The native adapters and the controller capabilities described below are both
still implementation work.

Before the first lane, the controller creates an immutable Wave 1 manifest
containing the full-suite hash, fixed calibration task IDs, task counts, retry
condition, CLI versions, protocol version, and hashes of the base instructions,
tool policy, invocation configuration, and diagnostic-feedback policy. Every
lane verifies that manifest rather than regenerating its own suite.

The controller also owns a cross-process subscription-family lock, per-repeat
phase checkpoints, whole-repeat restart after infrastructure interruption, and
lane-completion records. Lane operators render lane reports only. After both
lanes in a pair complete, one Wave 1 coordinator renders the pair report.

Calibration passes only when all eight durable attempts are scored, model
resolution and manifest values match, latencies are present and nonnegative,
and there are no infrastructure, isolation, parser-process, or report failures.
Malformed subject JSON remains a scored model outcome; it is not a calibration
failure by itself.

## Invalidation Rules

Stop and mark the lane invalid when:

- the resolved model does not match the target lane;
- the CLI switches or falls back to another model;
- a subject can access the private suite;
- tools or external context are available to a subject;
- the protocol manifest or suite hash changes;
- an operator answers a task;
- a CLI version changes between repeats in the same lane.

Authentication, entitlement, rate-limit, provider, timeout, and process
failures are infrastructure outcomes. Restart an interrupted repeat after
capacity recovers; never score it as a wrong answer.

## Reusable Prompt

Copy [OPERATOR-PROMPT.md](./OPERATOR-PROMPT.md) into a fresh top-level CLI
session and change only its `TARGET_RUNPLAN` line.

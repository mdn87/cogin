# Human effort tooling qualification — 2026-10-24

The measurement tools are implemented. Six accepted unattended v2 patches are
prepared for blind human review. **No actual human cleanup scores or supervised
task trials have been collected.** Those fields remain null, not zero.

The [machine-readable evidence](human-effort-tooling-2026-10-24.json) records
binary and artifact hashes. Private raw captures remain under
`src/agent-cli-harness/runs/`; credentials, session identifiers, and absolute
local paths are excluded from this export.

| Interface | Observed qualification | Human interruptions |
|---|---|---|
| Claude Code 2.1.296 | One file-write permission request; stdio host denied it; no patch produced | Unmeasured |
| Codex 0.164.0 app-server | One explicit escalation request; host sent the offered cancel decision; no command executed or patch produced | Unmeasured |
| agy 1.4.7 print mode | request-review auto-denied the write; headless mode reported that it cannot prompt | Unmeasured; unsupported interface |

These probes use a different task from the comparison and automated denials.
They qualify request/response transport only. They are not human observations,
completion-time samples, or evidence that one CLI is better.

## Delivered behavior

- Blind packages contain the common pinned task/base and randomly labeled
  patches. Lane metadata stays in a separate controller directory.
- Score import requires one named human, a blind attestation, every case exactly
  once, integer bounds, and reasons. Changed artifacts, missing/duplicate cases,
  incomplete reviews, and repeated imports are rejected. Original reports and
  trial records are unchanged.
- Supervised capture requires a named human at an interactive terminal. It
  records requests and explicit allow-once/deny decisions, preserves raw streams,
  archives the patch, and invokes fresh unit/Chromium acceptance separately.
  No persistent grants or automatic approvals are sent.
- A complete human capture with no prompts can report zero. Interrupted
  transport, unresolved requests, qualification runs, and absent reviews stay
  unmeasured. A human-denied task can have measured interruptions while failing
  task acceptance.
- Derived reports verify hashes and native request/ledger correspondence.
  Supervised sessions remain separate from unattended timing and repeatability.

## Interface findings

Claude's installed CLI accepts `manual` and reports it as `default`. The first
probe used a harmless Python print that did not prompt, so it did not qualify
the channel. With an empty setting-source list and a file-write probe, the CLI
emitted a real `can_use_tool` request and respected the deny response.

Codex's generated schema advertises `untrusted`, but the runtime rejects it.
The adapter uses `on-request`, reviewer `user`, and `workspace-write`, checking
the effective policy/model before the turn. Its command request offered `accept`
and `cancel`, without `decline`; the first host attempt stopped without granting
anything. The corrected adapter uses the offered negative decision. All earlier
probes are retained. The native schema and [official app-server protocol](https://learn.chatgpt.com/docs/app-server)
define the request/response boundary; installed runtime observations determine
which options this pinned binary actually accepts.

agy emitted only init, step-update, and result events. Its stderr explicitly
said headless mode could not prompt for `write_file` and auto-denied it. The
supervised launcher therefore rejects agy before launch. A supported interactive
approval channel is the missing dependency; bypassing permissions would not
measure human interruptions.

## Validation and limits

53 harness tests pass. Coverage includes anonymous package export/import,
immutable source evidence, score rejection cases, zero versus null, bidirectional
protocol fixtures, request IDs, allow-once and deny responses, unknown-request
stops, credential isolation, and report artifact checks. Real deny-only probes
qualified Claude/Codex; agy's auto-denial was reproduced without any file change.
Native allow-once handling is covered by local protocol tests, not a live human
approval. Full supervised task sessions still require a human operator.
An additional smoke check replayed an archived accepted patch through a
synthetic protocol boundary and the normal capture path: unit/Chromium checks,
task scoring, recovery bundle, and worktree cleanup passed. Its mode is explicitly
`test-fixture`, with no human score; it is excluded from measurement reports.

The prepared reviewer directory contains six patches and no identity mapping.
Code style may suggest an author, so reviewers must attest that they do not know
which lane produced the patches. The [operator guide](../../src/agent-cli-harness/HUMAN_REVIEW.md)
contains the tested commands and rubric. Existing v1/v2 comparison evidence is
preserved; this tooling does not justify a model ranking or migration.

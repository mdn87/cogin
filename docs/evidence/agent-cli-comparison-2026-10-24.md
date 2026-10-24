# Agent CLI comparison: 2026-10-24

The pinning fix and unattended harness are implemented. Claude and Codex each have two protocol-valid trials and pass the declared repeatability gate. The three-lane batch remains incomplete: agy requested `git log -p -2`, which its approved rules denied. A separate approval for fixture Git history inspection is pending; no bypass or further agy run was attempted.

## Pinned conditions

The controller invokes native executables by absolute path and verifies their SHA-256 and version before and after each trial. It avoids the PATH shadow selecting Clici Codex 0.162.1. All lanes use the same frozen task-board seed, prompt, medium effort, and subscription login. Global settings and PATH were not changed.

| CLI | Version | Requested model |
|---|---|---|
| claude | 2.1.296 (Claude Code) | `claude-sonnet-5` |
| codex | codex-cli 0.164.0 | `gpt-6.1-sol` |
| agy | 1.4.7 | `gemini-3.8-flash-medium` |

Seed commit: `ffb5bb0a74367996b8e44a19ce1a3152820ae5a2`. Prompt SHA-256: `bd97b97c1595766ba82f01b7e59926d4d01069f12cba4742caca734579a94fdf`.

Full binary hashes, fixture hashes, source manifests, raw-artifact hashes and per-trial scores are in the [machine-readable evidence](agent-cli-comparison-2026-10-24.json). Raw conversations, authentication metadata, absolute executable paths and screenshots stay in ignored local artifacts under `src/agent-cli-harness/runs/`.

## Observed trials

| Source / trial | Protocol valid | Task complete | Seconds | Assistant events | Fresh tests / browser | Off-target lines |
|---|---|---|---:|---:|---|---:|
| batch-5 / agy-1 | False | False | 35.548 | 5 | True / False | 0 |
| batch-3 / codex-1 | True | False | 78.877 | 5 | True / True | 0 |
| batch-3 / codex-2 | True | False | 37.93 | 3 | True / True | 0 |
| batch-1 / claude-1 | True | True | 37.988 | 14 | True / True | 0 |
| batch-1 / claude-2 | True | True | 43.011 | 15 | True / True | 0 |

Task completion requires an updated test file, no off-target edits, successful fresh unit/browser acceptance, observed subject test/browser commands, and a subject screenshot. Codex produced working patches and accurately reported that its sandbox prevented browser execution. Its task-complete value is false because the subject browser step could not finish.

The repeatability gate requires two valid trials, matching off-target verdicts, and an assistant-event difference no greater than `max(2, ceil(0.25 * larger_count))`. Claude counts 14/15 pass (allowance 4); Codex counts 5/3 pass (allowance 2). agy is ineligible. These gates do not establish equivalence across providers.

## Corrections and excluded attempts

- Batch 1: Codex could not execute tools because ignoring user configuration omitted its Windows sandbox setting; agy denied fixture directory inspection. Claude completed both trials.
- Approved correction: explicitly select the existing Codex `windows.sandbox="unelevated"` while retaining `workspace-write`, and allow agy fixture listing/reading while retaining its sandbox flag and URL/MCP denies.
- Batch 2: Codex completed its model turn but archival collided with an inherited tag; output was recovered and bundled, but exit code and duration were unavailable. The trial is excluded. Archive tags now include the batch, seed clones omit tags, and process metadata is saved before archival. agy denied the `dir` alias.
- Batch 3: two corrected Codex trials completed. Batch 4: agy could inspect files, but the original Python glob-style permission failed to match its command.
- Batch 5: corrected literal command-prefix rules and workspace-scoped file grants allowed progress; agy then requested unapproved `git log -p -2`. The trial is excluded. It was not retried under broader permissions.

The agy permission syntax correction follows its [official CLI permission rules](https://antigravity.google/docs/permissions). The Codex setting follows its [Windows sandbox documentation](https://learn.chatgpt.com/docs/windows/windows-sandbox). No permission-denied trial is counted as a model failure. Old summaries remain intact; the report reparses raw streams with a hashed scorer snapshot, including stderr soft-denials even when agy emits terminal SUCCESS.

## Limits and remaining work

- Four protocol-valid trials cover Claude and Codex. agy has no valid pair; the three-lane comparison is incomplete.
- Codex attempted the real browser but Windows returned PermissionError [WinError 5] creating a pipe. Both fresh patch replays passed unit and browser acceptance. This is an environment limitation, not evidence of incorrect patches.
- batch-3/codex-1 overlapped the excluded batch-4/agy-1 diagnostic for about 17 seconds. Wall times are descriptive only; no timing ranking is supported.
- Requested model selectors and effort are pinned; Claude and agy report their model in the stream, while the Codex stream does not attest its backend model identity.
- Permissions and sandbox implementations differ across CLIs. --sandbox is requested for agy; that flag alone does not prove OS sandbox availability.
- Assistant-event counts are provider-specific and support only the predeclared within-lane repeatability check.
- Supervised interruptions and blind human cleanup scoring remain unmeasured (null). No migration recommendation follows.

Remaining: obtain the requested bounded Git-history approval, run two agy trials in a new recorded batch, and recompute the gate. Supervised trials and blind human cleanup scoring remain a separate later phase.

## Verification

13 harness tests pass, including pin rejection, permission denial handling, prefix/path generation, parser semantics, repeatability and recoverable archive collisions. The existing Taxonomy Bench suite also passed (230 tests). All four valid subject patches passed fresh unit tests and the trusted real-Chromium feature checks.

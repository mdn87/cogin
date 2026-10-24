# Agent CLI comparison: 2026-10-24

The pinning fix and approved agy corrections are implemented. Status: unattended batch incomplete. The report records all primary outcomes and every excluded attempt; no model ranking is claimed.

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
| batch-12 / agy-1 | False | False | 600.726 | 21 | True / False | 0 |
| batch-12 / agy-2 | False | False | 47.716 | 6 | True / False | 0 |
| batch-3 / codex-1 | True | False | 78.877 | 5 | True / True | 0 |
| batch-3 / codex-2 | True | False | 37.93 | 3 | True / True | 0 |
| batch-1 / claude-1 | True | True | 37.988 | 14 | True / True | 0 |
| batch-1 / claude-2 | True | True | 43.011 | 15 | True / True | 0 |

Task completion requires an updated test file, no off-target edits, successful fresh unit/browser acceptance, observed subject test/browser commands, and a subject screenshot. Codex produced working patches and accurately reported that its sandbox prevented browser execution. Its task-complete value is false because the subject browser step could not finish.

The repeatability gate requires two valid trials, matching off-target verdicts, and an assistant-event difference no greater than `max(2, ceil(0.25 * larger_count))`. See the machine-readable evidence for each lane: Claude counts 14/15 pass (allowance 4); Codex counts 5/3 pass (allowance 2). agy results use the same frozen tolerance. These gates do not establish equivalence across providers.

## Corrections and excluded attempts

- Batch 1: Codex could not execute tools because ignoring user configuration omitted its Windows sandbox setting; agy denied fixture directory inspection. Claude completed both trials.
- Approved correction: explicitly select the existing Codex `windows.sandbox="unelevated"` while retaining `workspace-write`, and allow agy fixture listing/reading while retaining its sandbox flag and URL/MCP denies.
- Batch 2: Codex completed its model turn but archival collided with an inherited tag; output was recovered and bundled, but exit code and duration were unavailable. The trial is excluded. Archive tags now include the batch, seed clones omit tags, and process metadata is saved before archival. agy denied the `dir` alias.
- Batch 3: two corrected Codex trials completed. Batch 4: agy could inspect files, but the original Python glob-style permission failed to match its command.
- Batch 5: corrected literal command-prefix rules and workspace-scoped file grants allowed progress; agy then requested unapproved `git log -p -2`. The trial is excluded. Matt subsequently approved fixture Git-history access and running the batch.
- Batch 6: the approved Git-history correction was recorded, but Windows denied the required unit-test command despite its Python prefix rule. Batch 7 added exact task commands; a baseline browser invocation without flags was denied. Both attempts remain excluded.
- Batch 8: documented Windows regex rules encode argument variations for the already-authorized Python, Git diff/status/log and fixture-inspection commands. No arbitrary-command grant or sandbox bypass was added. The Python and Git rules matched, but Git could not read the linked seed metadata outside the trial folder. A subsequent Test-Path request on that metadata was denied. The trial remains excluded; Matt later approved read-only access to that isolated metadata and exact path checks for the next batch.
- Batch 9: the approved read-only metadata grant was recorded, but agy requested `cmd /c dir`, a spelling missing from the fixture-listing rules. The permission-denied trial remains excluded.
- Batch 10: an anchored rule permits exactly `cmd /c dir` under the existing fixture-listing authorization. It rejects extra paths, chained commands, and other cmd operations. The approved read-only metadata grant and existing sandbox/URL/MCP restrictions remained in force. The trial hit a shell launch failure at the inherited Codex app PowerShell, then a denied echo diagnostic; it remains excluded.
- Batch 11: pin installed PowerShell 7 first on the agy child PATH. Its hash/version are verified before and after each trial; the parent PATH is unchanged. No echo permission or sandbox bypass was added. Directory inspection and git log then succeeded, proving the shell and metadata corrections. A request to git show the frozen seed commit was denied; the trial remains excluded.
- Batch 12: permit exactly git show of the frozen seed commit under the existing read-only fixture-history authorization; additional arguments or other commits are not granted. The first trial ran Python tests but stalled at Playwright startup, then hit the unchanged 600-second process deadline. Its incomplete stream is excluded, not scored as a model failure. The second trial was denied a Select-String status-filter search and is also excluded.
- After batch 12: add an exact status-filter fixture-search rule for future corrected batches. Its scope is unit-tested, but no live trial has used it. No further trial was launched while Playwright startup inside agy remains unresolved.
- Git converted trusted fixture line endings during checkout after the first merge. Preparation stopped on the hash mismatch. Restoring the original LF bytes and adding repository attributes preserves the frozen hashes across future Windows checkouts.

The agy permission syntax correction follows its [official CLI permission rules](https://antigravity.google/docs/permissions). The Codex setting follows its [Windows sandbox documentation](https://learn.chatgpt.com/docs/windows/windows-sandbox). No permission-denied trial is counted as a model failure. Old summaries remain intact; the report reparses raw streams with a hashed scorer snapshot, including stderr soft-denials even when agy emits terminal SUCCESS.

## Limits and remaining work

- 4 protocol-valid trials are recorded. The cross-lane repeatability gate is False; this small task does not establish statistical equivalence or justify migration.
- Codex attempted the real browser but Windows returned PermissionError [WinError 5] creating a pipe. Both fresh patch replays passed unit and browser acceptance. This is an environment limitation, not evidence of incorrect patches.
- batch-3/codex-1 overlapped the excluded batch-4/agy-1 diagnostic for about 17 seconds. Wall times are descriptive only; no timing ranking is supported.
- Requested model selectors and effort are pinned; Claude and agy report their model in the stream, while the Codex stream does not attest its backend model identity.
- Permissions and sandbox implementations differ across CLIs. --sandbox is requested for agy; that flag alone does not prove OS sandbox availability.
- Assistant-event counts are provider-specific and support only the predeclared within-lane repeatability check.
- Batch-12/agy-1 reached sync_playwright().start() but did not return before the 600-second trial deadline. Fresh verification outside the subject sandbox can start Playwright; the subject environment remains a comparison limitation.
- Supervised interruptions and blind human cleanup scoring remain unmeasured (null). No migration recommendation follows.

The unattended trial collection remains incomplete. The approved metadata grant and pinned system shell are live-verified. Two valid agy repeats are still missing: Playwright startup inside agy remains unresolved, and the new fixture-search correction is not live-verified. No failed gate is waived. Supervised trials and blind human cleanup scoring remain a separate later phase.

## Verification

19 harness tests pass, including pin rejection, permission denial handling, Windows command rules and exact cmd listing scope, pinned child-shell isolation and integrity, exact fixture-search scope, parser semantics, repeatability and recoverable archive collisions. The existing Taxonomy Bench suite previously passed (230 tests) and is unchanged. Fresh unit-test and real-Chromium results appear per trial in the table above.

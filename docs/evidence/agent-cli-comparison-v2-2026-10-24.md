# Agent CLI comparison, protocol v2: 2026-10-24

Status: unattended v2 trial collection complete. Cross-lane repeatability gate: True. All subjects receive the same versioned task; browser acceptance runs independently after each patch is captured.

## Protocol and acceptance

Matt approved protocol v2 after v1 exposed subject browser sandbox failures. Subjects implement the status filter, update and run unit tests, and inspect their diff. The frozen prompt explicitly tells them not to launch Playwright or diagnose browser tooling. The controller applies each patch to a clean checkout, reruns the submitted tests, starts the app, and verifies its UI in real Chromium using the unchanged trusted helper.

A task pass requires fresh unit and Chromium acceptance, an updated test file, an observed subject unit-test command, and no off-target edits. Subject browser commands and screenshots are recorded but not required. Protocol validity still rejects permission denials, incomplete streams, timeouts, model mismatches and missing tool work.

The report scorer recognizes direct Python commands through common shell wrappers. A Codex file search mentioning browser_check.py was initially flagged as a launch; reparsing the retained stream corrects that observation. No accepted subject trial launched the browser helper. Original trial records remain unchanged.

The [historical v1 report](agent-cli-comparison-2026-10-24.md), original prompt, frozen manifests and results are preserved. No v1 outcome is rescored as v2. The report generator rejects mixed protocol versions.

## Pinned conditions

| CLI | Version | Requested model |
|---|---|---|
| claude | 2.1.296 (Claude Code) | `claude-sonnet-5` |
| codex | codex-cli 0.164.0 | `gpt-6.1-sol` |
| agy | 1.4.7 | `gemini-3.8-flash-medium` |

Seed commit: `ffb5bb0a74367996b8e44a19ce1a3152820ae5a2`. V2 prompt SHA-256: `e47ebc9926fe7e8d1f0b4d991b2d67c709e777a2ee4b739c99af11ec4ac2d85b`.

All lanes use medium effort and subscription authentication. Exact binary hashes and versions are checked before and after each trial. The installed PowerShell is pinned for agy and selected only in its child PATH. Existing scoped fixture inspection/history and read-only seed metadata grants remain in force; sandbox and URL/MCP restrictions are retained. Trials run sequentially, each with the same 600-second deadline.

The [machine-readable report](agent-cli-comparison-v2-2026-10-24.json) includes source manifests, patch and raw-artifact hashes, independent verification artifacts, scoring-source hash, and any excluded attempts. Raw conversations, executable paths and screenshots remain in ignored local artifacts.

## Observed trials

| Source / trial | Protocol valid | Task passed | Seconds | Assistant events | Fresh tests / browser | Subject browser | Off-target lines |
|---|---|---|---:|---:|---|---|---:|
| protocol-v2-batch-2 / agy-1 | True | True | 288.348 | 19 | True / True | False | 0 |
| protocol-v2-batch-2 / agy-2 | True | True | 250.004 | 22 | True / True | False | 0 |
| protocol-v2-batch-1 / claude-1 | True | True | 47.726 | 14 | True / True | False | 0 |
| protocol-v2-batch-1 / claude-2 | True | True | 43.576 | 12 | True / True | False | 0 |
| protocol-v2-batch-1 / codex-1 | True | True | 109.741 | 3 | True / True | False | 0 |
| protocol-v2-batch-1 / codex-2 | True | True | 44.57 | 2 | True / True | False | 0 |

## Repeatability

The frozen tolerance remains `max(2, ceil(0.25 * larger_count))`, with matching off-target verdicts and two protocol-valid trials. Failed gates are reported without retries chosen to improve the score.

| Lane | Assistant events | Allowed difference | Gate |
|---|---|---:|---|
| claude | [14, 12] | 4 | pass |
| codex | [3, 2] | 2 | pass |
| agy | [19, 22] | 6 | pass |

## Excluded attempts

- protocol-v2-batch-1/agy-1: permission denial

The first v2 agy attempt was denied a multiline Python command because the existing regex did not match line breaks. A separately recorded corrected batch uses an anchored multiline match within the existing Python grant. Claude and Codex results are retained only because their full lane pins and the frozen v2 task match. No subject browser requirement or acceptance check was restored or weakened.

## Limits

- Two repeats of one small task per lane do not establish statistical equivalence, a model ranking, or a migration recommendation.
- V2 measures browser-correct patches through an independent verifier; it does not measure subjects driving a browser. V1 scores and timing are historical and are not pooled with v2.
- Requested model selectors and medium effort are pinned. The Codex event stream does not attest its backend model identity.
- CLI implementations and sandbox behavior differ. The agy sandbox flag is retained; its presence alone does not establish OS sandbox availability.
- Assistant-event counts have provider-specific semantics and support only the frozen within-lane repeatability gate.
- Supervised interruptions and blind human cleanup scores remain unmeasured (null).

## Verification

34 harness tests pass, including version-specific acceptance and refusal to combine protocols. All 18 historical v1 task scores were checked for preservation before the v2 runs. Fresh unit and real-Chromium outcomes appear per trial above.

# Agent CLI Comparison Harness

**Status:** unattended harness implemented; live evidence and remaining limits
are in [the v2 report](../evidence/agent-cli-comparison-v2-2026-10-24.md).
The [v1 report](../evidence/agent-cli-comparison-2026-10-24.md) remains historical.
Supervised approval counts and blind human cleanup scoring remain a later phase.
Implementation: [`src/agent-cli-harness`](../../src/agent-cli-harness/).
**Relationship to Wave 1:** none. This is a separate experiment with a separate
harness. Do not extend `taxonomy_bench_wave.py` for it.

## Why this is not Taxonomy Bench

Wave 1 measures single-prompt answer correctness with tools **disabled**
(`--tools ""`, `codex --sandbox read-only`) and exact JSON scoring. This
experiment measures **agentic repo work with tools required**, scored on
process quality rather than answer correctness. Opposite protocol, opposite
metrics, different lane registry.

## Question being answered

Does another agent CLI materially beat the current Codex/Claude setup on
completion time, operator interruption, review burden, test reliability, or
cleanup required — on one contained repo task?

A tool earns a migration only by winning materially on at least one axis.

## Lanes

| Lane | Command shape | Automatable |
|---|---|---|
| `claude` | `claude -p --output-format stream-json --permission-mode <mode> --add-dir <wt>` | yes |
| `codex` | `codex exec --json -C <wt> -m <model> -s workspace-write` | yes |
| `agy` | `agy --print= --input-format stream-json --output-format stream-json --model <model> --mode <mode>` (prompt on stdin, cwd `<wt>`) | yes |

Updated 2026-10-22: the Antigravity CLI (`agy` 1.4.5) replaces both the retiring
Gemini CLI lane and the hand-run Antigravity IDE lane. It runs headless with
machine-readable output, so every lane is now instrumented. Verified installed
then: `claude` 2.1.296, `codex` 0.163.0, `agy` 1.4.5. See
`docs/evidence/agy-cli-characterization.md` for its stdin event format,
output events, permission profile, and conversation resume behavior.

## Approval modes

Interruption count is meaningless under auto-approve — it is zero by
construction. Run each lane twice:

- **Supervised** — `claude --permission-mode default`, `codex` default
  approvals, and `agy` with a `request-review` permission profile. Scores
  *interruptions* and *review burden*.
- **Unattended** — `claude --permission-mode acceptEdits`, `codex -s
  workspace-write`, `agy --mode accept-edits`. Scores *wall-clock* and *diff
  quality*.

Without a permission profile, agy print mode reports `always-proceed` and
auto-approves every tool call. Every agy lane must therefore load an explicit
profile and record the `permission_mode` from its `init` event. agy 1.4.4
warned that `--mode plan` has no effect together with
`--disable-slash-commands`. Check whether the chosen mode takes effect with that
flag before relying on it; other modes were not tested.

Do not use `bypassPermissions`, `--dangerously-bypass-approvals-and-sandbox`,
`--yolo`, or agy's `--dangerously-skip-permissions`. They change the sandbox,
not just the prompting, and break comparability.

## Seed repo

A pinned fixture repo, not cogin. Requirements:

- small web app with a real server and a browser-visible behavior;
- existing test suite that passes at the seed commit;
- no network dependencies;
- committed at a known SHA; every run starts from that exact SHA.

Each run gets its own `git worktree` off the seed SHA. Torn down after the
diff is captured, archived per the repo's branch-archival rule.

## Task spec

One prompt, byte-identical across lanes, stored in the harness and hashed into
each run record. Protocol v2 requires the subject to add one feature, update
and run unit tests, and produce a clean diff. The independent verifier applies
the patch to a clean checkout, reruns the submitted tests, starts the app, and
checks the UI in real Chromium with the trusted helper. Subject browser
execution and screenshots are not required.

V1 required subjects to run the browser themselves. Its frozen prompt and
scores remain unchanged. V2 has a new prompt hash and explicit protocol version;
all three lanes require fresh repeats, and reports reject mixed versions.

## Metrics

| Metric | How captured | Notes |
|---|---|---|
| Wall-clock | harness timer around the process | unattended mode only |
| Turns | count of assistant events in the JSON stream | all three emit this |
| Interruptions | count of approval prompts hit | supervised mode only |
| Off-target diff | `git diff --numstat` lines outside the intended file set | intended set declared in the task spec |
| Test reliability | suite re-run on a **fresh** checkout of the produced diff | catches "passes only in the agent's dirty worktree" |
| Cleanup | lines a human must revert before merge | scored by hand, one reviewer, blind to lane |

## Known asymmetries — record, do not paper over

1. **Browser verification.** V2 measures browser-correct patches through a
   shared independent verifier. It does not measure subjects' ability to drive
   a browser. V1's subject-browser failures remain historical environment
   evidence and are not reclassified as v2 successes.
2. **Model vs harness.** A lane's result confounds the model with its CLI's
   agent loop. This measures CLI session configurations, not models — same
   caveat Wave 1 carries.

## Build order

1. Build and pin the seed repo; confirm its suite is green at the seed SHA.
2. Write the task spec and freeze its hash.
3. Worktree provisioning + teardown with archival.
4. Per-lane runner with the flag sets above; capture raw JSON streams.
5. Stream parsers for turn and approval counts (three formats).
6. Diff and fresh-checkout test scorer.
7. Report renderer; blind review pass for the cleanup metric.

Steps 1-6 and unattended report rendering are implemented. Approval-event
counting and blind human review are not implemented; their scores remain null.

## Gate

The harness is trustworthy only when the same lane run twice on the seed SHA
produces the same turn count within noise and the same off-target diff verdict.
Until then, cross-lane differences are not evidence.

The first unattended batch freezes tolerance at an assistant-event difference
of `max(2, ceil(0.25 * larger_count))`, with matching off-target verdicts and two
protocol-valid trials. Assistant-event counts have different meanings across
CLIs; this checks within-lane consistency. Binary paths, hashes, versions,
requested models/effort, permissions, prompt and fixture hashes are recorded.
Denied or incomplete trials are retained and excluded rather than retried
silently. Permission changes require approval and a separate batch.

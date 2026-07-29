# Agent CLI Comparison Harness

**Status:** spec, not implemented
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
| `gemini` | `gemini -p --output-format stream-json --approval-mode <mode>` | yes |
| `antigravity` | IDE, no headless entry point | **no — hand-run** |

Verified installed: `claude` 2.1.195, `codex` 0.145.0, `gemini` 0.40.0.
`antigravity` is not installed and is an editor, not a CLI.

The Antigravity lane is measured by stopwatch and tally, and every report must
label it as manually observed. Do not present its numbers as peers of the
instrumented lanes.

## Approval modes

Interruption count is meaningless under auto-approve — it is zero by
construction. Run each lane twice:

- **Supervised** — `claude --permission-mode default`, `codex` default
  approvals, `gemini --approval-mode default`. Scores *interruptions* and
  *review burden*.
- **Unattended** — `claude --permission-mode acceptEdits`, `codex -s
  workspace-write`, `gemini --approval-mode auto_edit`. Scores *wall-clock*
  and *diff quality*.

Do not use `bypassPermissions`, `--dangerously-bypass-approvals-and-sandbox`,
or `--yolo`. They change the sandbox, not just the prompting, and break
comparability.

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
each run record. It must require all five of: add one feature, update tests,
run the app, verify behavior in the browser, produce a clean diff.

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

1. **Browser verification.** Claude Code has browser tooling; Codex and Gemini
   CLI do not natively. Score *how* each lane verified (real browser, curl,
   test-only, not at all) rather than pass/fail. A lane that skipped
   verification and a lane that could not are different results.
2. **Antigravity is not instrumented.** See above.
3. **Model vs harness.** A lane's result confounds the model with its CLI's
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
8. Hand-run the Antigravity lane last, if it is installed by then.

Steps 1-7 are roughly a day. Step 8 is gated on installing the IDE, which is
an operator decision.

## Gate

The harness is trustworthy only when the same lane run twice on the seed SHA
produces the same turn count within noise and the same off-target diff verdict.
Until then, cross-lane differences are not evidence.

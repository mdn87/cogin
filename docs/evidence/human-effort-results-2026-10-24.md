# Human effort observations — 2026-10-24

Six unattended patches have completed attested blind review. Two supervised
Claude sessions passed with four human approval prompts each. The Codex attempt
did not complete the task and supplies no valid interruption measurement.
These observations do not establish a CLI ranking.

The [sanitized records](human-effort-results-2026-10-24.json) retain binary,
source, capture, patch, and receipt hashes. Credentials, raw sessions, local
paths, reviewer identity, and free-text review reasons remain private.

## Blind cleanup review

One reviewer assessed the six accepted [v2 unattended patches](agent-cli-comparison-v2-2026-10-24.md)
before lane identities were revealed. Five patches received zero cleanup lines;
the Claude first-repeat patch received one line selected for reversion. The
reviewer's concern about that error-response line is unverified and is not a
validated vulnerability finding. Original patches and historical scores remain
unchanged. These scores do not cover the new supervised patches.

## Supervised sessions

| Capture | Human prompts | Allows | Denials | Task acceptance |
|---|---:|---:|---:|---|
| Claude `cfbbac84179d` | 4 | 3 | 1 | Passed fresh unit and Chromium checks |
| Claude `9cd8acaf639a` | 4 | 3 | 1 | Passed fresh unit and Chromium checks |
| Codex `5f078968f17e` | Unmeasured | Unmeasured | Unmeasured | Failed feature check; no edits |

The operator chose to finish the extra Claude run; both captures are retained.
Their native requests and explicit human decisions reconcile with the approval
ledger, with no unresolved requests. Permission profiles and transports differ
between CLIs; these counts are not pooled with unattended timing or event counts.

Codex's effective policy was `on-request`, reviewer `user`, with
`workspace-write` and Windows `unelevated` sandbox. Its native stream contained
no approval request. The sandbox log recorded three inspection command starts
without completion, and the agent reported that file reads never returned.
The turn ended without edits; the capture process exited with code 1 and
`capture_complete` is false. Baseline unit tests passed, but the independent
feature browser check failed. This is not a zero-interruption success.

Follow-up [sandbox diagnostics](codex-sandbox-diagnostic-2026-10-24.json)
reproduced the stall outside the model and console: a simple `echo` timed out
after 20 seconds under the pinned `unelevated` implementation. The same
read-only check passed under MXC, both through `codex sandbox` and app-server
`command/exec`, with exit code 0. The app-server check retained `workspaceWrite`
and `networkAccess: false`. No model turn or human measurement was generated.
An earlier diagnostic was rejected for missing a permission-profile argument;
it supplies no execution evidence. The deeper legacy sandbox failure remains
undiagnosed.

A fresh Codex capture can use MXC with `on-request`, reviewer `user`, and
`workspace-write`. This proposed implementation change awaits operator approval
and a separate source manifest; the failed capture stays intact. MXC changes
Windows isolation and permits host loopback, as described in the official
[Windows sandbox documentation](https://learn.chatgpt.com/docs/windows/windows-sandbox).
No replacement supervised run has been launched.

agy still lacks a supported interactive approval channel. Cleanup review of
the two new Claude patches also remains unmeasured. The sample is small and
comes from one human reviewer/operator.

## Validation

- Accepted receipt, input form, source package, capture manifests, raw artifact
  hashes, and approval ledgers validated using the existing review/report tools.
- All three Git bundles verified; temporary subject worktrees were removed
  after archival. All 57 historical fingerprints and original v2 trial artifact
  hashes remained unchanged.
- All 62 harness tests passed, including real Chromium checks for review
  submission and the idle, waiting, pending-approval, and ended session states.

The console now explains that no approval is pending while a CLI works and
directs the operator to the result when a session ends. Codex only sends a
request when its policy requires a decision; see the official
[app-server approval protocol](https://learn.chatgpt.com/docs/app-server#approvals).

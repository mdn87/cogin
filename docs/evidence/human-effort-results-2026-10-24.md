# Human effort observations — 2026-10-24

Six unattended patches have completed attested blind review. Two supervised
Claude sessions passed with four human approval prompts each. An approved MXC
Codex session passed with three human approval prompts. Three earlier Codex
attempts remain incomplete and supply no valid interruption measurements.
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
| Codex legacy `5f078968f17e` | Unmeasured | Unmeasured | Unmeasured | Failed feature check; no edits |
| Codex legacy `340277b0b3e6` | Unmeasured | Unmeasured | Unmeasured | Stalled; controller stopped it before the approved MXC switch |
| Codex MXC `8d0830214671` | Unmeasured | Unmeasured | Unmeasured | Timed out waiting for a human decision |
| Codex MXC `4e46769c7ad5` | 3 | 3 | 0 | Passed fresh unit and Chromium checks |

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

The operator approved a fresh Codex capture using MXC with `on-request`, reviewer
`user`, and `workspace-write`. The separate `supervised-mxc-source-1` manifest
retains the original seed, prompt, binary, model and effort. Both legacy attempts
stay intact. MXC changes Windows isolation and has host-loopback behavior
described in the official
[Windows sandbox documentation](https://learn.chatgpt.com/docs/windows/windows-sandbox).

The first MXC run received one human allow but timed out with a second request
unanswered. An older browser tab still held an expired access token after the
server restart. The operator started another run, and both open review tabs
were reconnected. The final run received three explicit human allows, no denials,
and no unresolved requests. It edited only `app.py` and `test_app.py`, ran unit
tests, and passed fresh patch replay and Chromium feature acceptance.

The sandboxed socket tests failed with Windows error 10013, so Codex replaced
them with in-memory HTTP handler tests. The independent verifier still exercised
the resulting app in a real browser. File edits required human approval to retry
outside the sandbox. The native runtime also exposed user-installed skills
despite its isolated auth directory. These are CLI configuration observations,
not an isolated model comparison or proof that all MXC networking works.

The final Codex capture is one completed observation, not a supervised repeatability
result. Its three prompts cannot establish lower human effort than Claude's four:
permission profiles, outcomes, and sample sizes differ. All failed attempts are
included in the sanitized records rather than replaced by the successful run.

agy still lacks a supported interactive approval channel. Cleanup review of
the new supervised patches also remains unmeasured. The sample is small and
comes from one human reviewer/operator.

## Validation

- Accepted receipt, input form, source package, capture manifests, raw artifact
  hashes, and approval ledgers validated using the existing review/report tools.
- All six Git bundles verified; temporary subject worktrees were removed
  after archival. All 57 historical fingerprints and original v2 trial artifact
  hashes remained unchanged.
- All 62 harness tests passed, including real Chromium checks for review
  submission, session states, disabling stale approval controls after token
  rotation, and reconnecting through a new private link without manual reload.

The console now explains that no approval is pending while a CLI works,
disables controls when disconnected, reconnects through updated private links,
and directs the operator to the result when a session ends. Codex only sends a
request when its policy requires a decision; see the official
[app-server approval protocol](https://learn.chatgpt.com/docs/app-server#approvals).

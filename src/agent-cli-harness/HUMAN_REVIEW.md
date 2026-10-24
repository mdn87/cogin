# Human effort measurements

The unattended v2 comparison is complete. These tools add separate human
measurements without changing its trials, prompt, acceptance gates, or reports.
Missing measurements stay `null` in JSON and `unmeasured` in Markdown. Zero is
valid only after a complete human observation or review.

## Local review console

From the repository root, open the prepared six-case package in your browser:

```powershell
python src/agent-cli-harness/review_console.py --open
```

The console binds only to `127.0.0.1:8765`; use `--port 0` for an available
port. Open the private link printed by the launcher. Keep one console process
per package. The link is local access, not a remote reviewer invitation.

- **Blind review:** read the task and original files, then one anonymous patch
  at a time. Select changed lines to revert; the page counts them. Give a
  specific reason and mark the patch reviewed. “No cleanup needed” explicitly
  records a reviewed zero, but still requires a reason. Line edits clear the
  reviewed flag. Do not run patch code or attest if you recognize identities.
- Progress saves automatically on this computer. Wait for “Saved on this
  computer” before closing. Reload to resume; competing tab edits are rejected
  rather than silently overwritten. A preexisting manual score form is preserved
  and must be imported using the command below before opening the console.
- Enter your name, attest that the review was blind, and submit to lock all
  scores. The controller mapping and derived reports are never served by the
  browser. Submission rechecks the package and uses the existing score validator.
- **Supervised sessions:** enter your name and explicitly start Claude or
  Codex. Inspect each native request and click **Allow once** or **Deny**.
  The page never grants persistent permission or answers automatically.
  **Stop current session** cancels further approvals; timeout or a closed
  console cannot turn missing observations into zero. Verification may continue
  briefly after stopping. agy remains unavailable because it cannot prompt.

The default session limit is 10 minutes. Keep the console process running while
reviewing or supervising; closing the browser does not terminate the process.
An interrupted session after a process restart requires controller inspection
before another run. Start only one subject process across all launchers.

Private draft, session, and derived report files live under the package's
`controller/`. `collection-status.json` prepares an evidence summary after
submission or session completion; it does not publish a Dias board update.
Session directories can contain subscription credentials and must stay private.
Use the CLI workflows below when a separate reviewer receives only `reviewer/`
or when collecting from a terminal. Automated UI tests use synthetic packages
and simulated approvals; they are not human measurements.

## Blind cleanup review

The prepared package for the six accepted v2 patches is at
`runs/blind-review-v2-1/reviewer/`. Give the reviewer **only that directory**.
The sibling `controller/` contains lane identities and must not be shown until
the review is complete. The reviewer must not already know which lane produced
the patches; use a different human if the reviewer recognizes the identities.
Unmodified code may still suggest an author, so blinding is an attested limit,
not a guarantee against inference.

The package includes the frozen task, common base files, six randomly labeled
patches, a fixed rubric, and `scores.json`. Count changed lines the reviewer
would revert before merging, not hypothetical new work or stylistic alternatives.
Every case needs an integer score and a specific reason. A complete review by
one named human and a true blind attestation are required for import.

From the repository root, create another package with a new output directory:

```powershell
python src/agent-cli-harness/human_review.py prepare --report src/agent-cli-harness/runs/protocol-v2-batch-2/report.json --batch src/agent-cli-harness/runs/protocol-v2-batch-1 --batch src/agent-cli-harness/runs/protocol-v2-batch-2 --output src/agent-cli-harness/runs/blind-review-v2-2
```

After the reviewer completes the existing package's form:

```powershell
python src/agent-cli-harness/human_review.py import-scores --package src/agent-cli-harness/runs/blind-review-v2-1 --scores src/agent-cli-harness/runs/blind-review-v2-1/reviewer/scores.json
```

Import validates case membership, duplicate/missing cases, integer bounds,
reasons, attestation, and package/source hashes. Accepted scores cannot be
overwritten. The derived JSON/Markdown report is under `controller/`; original
trial files and historical reports remain unchanged. Do not regenerate the
source report after preparing a review; it is bound by hash.

## Supervised capture

`supervised.py` starts an isolated fixture session and keeps the native input
and output streams open for bidirectional approvals. It records each request
and the human's explicit `allow` (once) or `deny` response, with timestamps.
Enter means deny. EOF, timeout, duplicate IDs, unknown request types, or an
unsupported decision stop the session without a grant. It never sends persistent
policy changes or automatic approvals. Native CLIs can still run actions that
their pinned policies permit without a prompt; the counter measures actual
prompts, not every tool call.

Run captures yourself in an interactive terminal. An agent or redirected stdin
cannot supply a measured human decision. Use a unique output directory per run:

```powershell
python src/agent-cli-harness/supervised.py capture --source src/agent-cli-harness/runs/protocol-v2-batch-2 --lane claude --operator Matt --output src/agent-cli-harness/runs/supervised-claude-1
python src/agent-cli-harness/supervised.py capture --source src/agent-cli-harness/runs/protocol-v2-batch-2 --lane codex --operator Matt --output src/agent-cli-harness/runs/supervised-codex-1
```

The default limit is 600 seconds including human response time; `--timeout`
accepts 1–3600 seconds and is recorded. The capture archives the patch and Git
bundle, then runs fresh unit and Chromium acceptance using the trusted verifier.
Human denial may end a task; a complete capture of that decision is still a
measurement, while `task_passed` remains false. Incomplete captures, unresolved
requests, and qualification probes never become zero-interruption successes.
Inspect `task_passed` separately from the approval count.

```powershell
python src/agent-cli-harness/supervised.py report --capture src/agent-cli-harness/runs/supervised-claude-1 --capture src/agent-cli-harness/runs/supervised-codex-1 --output src/agent-cli-harness/runs/supervised-human-report-1
```

The report verifies artifact hashes and reconciles the approval ledger with
native requests. It does not pool supervised runs with unattended repeatability
or timing results. Cleanup scores for new supervised patches remain unmeasured;
the existing blind package covers the six accepted unattended patches only.

## Qualified interfaces and limits

- **Claude Code 2.1.296:** `manual` mode (reported as `default`), stream-JSON
  control requests, and the stdio permission callback. Safe mode and an empty
  setting-source list exclude user customizations/grants. A real file-write
  request was denied through the callback; no probe file was created.
- **Codex 0.164.0:** app-server with `on-request`, reviewer `user`, and
  `workspace-write`. The effective response is checked before the model turn.
  The generated schema still lists `untrusted`, but this binary rejects it.
  An explicit probe escalation produced a real request; the offered negative
  decision was `cancel`, which ended the turn without executing the command.
  The adapter accepts `decline` when offered and otherwise `cancel`; it never
  substitutes a grant. This transport differs from unattended `codex exec`.
- **agy 1.4.7:** the request-review profile in headless mode auto-denies actions
  that need a prompt. Its stderr explicitly states that headless mode cannot
  prompt; no response channel was observed. Supervised capture rejects this
  lane before launching. A supported interactive event/response interface is
  needed before agy human interruption measurements can be collected.

`--probe` runs a bounded, deny-only channel qualification with a different task.
It must observe and resolve an actual approval request to qualify. These are
automated denials, not human decisions, and all human scores remain null.

Codex captures reuse the existing file-backed subscription login in an ignored
`private-home/auth.json` copy; they do not copy user configuration, hooks, MCPs,
or skills. API-key authentication is rejected. Keep capture directories private:
they contain credentials, raw sessions, and local paths. Share only the blind
`reviewer/` directory or the sanitized public qualification report.

Neither a qualified approval channel nor a passing patch establishes a CLI
ranking. Actual human cleanup scores and supervised trials are still required.

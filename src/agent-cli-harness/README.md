# Agent CLI comparison harness

This experiment measures a small repo task with tools enabled. It is separate
from Taxonomy Bench and does not use the Wave controller or its task scores.
The current implementation runs unattended trials only. Supervised approval
counts and blind human cleanup scores are intentionally null.

The application fixture uses Python's standard library. Verification uses an
already-installed Python Playwright package and Chromium; no dependency or
browser download occurs during a trial. The verified host is Windows 11 with
Python 3.14. Other operating systems have not been qualified for live runs.

## Protocol

Each batch pins the exact native executable path, SHA-256, version, requested
model and effort; the seed Git commit; the byte-identical task prompt; and
the fixture/acceptance-helper hashes. SHA-256 and version are checked before
and after every trial. agy and Claude automatic updates are disabled in child
environments. API-key environment variables are removed, and existing
subscription authentication is used. No global PATH or user setting changes
are needed.

Repository attributes preserve LF bytes for the hashed Python and fixture
files across Windows checkouts. An integrity mismatch stops preparation;
the controller never silently replaces a frozen hash.

The seed app lists three tasks. The subject must add a status filter, update
tests, run the local app through the provided Chromium helper, and inspect its
diff. Only `app.py` and `test_app.py` are intended edits. Each trial starts in a
fresh worktree at the same seed commit. The process deadline is 600 seconds;
there are no automatic retries. Provider restrictions remain enforced.

Raw stdout/stderr and the exact argument list are retained under the ignored
`runs/` directory. Output is committed in the isolated fixture repository,
tagged `archive/<batch>/<trial>`, and saved in a verified Git bundle before the
worktree is removed. The fixture repository has no remote; its retained tags
and self-contained bundles provide recovery without publishing subject code.
Subject screenshots are copied to the trial artifacts before cleanup.

The scorer applies the captured binary patch to another clean checkout,
runs the submitted unit tests, and executes the trusted browser helper from
the harness source against that checkout. This prevents a modified subject
helper from replacing acceptance checks. Off-target scoring includes newly
added files and renames; binary off-target files fail the verdict even though
their line count is unknown (reported as zero). A task pass also requires an
updated test file, observed unit-test and browser commands, a subject browser
screenshot, and no off-target edits. A correct replayed patch can therefore
pass acceptance even when the subject could not run the browser itself.

Malformed/incomplete streams, CLI errors/timeouts, model mismatches, unexpected
permission modes, permission denials, and trials with no completed tool events
are excluded from repeatability. A recorded permission denial prevents another
trial on that lane in the same batch. Correcting and retrying its permission
configuration requires explicit authorization and a separately recorded batch.

Assistant-event counts are provider-specific: Claude assistant messages,
Codex completed agent-message items, and agy completed agent-response steps.
Native reported turn counts are recorded separately. User-input steps and tool
events are not counted as assistant events. The predeclared repeatability gate
requires two valid trials, identical off-target verdicts, and an assistant-event
difference no greater than `max(2, ceil(0.25 * larger_count))`. This is a coarse
within-lane check, not proof of statistical equivalence or a model ranking.

## Commands

Run from the project root, supplying actual native executable paths rather
than shell shims or PATH aliases:

```text
python src/agent-cli-harness/harness.py --root <new-batch-directory> prepare --codex <codex.exe> --claude <claude.exe> --agy <agy.exe>
python src/agent-cli-harness/harness.py --root <batch-directory> run --lane claude --repeat 1
python src/agent-cli-harness/harness.py --root <batch-directory> run --lane claude --repeat 2
python src/agent-cli-harness/harness.py --root <batch-directory> report
python -m pytest src/agent-cli-harness/tests -q
```

On Windows, explicitly pin the authorized implementation with
`prepare --windows-sandbox unelevated` (or `elevated` if configured).
`--ignore-user-config` makes this necessary for Codex. An approved correction
uses a new directory and records the approval text:

```text
python src/agent-cli-harness/harness.py --root <new-directory> prepare-corrected --source <old-directory> --authorization "<actual approval and scope>"
python src/agent-cli-harness/harness.py --root <new-directory> report --include <prior-directory>
```

`prepare-corrected` enables the approved Windows sandbox setting and fixture
inspection commands. `--allow-git-log` requires separate approval for that
command. These options record permission; they do not supply authorization.
`--allow-git-metadata` separately records approved read-only access to the
isolated seed repository's `.git` directory and exact path-existence checks.
Linked worktrees otherwise point outside the trial's sandbox file grants.
This correction must be live-verified after approval; it is not enabled by
default or retroactively applied to earlier trials.
agy rules use literal command prefixes, not shell globs, and workspace paths
grant recursive file access. See the [official rules](https://antigravity.google/docs/permissions).
Windows can require full-command matches. New batches therefore use documented
`regex:` rules for argument variations within the authorized Python,
`git diff`/`status`, and fixture-inspection command classes. Git-history rules
are added only by the approved correction. Exact entries for the frozen test
and browser commands are also recorded. No rule grants arbitrary commands or
all Git subcommands.
The harness retains `--sandbox` and denies URL/MCP operations. CLI-specific
permission handling and actual sandbox availability remain comparison limits.

Repeat the two run commands for each available lane. Do not retry a denied
lane or change its settings without authorization. Reports are recomputed from
the retained raw events; their `scoring_source_sha256` and a matching source
snapshot identify the parser version. Initial trial summaries remain intact
if a parser defect is corrected. Session identifiers and raw conversations
stay private; publish only selected aggregate evidence.

Run one subject process at a time. The controller does not enforce a
machine-wide lock across separate invocations. Reports combine earlier lanes
only when their full pins and task hashes match; newer lane records supersede
older records regardless of outcome. Excluded trials remain visible. Process
metadata is saved before archival, and `finalize` can start postprocessing
from that saved record without invoking the subject again. Failures after
partial archival require inspection before recovery; finalization is not
idempotent.

The initial batch pins Codex 0.164.0 from the npm native package, Claude
2.1.296, and agy 1.4.7. This avoids PATH's Clici-specific Codex 0.162.1.
The [2026-10-24 evidence](../../docs/evidence/agent-cli-comparison-2026-10-24.md)
records the actual outcomes, excluded attempts, and remaining work. No model
ranking or migration decision follows from this small experiment.

# Subscription CLI Wave 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [x]`) syntax for tracking.

**Goal:** Make the six approved subscription-backed runplans executable through
native Claude Code and Codex CLI providers plus a restartable Wave 1 controller.

**Architecture:** Keep scoring, suite generation, and report rendering in
`taxonomy_bench.py`. Add a focused provider module for subscription CLI process
control and a focused Wave 1 module for immutable manifests, family locks,
calibration selection, and lane state. The existing CLI wires those modules
together without exposing the private suite to subject sessions.

**Tech Stack:** Python 3.10+, standard library, pytest, Claude Code CLI, Codex
CLI, PowerShell release packaging.

---

## Governing Documents

- Design:
  `docs/superpowers/specs/2026-07-25-subscription-cli-benchmark-design.md`
- Shared protocol: `docs/runplans/README.md`
- Operator prompt: `docs/runplans/OPERATOR-PROMPT.md`
- Model runplans: `docs/runplans/*.md`

If this plan conflicts with the design specification, stop and update the plan
before writing code. Do not weaken model resolution, authentication, isolation,
fallback, or private-suite gates to make a run proceed.

## Current State

> **Status correction (2026-08-02):** an earlier session marked every task
> complete, but only Tasks 1-4 and 6-7 (plus parts of 5 and 8) actually landed
> in commit `f4fe7be`. Checkboxes below now reflect verified code state.
> Remaining work is planned in
> `docs/superpowers/plans/2026-08-02-wave-1-completion.md`, which supersedes
> Tasks 8-12 here.

- `main` tracks `origin/main` at `f4fe7be`; 155 tests pass.
- Landed: `taxonomy_bench_protocol.py` (instructions, canonical JSON/hashes),
  `taxonomy_bench_cli.py` (`ClaudeCliProvider`, `CodexCliProvider`, sanitized
  env, injectable process runner, `preflight()`), `taxonomy_bench_wave.py`
  (manifest preparation, family locks, lane state, pair barriers,
  `WaveController` with subject-root validation and `build_provider`).
- Not landed despite prior checkmarks: the four `wave` CLI subcommands, the
  calibration admission gate (test class is an empty stub), the per-attempt
  checkpoint/immediate-abort seam, session-identifier redaction, lane reports,
  pair aggregation, packaging updates (`py-modules`, `.gitignore`, release
  map), documentation updates, and live preflight (`VALIDATION.md` is still
  the 2026-07-21 record).
- The upstream Marble taxonomy is not currently checked out in this repository.
  Implementation and synthetic end-to-end tests use `sample_data`; real Wave 1
  preparation waits for an operator-provided upstream checkout.

## File Map

| File | Responsibility |
|---|---|
| `src/taxonomy-bench/taxonomy_bench_protocol.py` | Single owner of benchmark instructions, shared exceptions, canonical JSON, and protocol hashes |
| `src/taxonomy-bench/taxonomy_bench_cli.py` | Provider base types, subprocess injection seam, auth/model preflight, Claude and Codex CLI invocation and output parsing |
| `src/taxonomy-bench/taxonomy_bench_wave.py` | Wave 1 protocol, manifest hashing, deterministic calibration selection, family locks, lane state, admission and pair barriers |
| `src/taxonomy-bench/taxonomy_bench.py` | Existing scoring/run engine; provider construction and `wave` command wiring |
| `src/taxonomy-bench/tests/test_subscription_cli.py` | Sanitized CLI fixtures, command construction, parsing, error classification, and session-continuation tests |
| `src/taxonomy-bench/tests/test_wave_controller.py` | Manifest, calibration, locks, state, restart, barriers, and fake-provider end-to-end tests |
| `src/taxonomy-bench/pyproject.toml` | Include the three new modules in the wheel |
| `src/taxonomy-bench/.gitignore` | Ignore Wave 1 private data, subject workspaces, and run artifacts |
| `src/taxonomy-bench/scripts/package-release.ps1` | Add new modules and tests to the deterministic release map |
| `src/taxonomy-bench/README.md` | Document subscription providers and Wave 1 commands |
| `src/taxonomy-bench/BENCHMARK_SPEC.md` | Record subscription-session controls and infrastructure handling |
| `src/taxonomy-bench/VALIDATION.md` | Record final local and live-preflight evidence |
| `src/taxonomy-bench/SHA256SUMS` | Regenerated release checksums |
| `src/taxonomy-bench.zip` | Regenerated deterministic release archive |

## Non-Negotiable Boundaries

- Subscription CLIs must not fall back to API billing.
- The requested and resolved model must match the lane.
- Subject sessions receive only one public task prompt and its response shape.
- Each task has a distinct session. Only that task's session may be resumed for
  continued retries.
- Calibration sessions are ephemeral.
- No two Claude lanes or two Codex lanes overlap.
- Pair N+1 waits for Pair N aggregation.
- Infrastructure failures abandon the affected repeat; they are not wrong
  answers.
- Raw private suites, subject sessions, and run artifacts remain uncommitted.
- A sterile subject root outside the Cogin repository is required for live
  runs. Creating it is an outside-project write and therefore requires explicit
  operator approval at execution time. The controller accepts
  `--subject-root`; it never chooses or creates an outside-project path
  implicitly.
- A controller-global control root outside Cogin is also required for
  cross-process family and aggregation locks. The operator approves its exact
  path once. Every Wave manifest records the same resolved control root so
  separate wave directories cannot bypass subscription-family locks.

## Implementation Tasks

### Task 1: Characterize Current CLI Contracts

**Files:**

- Create: `src/taxonomy-bench/tests/test_subscription_cli.py`
- Create: `docs/evidence/wave-1-cli-characterization.md`

- [x] **Step 1: Record installed CLI versions and non-interactive help**

Run from `src/taxonomy-bench`:

```powershell
codex --version
codex exec --help
codex login status --help
claude --version
claude --help
claude auth status --help
```

Expected: both CLIs exit successfully; the evidence document records versions,
supported model/session/output flags, and the date.

- [x] **Step 2: Capture one harmless machine-readable response per CLI**

Use prompt `Return only {"ok":true}.` with tools disabled, medium effort, and
machine-readable output. This is output-shape characterization, not a benchmark
run. First use `codex login status` and `claude auth status --json` to verify
subscription authentication. In the same temporary PowerShell process that
launches each characterization call, remove the API, auth-token,
alternate-provider, and base-URL environment variables listed in Task 3
without printing their values. Abort rather than call a model if subscription
auth cannot be proven. Do not redirect or commit unsanitized output.

Expected: identify the exact fields carrying final text, session/thread ID,
resolved model or model-usage identity, usage, status, and errors.

- [x] **Step 3: Sanitize the response shapes into test constants**

Create tests with inline JSON/JSONL strings. Replace real session IDs, account
identifiers, request IDs, timestamps, and usage values with obvious fixtures.
Do not commit raw CLI output.

```python
CODEX_SUCCESS_JSONL = """\
{"type":"thread.started","thread_id":"thread_fixture"}
{"type":"turn.completed","model":"gpt-5.6-sol","usage":{"input_tokens":10,"output_tokens":4}}
{"type":"item.completed","item":{"type":"agent_message","text":"{\\"ok\\":true}"}}
"""

CLAUDE_SUCCESS_JSON = {
    "type": "result",
    "result": '{"ok":true}',
    "session_id": "session_fixture",
    "model": "claude-opus-5-fixture",
    "usage": {"input_tokens": 10, "output_tokens": 4},
    "is_error": False,
}
```

Use the actual observed field names. If the installed CLI does not expose a
resolved model, record that as a blocking discovery instead of inferring it
from the requested selector.

- [x] **Step 4: Add fixture-shape tests**

Verify the sanitized Codex lines are individually valid JSON and the sanitized
Claude document is valid JSON. Record examples of malformed output, nonzero
exit, authentication failure, rate limit, unavailable model, fallback/model
mismatch, and missing session ID for Tasks 3 and 4.

Run:

```powershell
python -m pytest tests/test_subscription_cli.py -q
```

Expected: PASS. Do not commit a deliberately failing test between tasks.

- [x] **Step 5: Commit the characterization**

```powershell
git add docs/evidence/wave-1-cli-characterization.md src/taxonomy-bench/tests/test_subscription_cli.py
git commit -m "test: characterize subscription cli output"
```

### Task 2: Extract the Provider Seam

**Files:**

- Create: `src/taxonomy-bench/taxonomy_bench_protocol.py`
- Create: `src/taxonomy-bench/taxonomy_bench_cli.py`
- Modify: `src/taxonomy-bench/taxonomy_bench.py:45-54`
- Modify: `src/taxonomy-bench/taxonomy_bench.py:1229-1251`
- Modify: `src/taxonomy-bench/tests/test_taxonomy_bench.py:143-199`

- [x] **Step 1: Add a failing compatibility test**

```python
def test_provider_types_remain_public():
    assert tb.Provider.__module__ == "taxonomy_bench_cli"
    completion = tb.Completion(text="{}", latency_ms=1.0)
    assert completion.error_kind is None
    assert completion.provider_metadata == {}
```

Run:

```powershell
python -m pytest tests/test_taxonomy_bench.py::test_provider_types_remain_public -q
```

Expected: FAIL because the types still live in `taxonomy_bench` and lack the
new fields.

- [x] **Step 2: Establish one-way imports and protocol ownership**

Move `BASE_INSTRUCTIONS` and `BenchError` into
`taxonomy_bench_protocol.py`. Define canonical JSON/hash helpers there as well.
Define one `compose_subject_prompt(prompt: str) -> str` helper there that joins
the exact base instructions and task prompt for a fresh CLI subject session.
`taxonomy_bench.py`, `taxonomy_bench_cli.py`, and `taxonomy_bench_wave.py`
import from the protocol module. The protocol module imports none of them.

Provider-specific configuration and parse failures use subclasses of
`BenchError` defined in `taxonomy_bench_cli.py`; the CLI module never imports
`taxonomy_bench.py`. Re-export `BASE_INSTRUCTIONS`, `BenchError`, `Provider`,
and `Completion` from `taxonomy_bench.py` for compatibility.

- [x] **Step 3: Move the base types into the CLI module**

Implement and re-export these types from `taxonomy_bench.py`:

```python
@dataclasses.dataclass
class Completion:
    text: str
    latency_ms: float
    resolved_model: str | None = None
    response_id: str | None = None
    request_id: str | None = None
    usage: dict[str, int] = dataclasses.field(default_factory=dict)
    status: str | None = None
    incomplete_reason: str | None = None
    error: str | None = None
    error_kind: str | None = None
    provider_metadata: dict[str, Any] = dataclasses.field(default_factory=dict)


class Provider:
    supports_sessions = False

    def complete(
        self,
        prompt: str,
        output_schema: Mapping[str, Any],
        previous_response_id: str | None = None,
    ) -> Completion:
        raise NotImplementedError
```

Keep `OpenAIProvider`, `CommandProvider`, `OracleProvider`, and external imports
working through `taxonomy_bench.Provider` and `taxonomy_bench.Completion`.

- [x] **Step 4: Persist structured infrastructure metadata**

Extend `_attempt_record()` to include `error_kind` and `provider_metadata`.
Update existing tests to assert backward-compatible empty values.

- [x] **Step 5: Prove the instruction hash has one source**

At this stage, test that `taxonomy_bench.BASE_INSTRUCTIONS` and
`OpenAIProvider` reference the exact
`taxonomy_bench_protocol.BASE_INSTRUCTIONS` value and hash. No existing module
may duplicate the instruction string.

- [x] **Step 6: Run focused and full tests**

```powershell
python -m pytest tests/test_taxonomy_bench.py -q
python -m pytest -q
```

Expected: all current tests plus the compatibility test PASS.

- [x] **Step 7: Commit**

```powershell
git add src/taxonomy-bench/taxonomy_bench_protocol.py src/taxonomy-bench/taxonomy_bench_cli.py src/taxonomy-bench/taxonomy_bench.py src/taxonomy-bench/tests/test_taxonomy_bench.py
git commit -m "refactor: extract provider contract"
```

### Task 3: Implement Claude Code Subscription Provider

**Files:**

- Modify: `src/taxonomy-bench/taxonomy_bench_cli.py`
- Modify: `src/taxonomy-bench/tests/test_subscription_cli.py`

- [x] **Step 1: Add failing Claude command-construction tests**

Assert that a new attempt uses:

- `claude -p`
- `--output-format json`
- `--model <selector>`
- `--effort <effort>`
- `--safe-mode`
- `--tools ""`
- `--no-chrome`
- `--disable-slash-commands`
- `--no-session-persistence` only for ephemeral calibration
- an explicit sterile `cwd`

Assert that a continued retry uses `--resume <task-session-id>` and never
reuses another task's ID.

- [x] **Step 2: Add failing auth and output-parser tests**

`claude auth status --json` must identify Claude subscription authentication.
Reject API/Console billing, unresolved auth, fallback, model mismatch, missing
session IDs for persisted runs, and `is_error=true`.

- [x] **Step 3: Implement an injectable process runner**

```python
@dataclasses.dataclass(frozen=True)
class ProcessResult:
    args: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str
    latency_ms: float


ProcessRunner = Callable[
    [Sequence[str], str, Path, float, Mapping[str, str]],
    ProcessResult,
]
```

The production runner uses `subprocess.run`; tests inject a fake. Resolve the
CLI with `shutil.which()` and pass an argument list, never a shell command
string. Build a minimal inherited environment and explicitly remove API keys,
auth-token overrides, alternate-provider routing, proxy base URLs, and cloud
provider selectors before invoking either CLI.

At minimum, tests require these names to be absent even when present in the
parent process:

```text
OPENAI_API_KEY
CODEX_API_KEY
ANTHROPIC_API_KEY
ANTHROPIC_AUTH_TOKEN
ANTHROPIC_BASE_URL
CLAUDE_CODE_USE_BEDROCK
CLAUDE_CODE_USE_VERTEX
CLAUDE_CODE_USE_FOUNDRY
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
GOOGLE_APPLICATION_CREDENTIALS
AZURE_CLIENT_SECRET
```

Retain only OS/process variables needed to locate the executable, the user's
subscription credential store, and the approved temporary/control roots.

- [x] **Step 4: Implement `ClaudeCliProvider`**

Required public behavior: `ClaudeCliProvider` subclasses `Provider`, sets
`supports_sessions = True` and `family = "claude"`, exposes
`preflight() -> dict[str, Any]`, and implements the existing
`complete(prompt, output_schema, previous_response_id=None) -> Completion`
contract.

Constructor inputs include selector, expected resolved-model pattern, effort,
timeout, subject root, persistence mode, and process runner. Wave 1 supports
prompt output mode only; reject schema mode explicitly.

Use `--safe-mode`, `--strict-mcp-config` with an empty controller-owned MCP
configuration, `--tools ""`, and the sanitized environment. Tests must prove
user settings, plugins, MCP configuration, and API credential variables cannot
enter the child process.

For each fresh subject session, send the exact output of
`taxonomy_bench_protocol.compose_subject_prompt()` through stdin. A continued
retry sends only its retry instruction because the task-local session already
contains the base instructions. Test both cases and assert the provider reports
the shared instruction hash.

- [x] **Step 5: Classify infrastructure errors**

Use stable categories:

```text
authentication
entitlement
rate_limit
timeout
process
malformed_provider_output
model_mismatch
fallback
isolation
```

Do not classify malformed benchmark-answer JSON as infrastructure. That remains
subject output and is scored normally.

- [x] **Step 6: Run tests**

```powershell
python -m pytest tests/test_subscription_cli.py -q
python -m pytest -q
```

Expected: Claude construction, parsing, auth, error, and session tests PASS;
the full suite remains green.

- [x] **Step 7: Commit**

```powershell
git add src/taxonomy-bench/taxonomy_bench_cli.py src/taxonomy-bench/tests/test_subscription_cli.py
git commit -m "feat: add claude subscription provider"
```

### Task 4: Implement Codex Subscription Provider

**Files:**

- Modify: `src/taxonomy-bench/taxonomy_bench_cli.py`
- Modify: `src/taxonomy-bench/tests/test_subscription_cli.py`

- [x] **Step 1: Add failing Codex command-construction tests**

Assert that a new attempt uses:

- `codex exec --json`
- `--model <selector>`
- `--sandbox read-only`
- `--ignore-user-config`
- `--ignore-rules`
- strict configuration disabling shell tools and web search
- `--ephemeral` only for calibration
- `--skip-git-repo-check`
- an explicit sterile `--cd`

Assert that a continued retry uses `codex exec resume <task-thread-id>` with
machine-readable output and the same sterile directory.

- [x] **Step 2: Add failing auth and JSONL parser tests**

`codex login status` must explicitly indicate ChatGPT subscription access.
Reject API-key auth, unresolved auth, fallback, model mismatch, malformed JSONL,
missing final agent text, and missing thread ID for persisted runs.

- [x] **Step 3: Implement `CodexCliProvider`**

`CodexCliProvider` subclasses `Provider`, sets `supports_sessions = True` and
`family = "codex"`, exposes `preflight() -> dict[str, Any]`, and implements the
existing
`complete(prompt, output_schema, previous_response_id=None) -> Completion`
contract.

Parse JSONL by event type, not line position. Preserve the thread ID as
`response_id`, the final agent message as `text`, the provider-reported model
as `resolved_model`, and token data when available.

Use `--ignore-user-config`, `--ignore-rules`, disabled shell/web features, no
MCP configuration, and the same sanitized child environment specified in Task
3. Tests inject forbidden environment variables and assert none reach the fake
process runner.

For each fresh subject session, send the exact output of
`taxonomy_bench_protocol.compose_subject_prompt()` through stdin. Continued
retries send only the retry instruction. Test both cases and assert the
provider reports the shared instruction hash.

- [x] **Step 4: Prove prompt transport is exact**

Test prompts containing newlines, quotes, Unicode, and JSON. The prompt must go
through stdin; it must never be interpolated into a command string.

- [x] **Step 5: Run tests**

```powershell
python -m pytest tests/test_subscription_cli.py -q
python -m pytest -q
```

Expected: Codex and Claude provider tests PASS; the full suite remains green.

- [x] **Step 6: Commit**

```powershell
git add src/taxonomy-bench/taxonomy_bench_cli.py src/taxonomy-bench/tests/test_subscription_cli.py
git commit -m "feat: add codex subscription provider"
```

### Task 5: Add the Wave Provider Factory And Subject-Root Validator

**Files:**

- Modify: `src/taxonomy-bench/taxonomy_bench.py:1951-2023`
- Modify: `src/taxonomy-bench/tests/test_taxonomy_bench.py`
- Modify: `src/taxonomy-bench/tests/test_subscription_cli.py`

- [ ] **Step 1: Keep subscription providers out of generic `run`**

The existing `taxonomy-bench run` command remains limited to `openai` and
`command`. Add a test that generic `run` rejects subscription-provider names
and directs the operator to manifest-bound `taxonomy-bench wave preflight` or
`taxonomy-bench wave run`.

- [x] **Step 2: Implement a manifest-bound provider factory**

Add an internal factory used only by Wave commands. It requires a validated
manifest, lane ID, and subject root, then constructs the matching provider with:

- selector, expected resolved-model rule, and medium effort from the locked
  lane registry;
- prompt output mode and zero transport retries from the locked protocol;
- timeout;
- persistence enabled only for primary continued retries;
- no API key or alternate provider.

Expose `provider_version`, `auth_mode`, `invocation_hash`, and
`tool_policy_hash` for manifest and run metadata.

- [x] **Step 3: Implement manifest-bound subject-root validation**

Resolve repository and subject paths before comparing them. Require the
operator-supplied subject root to:

- already exist as a directory;
- initially be empty before controller initialization;
- resolve outside Cogin after following symlinks and Windows junctions;
- contain no `.git`, `AGENTS.md`, `CLAUDE.md`, private suite, manifest, scorer
  data, or unknown file;
- receive a controller marker bound to the manifest hash after validation.

On resumed runs, accept only that marker and controller-created task
directories. Reject changed markers, unknown entries, symlinked task
directories, repositories, instruction files, and private-suite patterns.

- [x] **Step 4: Add requested/resolved identity assertions**

Before scoring a completion, a subscription provider must return the expected
resolved model. If identity cannot be proven, record `model_mismatch` or
`fallback` and treat the run as infrastructure-invalid.

- [x] **Step 5: Run tests**

```powershell
python -m pytest tests/test_taxonomy_bench.py tests/test_subscription_cli.py -q
python -m pytest -q
```

Expected: generic-run rejection, Wave factory, resolved-path isolation,
manifest marker, identity, and metadata tests PASS.

- [x] **Step 6: Commit**

```powershell
git add src/taxonomy-bench/taxonomy_bench.py src/taxonomy-bench/tests/test_taxonomy_bench.py src/taxonomy-bench/tests/test_subscription_cli.py
git commit -m "feat: add wave provider factory"
```

### Task 6: Implement the Immutable Wave 1 Manifest

**Files:**

- Create: `src/taxonomy-bench/taxonomy_bench_wave.py`
- Create: `src/taxonomy-bench/tests/test_wave_controller.py`

- [x] **Step 1: Add failing protocol and manifest tests**

Assert the built-in Wave 1 protocol contains exactly:

```python
WAVE1_PAIRS = (
    ("claude-opus-5", "codex-gpt-5.6-sol"),
    ("claude-sonnet-5", "codex-gpt-5.6-terra"),
    ("claude-fable-5", "codex-gpt-5.6-luna"),
)
```

Assert medium effort, isolated sessions, prompt output, zero transport retries,
three primary repeats, up to two continued feedback retries, and the strict
pair barrier.

Assert the manifest's base-instruction hash is computed directly from
`taxonomy_bench_protocol.BASE_INSTRUCTIONS`.

- [x] **Step 2: Add deterministic calibration tests**

From the full suite, group tasks by tier, sort each tier's task IDs lexically,
and choose the first two IDs for tiers 1-4. Assert exactly eight unique IDs and
that every selected task belongs to the unchanged full suite.

- [x] **Step 3: Implement canonical hashing**

Use UTF-8 canonical JSON with sorted keys and compact separators. The manifest
contains:

- protocol version and canonical protocol hash;
- full private-suite SHA-256 and suite path;
- eight calibration task IDs;
- base-instruction hash;
- diagnostic-feedback-policy hash;
- provider invocation and tool-policy hashes;
- CLI versions captured at preparation;
- resolved controller-global control-root path;
- lane/pair registry;
- creation timestamp;
- deterministic input fingerprint excluding creation timestamp and manifest
  content hash;
- its own content hash, calculated with that field omitted.

- [x] **Step 4: Make manifest preparation idempotent**

When no manifest exists, compute the deterministic input fingerprint first,
then add `created_at` and the final manifest content hash. When a manifest
exists, recompute and compare only the deterministic input fingerprint. If it
matches, validate the stored content hash and return the existing manifest,
including its original timestamp, unchanged. If it differs, fail with a clear
error. Never overwrite an existing manifest.

- [x] **Step 5: Run tests**

```powershell
python -m pytest tests/test_wave_controller.py -q
```

Expected: protocol, calibration, hashing, tamper, and idempotence tests PASS.

- [x] **Step 6: Commit**

```powershell
git add src/taxonomy-bench/taxonomy_bench_wave.py src/taxonomy-bench/tests/test_wave_controller.py
git commit -m "feat: add wave one manifest"
```

### Task 7: Add Family Locks And Restartable Lane State

**Files:**

- Modify: `src/taxonomy-bench/taxonomy_bench_wave.py`
- Modify: `src/taxonomy-bench/tests/test_wave_controller.py`

- [x] **Step 1: Add failing family-lock tests**

Use the approved controller-global lock directory recorded in the manifest,
not the wave output directory. Test that:

- one Claude lock and one Codex lock may coexist;
- a second lock in the same family fails immediately;
- releasing a lock permits the next process;
- persistent lock files are not deleted.
- separate processes using different wave output directories still contend on
  the same family lock.

- [x] **Step 2: Implement cross-platform advisory locking**

Open one persistent file per family under the manifest's resolved
controller-global control root. Use `msvcrt.locking` on Windows and
`fcntl.flock` on POSIX. Hold the file handle for the whole lane. Do not use
PID-only lock files and do not delete lock files during cleanup.

- [x] **Step 3: Add failing lane-state tests**

State must preserve:

- lane, pair, manifest hash, provider fingerprint, and status;
- calibration run ID;
- completed primary repeat numbers and run IDs;
- current phase;
- abandoned run IDs with infrastructure reason;
- invalidation reason;
- completion timestamp.

Changing the manifest, CLI version, auth mode, requested/resolved model, tool
policy, or invocation hash invalidates continuation.

- [x] **Step 4: Implement atomic state writes**

Write a sibling temporary file, flush and fsync it, then replace `state.json`
with `os.replace()`. This is an atomic update, not destructive cleanup.

- [x] **Step 5: Implement pair barriers**

A lane in Pair N may start only when Pair N-1 has two completed lane states and
an aggregation-complete marker. Pair aggregation may start only when both
current lane states are complete.

- [x] **Step 6: Run tests**

```powershell
python -m pytest tests/test_wave_controller.py -q
```

Expected: lock, state, fingerprint, resume, and pair-barrier tests PASS.

- [x] **Step 7: Commit**

```powershell
git add src/taxonomy-bench/taxonomy_bench_wave.py src/taxonomy-bench/tests/test_wave_controller.py
git commit -m "feat: add restartable wave lane state"
```

### Task 8: Implement Wave Preparation And Calibration Admission

**Files:**

- Modify: `src/taxonomy-bench/taxonomy_bench.py:2048-2203`
- Modify: `src/taxonomy-bench/taxonomy_bench_wave.py`
- Modify: `src/taxonomy-bench/tests/test_wave_controller.py`

- [ ] **Step 1: Add failing `wave prepare` CLI tests**

Command:

```powershell
taxonomy-bench wave prepare `
  --suite suites/taxonomy-v1-seed42.private.json `
  --out wave-runs/wave-1 `
  --control-root C:/operator-approved/cogin-control
```

Expected behavior: validate the full suite, derive calibration IDs, capture
versions and policy hashes, write one immutable manifest, and print its path and
hash. The command requires an existing, explicitly approved control root
outside Cogin and never creates an outside-project root implicitly.

- [ ] **Step 2: Add failing calibration-admission tests**

Calibration passes only when:

- all eight first attempts have durable records;
- all eight are scored;
- latency is present and nonnegative;
- the run's full-suite hash matches the manifest;
- its task IDs exactly match the manifest's ordered eight calibration IDs;
- requested and resolved models match the lane;
- base-instruction, tool-policy, invocation, and CLI-version hashes match the
  manifest;
- no infrastructure, isolation, parser-process, or report failure exists.

Malformed subject-answer JSON remains a scored failure and does not reject
calibration.

- [ ] **Step 3: Implement preparation and admission as pure controller operations**

Manifest preparation does not invoke a model. Calibration admission accepts a
completed calibration run plus the locked manifest and returns a structured
pass/fail result with exact reasons. It does not use score thresholds or
operator judgment.

- [ ] **Step 4: Add manifest-bound `wave preflight`**

Command:

```powershell
taxonomy-bench wave preflight `
  --manifest wave-runs/wave-1/manifest.json `
  --lane claude-opus-5 `
  --subject-root C:/operator-approved/sterile-subjects
```

The command validates the manifest-bound subject-root marker, constructs the
lane through the Wave provider factory, performs subscription/auth/model/tool
preflight, prints only sanitized metadata, and exits without calibration. It is
the only live preflight path for subscription providers.

- [ ] **Step 5: Run tests**

```powershell
python -m pytest tests/test_wave_controller.py -q
python -m pytest -q
```

Expected: manifest CLI, manifest-bound preflight, and calibration-admission
tests PASS.

- [ ] **Step 6: Commit**

```powershell
git add src/taxonomy-bench/taxonomy_bench.py src/taxonomy-bench/taxonomy_bench_wave.py src/taxonomy-bench/tests/test_wave_controller.py
git commit -m "feat: prepare wave one runs"
```

### Task 9: Implement Immediate-Abort Lane Execution

**Files:**

- Modify: `src/taxonomy-bench/taxonomy_bench.py:1463-1576`
- Modify: `src/taxonomy-bench/taxonomy_bench.py:2048-2203`
- Modify: `src/taxonomy-bench/taxonomy_bench_wave.py`
- Modify: `src/taxonomy-bench/tests/test_taxonomy_bench.py`
- Modify: `src/taxonomy-bench/tests/test_wave_controller.py`

- [ ] **Step 1: Add a per-attempt checkpoint seam**

Add an optional callback to `execute_run()` while preserving default behavior:

```python
AttemptCheckpoint = Callable[[str, Mapping[str, Any]], None]
```

The second argument is the current run envelope, created before the first model
call and containing the durable run ID, configuration, task records completed
so far, and current attempt. Invoke the callback immediately after every
attempt is appended.

The Wave callback atomically persists the envelope. When the current attempt
has an infrastructure `error_kind`, it raises `WaveInfrastructureAbort` only
after persistence. `execute_run()` does not catch callback exceptions, so no
later task or retry call occurs. Existing callers pass no callback and retain
their current behavior.

- [ ] **Step 2: Prove immediate abort**

Add tests where authentication fails on first attempt, rate limiting occurs
mid-first-pass, and timeout occurs during recovery. In each case, assert the
fake provider receives no call after the failing attempt and the partial run
record remains durable.

- [ ] **Step 3: Add Wave-only session-identifier redaction**

Add an optional Wave execution setting that keeps response/session identifiers
only while a task can still be retried. After exact first-attempt success or
after that task's final retry, clear `base_previous_response_id` and every
attempt `response_id` before the next durable checkpoint. Before persisting an
abandoned partial run, clear every identifier because that repeat restarts
from scratch.

Generic OpenAI/API runs retain their existing response-ID behavior. Wave runs
may store a one-way session-trace hash for isolation diagnostics, but no
resumable raw identifier may remain in accepted, abandoned, lane-report, or
pair-report artifacts.

Test exact-first success, exhausted retries, early retry success, calibration,
and infrastructure abandonment. Assert finalized Wave artifacts contain no raw
session/thread ID fixture.

- [ ] **Step 4: Add failing `wave run` fake-provider tests**

Command shape:

```powershell
taxonomy-bench wave run `
  --manifest wave-runs/wave-1/manifest.json `
  --lane claude-opus-5 `
  --subject-root C:/operator-approved/sterile-subjects
```

The fake provider must prove:

- calibration runs first;
- repeats 1-3 are sequential;
- every repeat completes all 32 first attempts before its retries;
- exact-success retries stop early;
- task session IDs never cross tasks;
- an infrastructure error saves the run as abandoned and exits nonzero;
- rerun resumes at the abandoned repeat, not at repeat 1;
- calibration is not repeated after a matching successful calibration;
- provider-fingerprint drift invalidates the lane.

- [ ] **Step 5: Implement lane execution**

Acquire the family lock for the whole command. Preflight before calibration and
before a resumed primary sequence. Build a derived calibration view whose tasks
are the manifest's eight IDs while preserving the full-suite hash in run
provenance.

Save private suite copies only in the controller-owned wave directory. Never
copy the private suite or manifest into the subject root.

- [ ] **Step 6: Implement infrastructure restart behavior**

Save an interrupted run under its unique run ID, append it to
`abandoned_run_ids`, and leave completed repeats untouched. Return nonzero.
The next identical command starts that repeat again with a new run ID.

- [ ] **Step 7: Run focused and full tests**

```powershell
python -m pytest tests/test_wave_controller.py tests/test_taxonomy_bench.py -q
python -m pytest -q
```

Expected: all Wave 1 orchestration tests and the full suite PASS.

- [ ] **Step 8: Commit**

```powershell
git add src/taxonomy-bench/taxonomy_bench.py src/taxonomy-bench/taxonomy_bench_wave.py src/taxonomy-bench/tests/test_taxonomy_bench.py src/taxonomy-bench/tests/test_wave_controller.py
git commit -m "feat: execute restartable wave lanes"
```

### Task 10: Publish Lane Reports

**Files:**

- Modify: `src/taxonomy-bench/taxonomy_bench.py:1911-1949`
- Modify: `src/taxonomy-bench/taxonomy_bench_wave.py`
- Modify: `src/taxonomy-bench/tests/test_wave_controller.py`

- [ ] **Step 1: Add failing lane-report tests**

Reject lane completion unless calibration passed and exactly three accepted
primary repeat run IDs exist. Exclude calibration and abandoned runs.

- [ ] **Step 2: Implement lane aggregation**

Load the three accepted primary runs, call `aggregate_matrix()`, and render a
lane-level `lane.json` and `lane.html`. Include the manifest hash, requested and
resolved model identities, CLI version, calibration run ID, accepted run IDs,
and abandoned run IDs.

- [ ] **Step 3: Make lane publication atomic and idempotent**

Group staging attempts under a deterministic transaction key derived from the
manifest and input-run hashes. Each attempt uses a unique child directory.
Atomically rename a fully validated attempt directory to the final lane-report
path. On retry, validate and reuse an existing final directory or valid staging
attempt; if an invalid partial attempt exists, preserve it and create a new
attempt. Never overwrite a conflicting report and never delete abandoned
staging evidence.

- [ ] **Step 4: Mark lane complete only after publication**

The lane state transitions to complete only after the final report directory
and hashes validate.

- [ ] **Step 5: Run tests and commit**

```powershell
python -m pytest tests/test_wave_controller.py -q
python -m pytest -q
git add src/taxonomy-bench/taxonomy_bench.py src/taxonomy-bench/taxonomy_bench_wave.py src/taxonomy-bench/tests/test_wave_controller.py
git commit -m "feat: publish wave lane reports"
```

### Task 11: Implement Single-Owner Pair Aggregation

**Files:**

- Modify: `src/taxonomy-bench/taxonomy_bench.py:1911-1949`
- Modify: `src/taxonomy-bench/taxonomy_bench_wave.py`
- Modify: `src/taxonomy-bench/tests/test_wave_controller.py`

- [ ] **Step 1: Add failing aggregation-barrier tests**

Command:

```powershell
taxonomy-bench wave aggregate --manifest wave-runs/wave-1/manifest.json --pair 1
```

Reject aggregation unless both lane states are complete with three accepted
primary run IDs each. Exclude calibration and abandoned runs.

- [ ] **Step 2: Add a controller-global aggregation lock**

Acquire `pair-N.lock` under the same approved controller-global control root as
the family locks. Test two separate coordinator processes against different
wave working directories; exactly one may own aggregation for the same
manifest and pair.

- [ ] **Step 3: Implement crash-recoverable atomic aggregation**

Load exactly six primary run records and call `aggregate_matrix()`. Derive a
deterministic transaction key from the manifest hash and ordered input run IDs.
Write `matrix.json`, `matrix.html`, and a marker with their hashes into a unique
attempt directory grouped beneath that transaction key.

After every staged file validates, atomically rename the whole staging
attempt to the final pair-report directory. If a crash leaves a valid staging
attempt, the next lock owner promotes it. If it leaves an invalid attempt,
preserve it and create a new unique attempt. If the final directory exists,
validate and return it. Never overwrite a conflicting directory and never
delete crash evidence.

- [ ] **Step 4: Prove Pair N+1 barrier**

After successful aggregation of Pair 1, Pair 2 lanes may start. Before it,
both Pair 2 lane commands must fail without invoking a provider.

- [ ] **Step 5: Run tests**

```powershell
python -m pytest tests/test_wave_controller.py -q
python -m pytest -q
```

Expected: aggregation ownership, crash recovery, idempotence, run selection,
and pair-order tests PASS.

- [ ] **Step 6: Commit**

```powershell
git add src/taxonomy-bench/taxonomy_bench.py src/taxonomy-bench/taxonomy_bench_wave.py src/taxonomy-bench/tests/test_wave_controller.py
git commit -m "feat: aggregate completed wave pairs"
```

### Task 12: Package, Document, Land, And Preflight

**Files:**

- Modify: `src/taxonomy-bench/pyproject.toml`
- Modify: `src/taxonomy-bench/.gitignore`
- Modify: `src/taxonomy-bench/scripts/package-release.ps1`
- Modify: `src/taxonomy-bench/tests/test_taxonomy_bench.py`
- Modify: `src/taxonomy-bench/README.md`
- Modify: `src/taxonomy-bench/BENCHMARK_SPEC.md`
- Modify: `src/taxonomy-bench/VALIDATION.md`
- Modify: `src/taxonomy-bench/SHA256SUMS`
- Modify: `src/taxonomy-bench.zip`
- Modify: `docs/runplans/README.md`
- Modify: `docs/runplans/OPERATOR-PROMPT.md`
- Modify: `docs/INDEX.md`

- [ ] **Step 1: Add new modules to package and release maps**

Add `taxonomy_bench_protocol`, `taxonomy_bench_cli`, and
`taxonomy_bench_wave` to `py-modules`. Include the new modules and test files in
the deterministic release map and packager fixture.

- [ ] **Step 2: Ignore private execution data**

Add:

```gitignore
wave-runs/
.subject-workspaces/
suites/*.private.json
```

Do not ignore public reports or documentation intended for review.

- [ ] **Step 3: Update user documentation**

Document the four Wave commands (`prepare`, `preflight`, `run`, and
`aggregate`), explicit subject-root requirement,
subscription-auth gates, role-matched pairs, infrastructure semantics, and the
fact that results measure CLI session configurations.

Replace the operator prompt's readiness warning with the exact verified
commands. Keep `TARGET_RUNPLAN` as the only routinely edited prompt value.

- [ ] **Step 4: Run the complete local verification**

```powershell
python -m pytest -q
python -m build
python -m pip install --force-reinstall --no-deps dist/taxonomy_bench-0.2.0-py3-none-any.whl
taxonomy-bench --version
taxonomy-bench validate --taxonomy sample_data
```

Expected: all tests PASS, wheel builds and installs, version is 0.2.0, and the
sample taxonomy is valid.

- [ ] **Step 5: Run a fake-CLI Wave 1 smoke test**

Use test-controlled fake `claude` and `codex` executables with the synthetic
suite. Run prepare, one Claude lane and one Codex lane concurrently, then pair
aggregation.

Use pytest-managed `tmp_path` directories for the fake control, subject, and
wave roots. Inject the fake process runner and test-only approval marker; never
read real credential stores or invoke installed CLIs. This automated test
isolation does not authorize or create a live outside-project subject root.

Expected: family concurrency is two, lane states complete, each task-local
session remains isolated, and the pair matrix contains six accepted primary
runs.

- [ ] **Step 6: Regenerate release artifacts**

```powershell
python -m build
pwsh -NoProfile -File scripts/package-release.ps1 `
  -WheelPath dist/taxonomy_bench-0.2.0-py3-none-any.whl `
  -ArchivePath ../taxonomy-bench.zip
```

Expected: every mapped SHA-256 verifies and the archive contains the exact
declared entry set.

- [ ] **Step 7: Final local verification**

Use `@superpowers:verification-before-completion`.

```powershell
python -m pytest -q
git diff --check
git status --short
```

Expected: tests pass, no whitespace errors, and only the intended implementation
and regenerated release artifacts are modified.

- [ ] **Step 8: Commit and land the locally verified implementation**

```powershell
git add src/taxonomy-bench src/taxonomy-bench.zip docs
git commit -m "docs: finalize subscription benchmark workflow"
git push origin main
```

Confirm `origin/main...HEAD` is `0 0`.

Landing occurs before live model preflight. A later-pair entitlement or model
availability issue must not strand the executable Pair 1 implementation.

- [ ] **Step 9: Perform live preflight as a separate operational milestone**

Obtain explicit operator approval for the exact sterile subject root and
controller-global control root outside Cogin. Then run preflight—not
calibration—for the six selectors in pair order.

Use the manifest-bound command from Task 8 for each lane:

```powershell
taxonomy-bench wave preflight `
  --manifest wave-runs/wave-1/manifest.json `
  --lane claude-opus-5 `
  --subject-root C:/operator-approved/sterile-subjects
```

Stop a lane on unavailable model, unprovable resolved model, API billing route,
or fallback. Do not weaken the gate. A failure blocks that lane's experiment,
not the already-landed implementation.

- [ ] **Step 10: Commit sanitized preflight evidence when available**

Record requested/resolved model, auth mode, CLI version, tool policy, invocation
hash, and any blocked lane in `VALIDATION.md`. Do not commit raw CLI output,
account identifiers, outside paths that reveal secrets, or subject session
state.

```powershell
git add src/taxonomy-bench/VALIDATION.md
git commit -m "docs: record subscription cli preflight"
git push origin main
```

## Completion Gate

Implementation is ready for the first calibration pair only when:

- all automated and packaging checks pass;
- both live CLI preflights prove subscription auth and resolved model identity;
- the operator has approved an exact sterile subject-root path outside Cogin;
- the immutable manifest is prepared from the real 32-task private suite;
- Opus 5 and Sol lane commands both pass preflight against the same manifest.

Then use `docs/runplans/OPERATOR-PROMPT.md` in two fresh top-level operator
sessions, targeting:

- `docs/runplans/claude-opus-5.md`
- `docs/runplans/codex-gpt-5.6-sol.md`

Do not start Pair 2 until Pair 1 has two completed lane states and one
coordinator-owned aggregation marker.

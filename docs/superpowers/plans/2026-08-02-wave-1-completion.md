# Wave 1 Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the already-landed Wave 1 provider and controller library into
executable `wave` CLI commands with immediate-abort execution, lane reports,
pair aggregation, packaging, and live preflight.

**Architecture:** All new orchestration logic lives in
`taxonomy_bench_wave.py`; `taxonomy_bench.py` gains only the `wave` argparse
subcommands and a per-attempt checkpoint seam in `execute_run()`. Providers in
`taxonomy_bench_cli.py` are complete and must not change. Scoring and report
rendering stay in `taxonomy_bench.py`.

**Tech Stack:** Python 3.10+, standard library, pytest, Claude Code CLI, Codex
CLI, PowerShell release packaging.

---

## Governing Documents

- Design:
  `docs/superpowers/specs/2026-07-25-subscription-cli-benchmark-design.md`
- Superseded plan (Tasks 8-12): `docs/NEXT-STEPS.md` — its Non-Negotiable
  Boundaries section still applies verbatim to every task below.
- Shared protocol: `docs/runplans/README.md`
- Operator prompt: `docs/runplans/OPERATOR-PROMPT.md`

## Verified Starting State (2026-08-02)

- Commit `f4fe7be` on `main`; 155 tests pass.
- `taxonomy_bench_cli.py`: `ClaudeCliProvider` and `CodexCliProvider` with
  `preflight()`, `_sanitized_env()`, injectable `ProcessRunner`, session
  continuation, and error classification — complete.
- `taxonomy_bench_wave.py`: `WAVE1_PROTOCOL`, `WAVE1_PAIRS`, `WAVE1_LANES`,
  `prepare_manifest()`, `deterministic_calibration_ids()`,
  `compute_suite_sha256()`, `FamilyLock`, `LaneState`, `pair_can_start()`,
  `pair_can_aggregate()`, `record_aggregation()`, and `WaveController`
  (`_validate_manifest`, `validate_subject_root`, `build_provider`) — complete.
- Missing: everything below. `taxonomy_bench.py` contains no reference to the
  wave module; `tests/test_wave_controller.py::TestCalibrationAdmission` is an
  empty stub; `pyproject.toml` `py-modules` lists only the three original
  modules; `SHA256SUMS` has the pre-wave 18-entry map.

## Operator Preconditions (needed for Task 9 only; Tasks 1-8 are code-only)

1. Upstream Marble taxonomy checkout (https://github.com/withmarbleapp/os-taxonomy)
   provided by the operator; used to generate the real 32-task private suite.
2. Operator-approved sterile subject root outside the Cogin repository.
3. Operator-approved controller-global control root outside the Cogin
   repository.

---

## Implementation Tasks

### Task 1: Reject Subscription Providers In Generic `run`

**Files:**

- Modify: `src/taxonomy-bench/taxonomy_bench.py` (provider construction in the
  `run` command path, near `_build_provider`/`cmd_run`)
- Modify: `src/taxonomy-bench/tests/test_taxonomy_bench.py`

- [x] **Step 1: Write the failing test**

```python
def test_generic_run_rejects_subscription_providers():
    for name in ("claude-cli", "codex-cli"):
        with pytest.raises(tb.BenchError) as exc:
            tb.build_run_provider(provider=name, model="x", effort="medium")
        assert "wave" in str(exc.value).lower()
```

Adapt the call target to the actual provider-construction function in
`taxonomy_bench.py`; the assertion is that subscription provider names raise
`BenchError` whose message directs the operator to
`taxonomy-bench wave preflight` / `taxonomy-bench wave run`.

- [x] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_taxonomy_bench.py::test_generic_run_rejects_subscription_providers -q`
Expected: FAIL (no rejection exists today).

- [x] **Step 3: Implement the rejection**

In the generic provider-construction branch, before any other dispatch:

```python
if provider in ("claude-cli", "codex-cli"):
    raise BenchError(
        f"Provider '{provider}' is manifest-bound. Use "
        "'taxonomy-bench wave preflight' or 'taxonomy-bench wave run'."
    )
```

- [x] **Step 4: Run the full suite**

Run: `python -m pytest -q` — Expected: 156 PASS.

- [x] **Step 5: Commit**

```powershell
git add src/taxonomy-bench/taxonomy_bench.py src/taxonomy-bench/tests/test_taxonomy_bench.py
git commit -m "feat: reject subscription providers in generic run"
```

### Task 2: Calibration Admission Gate

**Files:**

- Modify: `src/taxonomy-bench/taxonomy_bench_wave.py`
- Modify: `src/taxonomy-bench/tests/test_wave_controller.py` (replace the
  `TestCalibrationAdmission` stub)

- [x] **Step 1: Write failing admission tests**

Build a passing fixture run record, then break one property per test:

```python
def _calibration_run(manifest, lane_id="claude-opus-5"):
    return {
        "suite_sha256": manifest["suite_sha256"],
        "task_ids": list(manifest["calibration_ids"]),
        "lane": lane_id,
        "requested_model": "claude-opus-5",
        "resolved_model": "claude-opus-5",
        "base_instruction_hash": manifest["base_instruction_hash"],
        "tool_policy_hash": manifest["tool_policy_hash"],
        "invocation_hash": manifest["invocation_hash"],
        "cli_versions": manifest["cli_versions"],
        "attempts": [
            {"task_id": tid, "scored": True, "latency_ms": 12.0, "error_kind": None}
            for tid in manifest["calibration_ids"]
        ],
    }


class TestCalibrationAdmission:
    def test_admits_complete_calibration(self, manifest):
        result = wave.admit_calibration(_calibration_run(manifest), manifest, "claude-opus-5")
        assert result.passed and result.reasons == ()

    def test_rejects_missing_attempt(self, manifest): ...      # 7 attempts -> fail
    def test_rejects_unscored_attempt(self, manifest): ...     # scored=False -> fail
    def test_rejects_negative_latency(self, manifest): ...
    def test_rejects_suite_hash_mismatch(self, manifest): ...
    def test_rejects_task_id_order_mismatch(self, manifest): ...
    def test_rejects_resolved_model_mismatch(self, manifest): ...
    def test_rejects_hash_drift(self, manifest): ...           # each of the four hashes
    def test_rejects_infrastructure_error(self, manifest): ... # error_kind="rate_limit"
    def test_malformed_subject_json_still_admits(self, manifest): ...
```

The last test sets an attempt's scored answer to malformed JSON while keeping
`scored=True, error_kind=None` — admission must still pass, because malformed
subject output is a scored model outcome, not an infrastructure failure.

- [x] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_wave_controller.py::TestCalibrationAdmission -q`
Expected: FAIL with `AttributeError: ... has no attribute 'admit_calibration'`.

- [x] **Step 3: Implement `admit_calibration`**

```python
@dataclasses.dataclass(frozen=True)
class AdmissionResult:
    passed: bool
    reasons: tuple[str, ...]


def admit_calibration(
    run_record: Mapping[str, Any],
    manifest: Mapping[str, Any],
    lane_id: str,
) -> AdmissionResult:
    reasons: list[str] = []
    lane = manifest["lanes"][lane_id]
    attempts = run_record.get("attempts", [])
    cal_ids = list(manifest["calibration_ids"])
    if [a["task_id"] for a in attempts] != cal_ids:
        reasons.append("task_ids_mismatch")
    if len(attempts) != len(cal_ids):
        reasons.append("attempt_count")
    for a in attempts:
        if not a.get("scored"):
            reasons.append(f"unscored:{a['task_id']}")
        if a.get("latency_ms") is None or a["latency_ms"] < 0:
            reasons.append(f"latency:{a['task_id']}")
        if a.get("error_kind"):
            reasons.append(f"infrastructure:{a['task_id']}:{a['error_kind']}")
    if run_record.get("suite_sha256") != manifest["suite_sha256"]:
        reasons.append("suite_hash_mismatch")
    if run_record.get("resolved_model") != lane["expected_model"]:
        reasons.append("resolved_model_mismatch")
    if run_record.get("requested_model") != lane["selector"]:
        reasons.append("requested_model_mismatch")
    for key in ("base_instruction_hash", "tool_policy_hash", "invocation_hash"):
        if run_record.get(key) != manifest[key]:
            reasons.append(f"{key}_mismatch")
    if run_record.get("cli_versions") != manifest["cli_versions"]:
        reasons.append("cli_version_mismatch")
    return AdmissionResult(passed=not reasons, reasons=tuple(sorted(set(reasons))))
```

Adjust field names to the actual manifest keys produced by
`prepare_manifest()` — read that function first; do not invent parallel names.
No score thresholds, no operator judgment: structural checks only.

- [x] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_wave_controller.py -q` — Expected: PASS.

- [x] **Step 5: Commit**

```powershell
git add src/taxonomy-bench/taxonomy_bench_wave.py src/taxonomy-bench/tests/test_wave_controller.py
git commit -m "feat: add calibration admission gate"
```

### Task 3: `wave prepare` And `wave preflight` CLI Commands

**Files:**

- Modify: `src/taxonomy-bench/taxonomy_bench.py` (argparse wiring + two command
  functions)
- Modify: `src/taxonomy-bench/tests/test_wave_controller.py`

- [x] **Step 1: Write failing CLI tests**

```python
def test_wave_prepare_writes_manifest(tmp_path, capsys):
    suite_path = _write_fake_suite(tmp_path)
    control = tmp_path / "control"; control.mkdir()
    out = tmp_path / "wave-1"
    rc = tb.main([
        "wave", "prepare",
        "--suite", str(suite_path),
        "--out", str(out),
        "--control-root", str(control),
    ])
    assert rc == 0
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["manifest_hash"] in capsys.readouterr().out


def test_wave_prepare_requires_existing_control_root(tmp_path):
    rc-or-raises: control root that does not exist -> nonzero exit, no manifest,
    and no directory creation outside --out.


def test_wave_prepare_is_idempotent(tmp_path):
    run prepare twice -> identical manifest bytes, original created_at retained.


def test_wave_preflight_uses_provider_preflight(tmp_path, monkeypatch, capsys):
    prepare a manifest, create sterile subject root, monkeypatch
    WaveController.build_provider to return a fake whose preflight() returns
    {"auth_mode": "subscription", "resolved_model": "claude-opus-5"}.
    rc == 0 and sanitized fields appear in stdout; no raw session IDs printed.
```

Use `tb.main(argv)` (or the actual entry function) so tests never spawn a real
process. If `main()` currently calls `sys.exit`, capture `SystemExit.code`.

- [x] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_wave_controller.py -q -k "wave_prepare or wave_preflight"`
Expected: FAIL — argparse rejects the unknown `wave` command.

- [x] **Step 3: Wire the `wave` subparser group**

```python
wave_parser = subparsers.add_parser("wave", help="Wave 1 subscription benchmark controller")
wave_sub = wave_parser.add_subparsers(dest="wave_command", required=True)

prepare = wave_sub.add_parser("prepare")
prepare.add_argument("--suite", required=True, type=Path)
prepare.add_argument("--out", required=True, type=Path)
prepare.add_argument("--control-root", required=True, type=Path)

preflight = wave_sub.add_parser("preflight")
preflight.add_argument("--manifest", required=True, type=Path)
preflight.add_argument("--lane", required=True)
preflight.add_argument("--subject-root", required=True, type=Path)
```

`cmd_wave_prepare`: fail if the control root does not already exist (never
create an outside-project path); load and validate the suite; build the
provider-metadata dict (instruction hash from
`taxonomy_bench_protocol.BASE_INSTRUCTIONS`, invocation and tool-policy hashes
from the provider classes, CLI versions via `shutil.which` + `--version`
capture through the injectable runner); call `wave.prepare_manifest(...)`;
print the manifest path and `manifest_hash`.

`cmd_wave_preflight`: construct `WaveController`, call
`validate_subject_root()`, `build_provider(lane)`, then `provider.preflight()`;
print only sanitized metadata (auth mode, requested/resolved model, CLI
version, tool policy); exit nonzero on any preflight failure. This is the only
live preflight path for subscription providers.

- [x] **Step 4: Run focused and full tests**

Run: `python -m pytest tests/test_wave_controller.py -q` then `python -m pytest -q`
Expected: PASS.

- [x] **Step 5: Commit**

```powershell
git add src/taxonomy-bench/taxonomy_bench.py src/taxonomy-bench/tests/test_wave_controller.py
git commit -m "feat: add wave prepare and preflight commands"
```

### Task 4: Per-Attempt Checkpoint Seam And Immediate Abort

**Files:**

- Modify: `src/taxonomy-bench/taxonomy_bench.py` (`execute_run()`)
- Modify: `src/taxonomy-bench/taxonomy_bench_wave.py`
- Modify: `src/taxonomy-bench/tests/test_taxonomy_bench.py`
- Modify: `src/taxonomy-bench/tests/test_wave_controller.py`

- [x] **Step 1: Write failing checkpoint tests**

```python
def test_execute_run_invokes_checkpoint_after_each_attempt():
    seen = []
    def checkpoint(run_id, envelope):
        seen.append(len(envelope["tasks"]))
    tb.execute_run(..., attempt_checkpoint=checkpoint)
    assert seen  # called once per appended attempt, envelope grows monotonically


def test_wave_checkpoint_aborts_on_infrastructure_error():
    provider = FakeProvider(fail_on=2, error_kind="rate_limit")
    with pytest.raises(wave.WaveInfrastructureAbort):
        tb.execute_run(..., attempt_checkpoint=wave_checkpoint)
    assert provider.calls == 2          # nothing after the failing attempt
    assert persisted_envelope_exists()  # durable before the raise
```

Cover three failure points: authentication on the first attempt, rate limit
mid-first-pass, timeout during recovery.

- [x] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_taxonomy_bench.py -q -k checkpoint`
Expected: FAIL — `execute_run()` has no `attempt_checkpoint` parameter.

- [x] **Step 3: Implement the seam**

```python
AttemptCheckpoint = Callable[[str, Mapping[str, Any]], None]

def execute_run(..., attempt_checkpoint: AttemptCheckpoint | None = None) -> ...:
```

Create the run envelope (durable run ID, configuration, completed task
records, current attempt) before the first model call. Immediately after every
attempt is appended, invoke the callback. `execute_run()` must not catch
callback exceptions. Existing callers pass no callback and keep current
behavior byte-for-byte.

In `taxonomy_bench_wave.py`:

```python
class WaveInfrastructureAbort(BenchError):
    def __init__(self, error_kind: str, run_id: str) -> None:
        super().__init__(f"infrastructure {error_kind} in run {run_id}")
        self.error_kind = error_kind
        self.run_id = run_id


def make_wave_checkpoint(state_dir: Path) -> AttemptCheckpoint:
    def checkpoint(run_id: str, envelope: Mapping[str, Any]) -> None:
        _atomic_write_json(state_dir / f"{run_id}.envelope.json", envelope)
        last = envelope["tasks"][-1]["attempts"][-1]
        if last.get("error_kind"):
            raise WaveInfrastructureAbort(last["error_kind"], run_id)
    return checkpoint
```

Reuse the existing atomic-write helper from `LaneState.save()` (tmp file →
flush → fsync → `os.replace`); extract it to a module-level
`_atomic_write_json()` if it is currently inline.

- [x] **Step 4: Run focused and full tests**

Run: `python -m pytest tests/test_taxonomy_bench.py tests/test_wave_controller.py -q` then `python -m pytest -q`
Expected: PASS.

- [x] **Step 5: Commit**

```powershell
git add src/taxonomy-bench/taxonomy_bench.py src/taxonomy-bench/taxonomy_bench_wave.py src/taxonomy-bench/tests/test_taxonomy_bench.py src/taxonomy-bench/tests/test_wave_controller.py
git commit -m "feat: add per-attempt checkpoint with immediate abort"
```

### Task 5: Wave Session-Identifier Redaction

**Files:**

- Modify: `src/taxonomy-bench/taxonomy_bench_wave.py`
- Modify: `src/taxonomy-bench/tests/test_wave_controller.py`

- [x] **Step 1: Write failing redaction tests**

Cover five cases: exact first-attempt success, exhausted retries, early retry
success, calibration (always ephemeral), and infrastructure abandonment. In
each, assert the finalized envelope contains no raw `response_id` or
`base_previous_response_id` fixture string, and that a one-way
`session_trace_hash` (SHA-256 of the raw ID) is present where an ID existed.
While a task can still be retried, its identifiers must survive.

- [x] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_wave_controller.py -q -k redact`
Expected: FAIL — function does not exist.

- [x] **Step 3: Implement redaction**

```python
def redact_task_sessions(task_record: MutableMapping[str, Any], *, final: bool) -> None:
    """Clear resumable identifiers once a task's retry window is closed."""
    if not final:
        return
    for attempt in task_record.get("attempts", []):
        raw = attempt.pop("response_id", None)
        if raw:
            attempt["session_trace_hash"] = hashlib.sha256(raw.encode()).hexdigest()
    task_record.pop("base_previous_response_id", None)
```

Call it from the wave checkpoint when a task reaches exact success or its
final retry, and over every task before persisting an abandoned envelope
(abandoned repeats restart from scratch, so nothing resumable may remain).
Generic OpenAI/API runs keep their existing response-ID behavior untouched.

- [x] **Step 4: Run tests and commit**

```powershell
python -m pytest tests/test_wave_controller.py -q
python -m pytest -q
git add src/taxonomy-bench/taxonomy_bench_wave.py src/taxonomy-bench/tests/test_wave_controller.py
git commit -m "feat: redact wave session identifiers"
```

### Task 6: `wave run` Lane Execution

**Files:**

- Modify: `src/taxonomy-bench/taxonomy_bench.py` (add `run` to the `wave`
  subparser; `cmd_wave_run`)
- Modify: `src/taxonomy-bench/taxonomy_bench_wave.py` (`WaveController.run_lane`)
- Modify: `src/taxonomy-bench/tests/test_wave_controller.py`

- [x] **Step 1: Write failing fake-provider lane tests**

Command shape under test (via `tb.main`, fake provider injected through a
`WaveController` seam — add a `provider_factory` constructor argument that
defaults to `build_provider`):

```powershell
taxonomy-bench wave run `
  --manifest wave-runs/wave-1/manifest.json `
  --lane claude-opus-5 `
  --subject-root <tmp sterile root>
```

The fake provider must prove, one test each:

- calibration runs first and uses exactly the manifest's eight ordered IDs;
- repeats 1-3 are sequential; every repeat completes all 32 first attempts
  before its retries; exact-success retries stop early;
- task session IDs never cross tasks;
- an infrastructure error persists the run as abandoned
  (`abandoned_run_ids` grows, envelope durable) and the command exits nonzero;
- rerunning the identical command resumes at the abandoned repeat with a new
  run ID, not at repeat 1;
- calibration is not repeated after a matching successful calibration;
- provider-fingerprint drift (changed invocation hash) invalidates the lane
  via `LaneState.validate_continuation`;
- the family lock is held for the whole command (a second controller in the
  same family fails immediately while the first runs).

- [x] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_wave_controller.py -q -k wave_run`
Expected: FAIL.

- [x] **Step 3: Implement `WaveController.run_lane`**

Order of operations:

1. `FamilyLock(control_root, family)` — hold for the entire command.
2. `pair_can_start(...)` barrier check; fail before any provider call.
3. Load or initialize `LaneState`; `validate_continuation` on resume.
4. `validate_subject_root()`; provider `preflight()` (both on fresh and
   resumed sequences).
5. If no admitted calibration run ID in state: build a derived calibration
   view whose tasks are the manifest's eight IDs while run provenance records
   the full-suite hash; run it with an ephemeral (non-persistent) provider;
   apply `admit_calibration`; on failure, record the invalidation reason and
   exit nonzero.
6. Run primary repeats `1..3` sequentially with a persistent provider and
   `make_wave_checkpoint`. On `WaveInfrastructureAbort`: append the run ID to
   `state.abandoned_run_ids` with its `error_kind`, redact, save state, return
   nonzero. On success: append to `state.completed_run_ids` (the same field
   Task 7 reads), save state.
7. Save private-suite copies only in the controller-owned wave directory;
   never write the suite or manifest into the subject root.

`cmd_wave_run` is a thin wrapper: parse args, construct the controller, return
`controller.run_lane(lane_id)`.

- [x] **Step 4: Run focused and full tests**

Run: `python -m pytest tests/test_wave_controller.py tests/test_taxonomy_bench.py -q` then `python -m pytest -q`
Expected: PASS.

- [x] **Step 5: Commit**

```powershell
git add src/taxonomy-bench/taxonomy_bench.py src/taxonomy-bench/taxonomy_bench_wave.py src/taxonomy-bench/tests/test_wave_controller.py
git commit -m "feat: execute restartable wave lanes"
```

### Task 7: Lane Report Publication

**Files:**

- Modify: `src/taxonomy-bench/taxonomy_bench_wave.py`
- Modify: `src/taxonomy-bench/tests/test_wave_controller.py`

- [x] **Step 1: Write failing lane-report tests**

- publication refuses unless calibration passed and exactly three accepted
  primary run IDs exist (calibration and abandoned runs excluded);
- `lane.json` includes manifest hash, requested and resolved model, CLI
  version, calibration run ID, accepted run IDs, abandoned run IDs;
- rerunning publication with the same inputs reuses the existing final
  directory (idempotent); a conflicting existing directory is never
  overwritten; an invalid partial staging attempt is preserved and a new
  attempt directory is created;
- lane state transitions to `complete` only after the final directory and
  hashes validate.

- [x] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_wave_controller.py -q -k lane_report`
Expected: FAIL.

- [x] **Step 3: Implement atomic staged publication**

```python
def publish_lane_report(state: LaneState, manifest, wave_dir: Path) -> Path:
    runs = [_load_run(wave_dir, rid) for rid in state.completed_run_ids]
    matrix = aggregate_matrix(runs)                    # from taxonomy_bench
    txn_key = canonical_hash({"manifest": manifest["manifest_hash"],
                              "runs": sorted(state.completed_run_ids)})
    staging_root = wave_dir / "staging" / f"lane-{state.lane}" / txn_key
    final = wave_dir / "reports" / f"lane-{state.lane}"
    if final.exists():
        _validate_report_dir(final); return final
    attempt = staging_root / uuid.uuid4().hex
    attempt.mkdir(parents=True)
    (attempt / "lane.json").write_text(canonical_json(payload), encoding="utf-8")
    (attempt / "lane.html").write_text(render_lane_html(payload), encoding="utf-8")
    _validate_report_dir(attempt)
    final.parent.mkdir(parents=True, exist_ok=True)
    attempt.replace(final)                             # atomic promote
    return final
```

Reuse the existing HTML rendering path in `taxonomy_bench.py` /
`taxonomy_bench_report.py` for `lane.html`; do not write a second renderer.
Never delete abandoned staging attempts.

- [x] **Step 4: Run tests and commit**

```powershell
python -m pytest tests/test_wave_controller.py -q
python -m pytest -q
git add src/taxonomy-bench/taxonomy_bench_wave.py src/taxonomy-bench/tests/test_wave_controller.py
git commit -m "feat: publish wave lane reports"
```

### Task 8: `wave aggregate` Pair Aggregation

**Files:**

- Modify: `src/taxonomy-bench/taxonomy_bench.py` (add `aggregate` to the
  `wave` subparser)
- Modify: `src/taxonomy-bench/taxonomy_bench_wave.py`
- Modify: `src/taxonomy-bench/tests/test_wave_controller.py`

- [x] **Step 1: Write failing aggregation tests**

Command: `taxonomy-bench wave aggregate --manifest <path> --pair 1`

- rejects unless both lane states are complete with three accepted primary
  run IDs each (uses existing `pair_can_aggregate`);
- acquires `pair-N.lock` under the manifest's control root; two coordinator
  processes against different wave directories — exactly one owns aggregation
  (test with the same `FamilyLock` mechanism, distinct lock name);
- loads exactly six primary runs, writes `matrix.json`, `matrix.html`, and a
  hash marker in a unique staging attempt under a deterministic transaction
  key, then atomically promotes;
- a valid crashed staging attempt is promoted by the next lock owner; an
  invalid one is preserved and a fresh attempt created; an existing final
  directory is validated and returned;
- after Pair 1 aggregation, `pair_can_start` admits Pair 2 lanes; before it,
  both Pair 2 lane commands fail without invoking a provider.

- [x] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_wave_controller.py -q -k aggregate`
Expected: FAIL.

- [x] **Step 3: Implement aggregation**

Mirror Task 7's staging/promote pattern with a `PairLock` (same
`msvcrt`/`fcntl` advisory mechanism as `FamilyLock`, file
`pair-{n}.lock` in the control root). After promotion call the existing
`record_aggregation(control_root, manifest_hash, pair_index)` so the
Pair N+1 barrier opens. Use `aggregate_matrix()` from `taxonomy_bench.py` on
the six accepted runs; exclude calibration and abandoned runs.

- [x] **Step 4: Run tests and commit**

```powershell
python -m pytest tests/test_wave_controller.py -q
python -m pytest -q
git add src/taxonomy-bench/taxonomy_bench.py src/taxonomy-bench/taxonomy_bench_wave.py src/taxonomy-bench/tests/test_wave_controller.py
git commit -m "feat: aggregate completed wave pairs"
```

### Task 9: Fake-CLI End-To-End Smoke Test

**Files:**

- Modify: `src/taxonomy-bench/tests/test_wave_controller.py`

- [x] **Step 1: Write the end-to-end test**

Using pytest `tmp_path` for control, subject, and wave roots, a synthetic
suite, and injected fake process runners for both families (never real CLIs or
credential stores):

1. `wave prepare` → manifest written;
2. one Claude lane and one Codex lane run concurrently
   (`concurrent.futures.ThreadPoolExecutor`, two workers) — both complete;
   family concurrency is exactly two;
3. each task-local session stays isolated (fake runner records session IDs);
4. `wave aggregate --pair 1` → pair matrix contains six accepted primary runs.

- [x] **Step 2: Run the test and the full suite**

Run: `python -m pytest tests/test_wave_controller.py -q` then `python -m pytest -q`
Expected: PASS. Fix integration seams here rather than weakening assertions.

- [x] **Step 3: Commit**

```powershell
git add src/taxonomy-bench/tests/test_wave_controller.py
git commit -m "test: add fake-cli wave end-to-end smoke"
```

### Task 10: Packaging, Documentation, And Release

**Files:**

- Modify: `src/taxonomy-bench/pyproject.toml`
- Modify: `src/taxonomy-bench/.gitignore`
- Modify: `src/taxonomy-bench/scripts/package-release.ps1`
- Modify: `src/taxonomy-bench/tests/test_taxonomy_bench.py` (packager fixture)
- Modify: `src/taxonomy-bench/README.md`
- Modify: `src/taxonomy-bench/BENCHMARK_SPEC.md`
- Modify: `src/taxonomy-bench/SHA256SUMS`
- Modify: `src/taxonomy-bench.zip`
- Modify: `docs/runplans/README.md`
- Modify: `docs/runplans/OPERATOR-PROMPT.md`
- Modify: `docs/INDEX.md`

- [x] **Step 1: Bump version and extend the package map**

In `pyproject.toml`: version `0.2.0` → `0.3.0`;
`py-modules = ["taxonomy_bench", "taxonomy_bench_progression", "taxonomy_bench_report", "taxonomy_bench_protocol", "taxonomy_bench_cli", "taxonomy_bench_wave"]`.
Add the three modules plus `tests/test_subscription_cli.py` and
`tests/test_wave_controller.py` to the deterministic release map in
`package-release.ps1` and its packager fixture test.

- [x] **Step 2: Ignore private execution data**

Append to `src/taxonomy-bench/.gitignore` (keep the existing
`suites/*.private.json` line):

```gitignore
wave-runs/
.subject-workspaces/
```

- [x] **Step 3: Update documentation**

`README.md` + `BENCHMARK_SPEC.md`: document the four `wave` commands
(`prepare`, `preflight`, `run`, `aggregate`), the explicit subject-root and
control-root requirements, subscription-auth gates, role-matched pairs,
infrastructure semantics, and that results measure CLI session configurations
— not raw models. `docs/runplans/OPERATOR-PROMPT.md`: replace the readiness
warning with the exact verified commands; keep `TARGET_RUNPLAN` as the only
routinely edited value. Add the new plan to `docs/INDEX.md`.

- [x] **Step 4: Full local verification and release regeneration**

```powershell
python -m pytest -q
python -m build
python -m pip install --force-reinstall --no-deps dist/taxonomy_bench-0.3.0-py3-none-any.whl
taxonomy-bench --version
taxonomy-bench validate --taxonomy sample_data
pwsh -NoProfile -File scripts/package-release.ps1 `
  -WheelPath dist/taxonomy_bench-0.3.0-py3-none-any.whl `
  -ArchivePath ../taxonomy-bench.zip
```

Expected: all tests pass, version reports 0.3.0, sample taxonomy valid, every
mapped SHA-256 verifies, archive contains the exact declared entry set.

- [x] **Step 5: Verify, commit, and land**

Use `superpowers:verification-before-completion`, then:

```powershell
python -m pytest -q
git diff --check
git add src/taxonomy-bench src/taxonomy-bench.zip docs
git commit -m "feat: complete wave one controller cli and release"
git push origin main
```

Landing occurs before live preflight — a later entitlement or model
availability issue must not strand the executable implementation.

### Task 11: Live Preflight (Operational Milestone — Blocked On Operator)

**Do not start until the operator provides, in chat:**

1. the upstream Marble taxonomy checkout location;
2. the exact approved sterile subject-root path outside Cogin;
3. the exact approved controller-global control-root path outside Cogin.

- [x] **Step 1: Generate the real private suite and prepare the manifest**

```powershell
taxonomy-bench generate --taxonomy <upstream-checkout> --seed 42 --out suites/
taxonomy-bench wave prepare `
  --suite suites/taxonomy-v1-seed42.private.json `
  --out wave-runs/wave-1 `
  --control-root <approved-control-root>
```

Adapt `generate` flags to the actual CLI; the suite must be the full 32-task
private suite and must remain uncommitted (`suites/*.private.json` is
ignored).

- [x] **Step 2: Preflight all six lanes in pair order**

```powershell
taxonomy-bench wave preflight `
  --manifest wave-runs/wave-1/manifest.json `
  --lane claude-opus-5 `
  --subject-root <approved-subject-root>
```

Repeat for `codex-gpt-5.6-sol`, `claude-sonnet-5`, `codex-gpt-5.6-terra`,
`claude-fable-5`, `codex-gpt-5.6-luna`. Stop a lane on unavailable model,
unprovable resolved model, API billing route, or fallback. Do not weaken the
gate; a blocked lane blocks that experiment, not the landed implementation.

- [x] **Step 3: Record sanitized evidence in `VALIDATION.md` and land it**

Record requested/resolved model, auth mode, CLI version, tool policy,
invocation hash, and any blocked lane. No raw CLI output, account
identifiers, secret-revealing paths, or subject session state.

```powershell
git add src/taxonomy-bench/VALIDATION.md
git commit -m "docs: record subscription cli preflight"
git push origin main
```

## Completion Gate (unchanged from the original plan)

Ready for the first calibration pair only when: all automated and packaging
checks pass; both Pair 1 live preflights prove subscription auth and resolved
model identity; the manifest is prepared from the real 32-task private suite;
and the operator has approved the sterile subject root. Then use
`docs/runplans/OPERATOR-PROMPT.md` in two fresh operator sessions targeting
`docs/runplans/claude-opus-5.md` and `docs/runplans/codex-gpt-5.6-sol.md`. Do
not start Pair 2 until Pair 1 has two completed lane states and one
coordinator-owned aggregation marker.

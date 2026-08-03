"""Wave 1 controller tests with fake providers."""

from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path

import pytest

import taxonomy_bench as tb
import taxonomy_bench_cli
import taxonomy_bench_protocol
import taxonomy_bench_wave as wave
from taxonomy_bench_cli import Completion, ProcessResult
from taxonomy_bench_protocol import BASE_INSTRUCTIONS, BenchError, canonical_hash
from test_taxonomy_bench import correct_answer

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_suite(tasks_per_tier: int = 4) -> dict:
    """Create a synthetic suite for testing wave operations."""
    taxonomy = tb.Taxonomy.load(
        Path(__file__).resolve().parents[0].parent / "sample_data"
    )
    return tb.SuiteGenerator(taxonomy, seed=42).generate(
        max_tier=8, tasks_per_tier=tasks_per_tier
    )


def _fake_runner(stdout: str, returncode: int = 0):
    def runner(args, stdin_text, cwd, timeout, env):
        return ProcessResult(args=tuple(args), returncode=returncode, stdout=stdout, stderr="", latency_ms=100.0)
    return runner


def _claude_success_json(model: str = "claude-fable-5") -> str:
    return json.dumps({
        "type": "result", "subtype": "success", "is_error": False,
        "result": '{"ids":["mt_test"]}',
        "session_id": "session_fixture", "stop_reason": "end_turn",
        "usage": {"input_tokens": 10, "output_tokens": 5},
        "modelUsage": {
            model: {"inputTokens": 10, "outputTokens": 5, "cacheReadInputTokens": 0, "cacheCreationInputTokens": 0, "webSearchRequests": 0}
        },
        "permission_denials": [], "terminal_reason": "completed",
    })


def _prepared_wave(tmp_path: Path) -> tuple[dict, Path, Path, Path]:
    suite = _fake_suite(tasks_per_tier=4)
    suite_path = tmp_path / "suite.private.json"
    suite_path.write_text(json.dumps(suite), encoding="utf-8")
    control_root = tmp_path / "control"
    control_root.mkdir()
    out_dir = tmp_path / "wave-1"
    metadata = wave.collect_provider_metadata()
    manifest = wave.prepare_manifest(
        suite, suite_path, control_root, metadata, out_dir
    )
    return manifest, suite_path, control_root, out_dir


def _calibration_run(manifest: dict, lane_id: str = "claude-opus-5") -> dict:
    lane = manifest["lanes"][lane_id]
    lane_meta = manifest["lane_metadata"][lane_id]
    return {
        "suite_sha256": manifest["suite_sha256"],
        "task_ids": list(manifest["calibration_ids"]),
        "requested_model": lane["selector"],
        "resolved_model": lane["expected_model"],
        "base_instruction_hash": manifest["base_instruction_hash"],
        "tool_policy_hash": lane_meta["tool_policy_hash"],
        "invocation_hash": lane_meta["invocation_hash"],
        "cli_versions": manifest["cli_versions"],
        "attempts": [
            {
                "task_id": task_id,
                "scored": True,
                "latency_ms": 12.0,
                "error_kind": None,
            }
            for task_id in manifest["calibration_ids"]
        ],
    }


class WaveOracleProvider(taxonomy_bench_cli.Provider):
    supports_sessions = True
    auth_mode = "subscription"

    def __init__(
        self,
        suite: dict,
        manifest: dict,
        lane_id: str,
        *,
        persistent: bool,
        fail_on: int | None = None,
        error_kind: str = "rate_limit",
    ) -> None:
        self.selector = manifest["lanes"][lane_id]["selector"]
        self.expected_model = manifest["lanes"][lane_id]["expected_model"]
        lane_meta = manifest["lane_metadata"][lane_id]
        self.invocation_hash = lane_meta["invocation_hash"]
        self.tool_policy_hash = lane_meta["tool_policy_hash"]
        self.persistent = persistent
        self.fail_on = fail_on
        self.error_kind = error_kind
        self.calls: list[tuple[str, str | None]] = []
        self._answers = {
            task["prompt"]: correct_answer(task)
            for task in suite["tasks"]
        }
        self._prompt_by_session: dict[str, str] = {}

    def preflight(self):
        return {
            "auth_mode": "subscription",
            "resolved_model": self.expected_model,
        }

    def complete(self, prompt, output_schema, previous_response_id=None):
        self.calls.append((prompt, previous_response_id))
        call_number = len(self.calls)
        if self.fail_on == call_number:
            return Completion(
                text="",
                latency_ms=1.0,
                error="synthetic infrastructure failure",
                error_kind=self.error_kind,
            )
        if prompt in self._answers:
            original = prompt
        elif previous_response_id in self._prompt_by_session:
            original = self._prompt_by_session[previous_response_id]
        else:
            matches = [value for value in self._answers if prompt.startswith(value)]
            assert matches
            original = matches[0]
        session_id = f"raw-session-{id(self)}-{call_number}"
        self._prompt_by_session[session_id] = original
        return Completion(
            text=self._answers[original],
            latency_ms=1.0,
            resolved_model=self.expected_model,
            response_id=session_id if self.persistent else None,
            status="completed",
        )


# ---------------------------------------------------------------------------
# Task 6: Manifest tests
# ---------------------------------------------------------------------------


class TestManifest:
    def test_wave1_protocol_contains_correct_pairs(self):
        assert wave.WAVE1_PAIRS == (
            ("claude-opus-5", "gpt-5.6-sol"),
            ("claude-sonnet-5", "gpt-5.6-terra"),
            ("claude-fable-5", "gpt-5.6-luna"),
        )
        assert len(wave.WAVE1_PAIRS) == 3

    def test_wave1_lanes_covers_all_selectors(self):
        expected_selectors = set()
        for pair in wave.WAVE1_PAIRS:
            expected_selectors.add(pair[0])
            expected_selectors.add(pair[1])
        assert set(wave.WAVE1_LANES.keys()) == expected_selectors

    def test_lane_registry_has_family_and_selector(self):
        for selector, info in wave.WAVE1_LANES.items():
            assert "family" in info
            assert "selector" in info
            assert info["selector"] == selector
            assert info["family"] in ("claude", "codex")

    def test_deterministic_calibration_ids(self):
        suite = _fake_suite(tasks_per_tier=4)
        ids = wave.deterministic_calibration_ids(suite)
        assert len(ids) == 8
        assert len(set(ids)) == 8
        # Determinism: same suite, same ids
        ids2 = wave.deterministic_calibration_ids(suite)
        assert ids == ids2

    def test_prepare_manifest_and_idempotence(self, tmp_path: Path):
        suite = _fake_suite(tasks_per_tier=4)
        suite_path = tmp_path / "suite.private.json"
        suite_path.write_text(json.dumps(suite), encoding="utf-8")
        control_root = tmp_path / "control"
        control_root.mkdir()
        out_dir = tmp_path / "wave-1"

        provider_meta = {
            "instruction_hash": canonical_hash(BASE_INSTRUCTIONS),
            "invocation_hash": "abc123",
            "tool_policy_hash": "def456",
            "codex_version": "0.146.0",
            "claude_version": "2.1.195",
        }

        m1 = wave.prepare_manifest(suite, suite_path, control_root, provider_meta, out_dir)
        assert m1["protocol_version"] == wave.WAVE1_VERSION
        assert "manifest_hash" in m1
        assert "input_fingerprint" in m1
        assert len(m1["calibration_ids"]) == 8
        assert m1["lanes"] == wave.WAVE1_LANES
        assert (out_dir / "manifest.json").exists()

        # Idempotent: same result
        m2 = wave.prepare_manifest(suite, suite_path, control_root, provider_meta, out_dir)
        assert m2 == m1
        assert m2["created_at"] == m1["created_at"]

    def test_prepare_manifest_rejects_tampered(self, tmp_path: Path):
        suite = _fake_suite(tasks_per_tier=4)
        suite_path = tmp_path / "suite.private.json"
        suite_path.write_text(json.dumps(suite), encoding="utf-8")
        out_dir = tmp_path / "wave-1"
        control_root = tmp_path / "control"
        control_root.mkdir()

        provider_meta = {"instruction_hash": canonical_hash(BASE_INSTRUCTIONS), "invocation_hash": "a", "tool_policy_hash": "b"}
        wave.prepare_manifest(suite, suite_path, control_root, provider_meta, out_dir)

        # Tamper with manifest
        manifest_path = out_dir / "manifest.json"
        m = json.loads(manifest_path.read_text(encoding="utf-8"))
        m["suite_sha256"] = "bad"
        manifest_path.write_text(json.dumps(m), encoding="utf-8")

        # Should refuse to overwrite with different fingerprint
        suite_path.write_text(json.dumps(suite), encoding="utf-8")
        with pytest.raises(BenchError, match="invalid content hash"):
            wave.prepare_manifest(suite, suite_path, control_root, provider_meta, out_dir)


# ---------------------------------------------------------------------------
# Task 7: Family locks and lane state tests
# ---------------------------------------------------------------------------


class TestFamilyLocks:
    def test_two_different_family_locks_coexist(self, tmp_path: Path):
        lock1 = wave.FamilyLock(tmp_path, "claude")
        lock2 = wave.FamilyLock(tmp_path, "codex")
        try:
            assert lock1._path.exists()
            assert lock2._path.exists()
        finally:
            lock1.release()
            lock2.release()

    def test_same_family_lock_conflict(self, tmp_path: Path):
        lock1 = wave.FamilyLock(tmp_path, "claude")
        try:
            with pytest.raises(BenchError, match="Cannot acquire claude lock"):
                wave.FamilyLock(tmp_path, "claude")
        finally:
            lock1.release()

    def test_release_allows_reacquire(self, tmp_path: Path):
        lock1 = wave.FamilyLock(tmp_path, "claude")
        lock1.release()
        lock2 = wave.FamilyLock(tmp_path, "claude")
        lock2.release()


class TestLaneState:
    def test_state_save_and_load(self, tmp_path: Path):
        state = wave.LaneState(
            lane="claude-opus-5", pair_index=1, manifest_hash="mh",
            provider_fingerprint="pf", status="pending",
        )
        state_dir = tmp_path / "lane-state"
        state.save(state_dir)
        loaded = wave.LaneState.load(state_dir)
        assert loaded.lane == state.lane
        assert loaded.status == "pending"
        assert loaded.pair_index == 1

    def test_state_validation_rejects_changed_manifest(self, tmp_path: Path):
        manifest = {"manifest_hash": "mh_original"}
        state = wave.LaneState(lane="c", pair_index=1, manifest_hash="mh_changed", provider_fingerprint="pf", status="running")

        class FakeProvider:
            invocation_hash = "a"
            tool_policy_hash = "b"

        with pytest.raises(BenchError, match="hash changed"):
            state.validate_continuation(manifest, FakeProvider())

    def test_state_validation_rejects_provider_drift(self):
        manifest = {"manifest_hash": "mh"}
        fp = canonical_hash({"invocation": "orig", "tool_policy": "orig"})
        state = wave.LaneState(lane="c", pair_index=1, manifest_hash="mh", provider_fingerprint=fp, status="running")

        class DriftedProvider:
            invocation_hash = "changed"
            tool_policy_hash = "changed"

        with pytest.raises(BenchError, match="fingerprint drift"):
            state.validate_continuation(manifest, DriftedProvider())


# ---------------------------------------------------------------------------
# Task 8: Pair barriers
# ---------------------------------------------------------------------------


class TestPairBarriers:
    def test_pair_1_can_always_start(self, tmp_path: Path):
        assert wave.pair_can_start({}, tmp_path, 1)

    def test_pair_2_needs_pair_1_marker(self, tmp_path: Path):
        assert not wave.pair_can_start({"manifest_hash": "mh"}, tmp_path, 2)
        wave.record_aggregation(tmp_path, "mh", 1)
        assert wave.pair_can_start({"manifest_hash": "mh"}, tmp_path, 2)

    def test_pair_2_rejects_mismatched_manifest(self, tmp_path: Path):
        wave.record_aggregation(tmp_path, "mh", 1)
        assert not wave.pair_can_start({"manifest_hash": "different"}, tmp_path, 2)

    def test_aggregation_requires_two_complete_lanes(self, tmp_path: Path):
        state1 = wave.LaneState(lane="c1", pair_index=1, manifest_hash="mh", provider_fingerprint="pf", status="complete", accepted_run_ids=["r1", "r2", "r3"])
        state2 = wave.LaneState(lane="c2", pair_index=1, manifest_hash="mh", provider_fingerprint="pf", status="complete", accepted_run_ids=["r4", "r5", "r6"])
        states = [state1, state2]
        assert wave.pair_can_aggregate({"manifest_hash": "mh"}, tmp_path, 1, states)

    def test_aggregation_rejects_incomplete_lanes(self, tmp_path: Path):
        state1 = wave.LaneState(lane="c1", pair_index=1, manifest_hash="mh", provider_fingerprint="pf", status="running", accepted_run_ids=["r1", "r2", "r3"])
        state2 = wave.LaneState(lane="c2", pair_index=1, manifest_hash="mh", provider_fingerprint="pf", status="complete", accepted_run_ids=["r4", "r5", "r6"])
        states = [state1, state2]
        assert not wave.pair_can_aggregate({}, tmp_path, 1, states)

    def test_aggregation_rejects_insufficient_runs(self, tmp_path: Path):
        state1 = wave.LaneState(lane="c1", pair_index=1, manifest_hash="mh", provider_fingerprint="pf", status="complete", accepted_run_ids=["r1"])
        state2 = wave.LaneState(lane="c2", pair_index=1, manifest_hash="mh", provider_fingerprint="pf", status="complete", accepted_run_ids=["r2"])
        states = [state1, state2]
        assert not wave.pair_can_aggregate({}, tmp_path, 1, states)


# ---------------------------------------------------------------------------
# Task 8: Calibration admission
# ---------------------------------------------------------------------------


class TestCalibrationAdmission:
    def test_admits_complete_calibration(self, tmp_path: Path):
        manifest, *_ = _prepared_wave(tmp_path)
        result = wave.admit_calibration(
            _calibration_run(manifest), manifest, "claude-opus-5"
        )
        assert result.passed
        assert result.reasons == ()

    @pytest.mark.parametrize(
        ("mutation", "reason"),
        [
            (lambda run: run["attempts"].pop(), "attempt_count"),
            (
                lambda run: run["attempts"][0].update(scored=False),
                "unscored:",
            ),
            (
                lambda run: run["attempts"][0].update(latency_ms=-1),
                "latency:",
            ),
            (
                lambda run: run.update(suite_sha256="changed"),
                "suite_hash_mismatch",
            ),
            (
                lambda run: run["task_ids"].reverse(),
                "task_ids_mismatch",
            ),
            (
                lambda run: run.update(resolved_model="fallback"),
                "resolved_model_mismatch",
            ),
            (
                lambda run: run.update(invocation_hash="changed"),
                "invocation_hash_mismatch",
            ),
            (
                lambda run: run["attempts"][0].update(error_kind="rate_limit"),
                "infrastructure:",
            ),
        ],
    )
    def test_rejects_invalid_calibration(
        self, tmp_path: Path, mutation, reason: str
    ):
        manifest, *_ = _prepared_wave(tmp_path)
        run = _calibration_run(manifest)
        mutation(run)
        result = wave.admit_calibration(run, manifest, "claude-opus-5")
        assert not result.passed
        assert any(reason in item for item in result.reasons)

    def test_malformed_subject_json_is_still_scored(self, tmp_path: Path):
        manifest, *_ = _prepared_wave(tmp_path)
        run = _calibration_run(manifest)
        run["attempts"][0]["text"] = "not json"
        assert wave.admit_calibration(
            run, manifest, "claude-opus-5"
        ).passed


class TestWaveCheckpoint:
    def test_persists_then_aborts_on_infrastructure(self, tmp_path: Path):
        envelope = {
            "configuration": {"retries": 2},
            "tasks": [{
                "task_id": "t1",
                "base_previous_response_id": None,
                "attempts": [{
                    "attempt": 1,
                    "response_id": "raw-session",
                    "error_kind": "rate_limit",
                    "score": None,
                }],
            }],
        }
        checkpoint = wave.make_wave_checkpoint(tmp_path)
        with pytest.raises(wave.WaveInfrastructureAbort):
            checkpoint("run-1", envelope)
        saved = json.loads(
            (tmp_path / "run-1.envelope.json").read_text(encoding="utf-8")
        )
        text = json.dumps(saved)
        assert "raw-session" not in text
        assert hashlib.sha256(b"raw-session").hexdigest() in text

    @pytest.mark.parametrize(
        ("attempt", "exact", "retries", "redacted"),
        [(1, True, 2, True), (1, False, 2, False), (3, False, 2, True)],
    )
    def test_redacts_only_closed_retry_windows(
        self, tmp_path: Path, attempt: int, exact: bool, retries: int, redacted: bool
    ):
        envelope = {
            "configuration": {"retries": retries},
            "tasks": [{
                "task_id": "t1",
                "base_previous_response_id": None,
                "attempts": [{
                    "attempt": attempt,
                    "response_id": "raw-session",
                    "error_kind": None,
                    "score": {"exact": exact},
                }],
            }],
        }
        wave.make_wave_checkpoint(tmp_path)("run-1", envelope)
        saved = (tmp_path / "run-1.envelope.json").read_text(encoding="utf-8")
        assert ("raw-session" not in saved) is redacted


# ---------------------------------------------------------------------------
# Wave controller tests
# ---------------------------------------------------------------------------


class TestWaveController:
    def test_validate_manifest(self, tmp_path: Path):
        suite = _fake_suite(tasks_per_tier=4)
        suite_path = tmp_path / "suite.private.json"
        suite_path.write_text(json.dumps(suite), encoding="utf-8")
        control_root = tmp_path / "control"
        control_root.mkdir()
        subject_root = tmp_path / "subjects"
        subject_root.mkdir()
        out_dir = tmp_path / "wave-1"

        provider_meta = {
            "instruction_hash": canonical_hash(BASE_INSTRUCTIONS),
            "invocation_hash": "a", "tool_policy_hash": "b",
        }
        wave.prepare_manifest(suite, suite_path, control_root, provider_meta, out_dir)

        ctrl = wave.WaveController(
            manifest_path=out_dir / "manifest.json",
            control_root=control_root,
            subject_root=subject_root,
            wave_dir=out_dir,
        )
        assert ctrl.manifest["protocol_version"] == wave.WAVE1_VERSION

    def test_validate_subject_root(self, tmp_path: Path):
        suite = _fake_suite(tasks_per_tier=4)
        suite_path = tmp_path / "suite.private.json"
        suite_path.write_text(json.dumps(suite), encoding="utf-8")
        out_dir = tmp_path / "wave-1"
        control_root = tmp_path / "control"
        control_root.mkdir()
        subject_root = tmp_path / "subjects"
        subject_root.mkdir()

        provider_meta = {
            "instruction_hash": canonical_hash(BASE_INSTRUCTIONS),
            "invocation_hash": "a", "tool_policy_hash": "b",
        }
        wave.prepare_manifest(suite, suite_path, control_root, provider_meta, out_dir)

        ctrl = wave.WaveController(
            manifest_path=out_dir / "manifest.json",
            control_root=control_root,
            subject_root=subject_root,
            wave_dir=out_dir,
        )
        ctrl.validate_subject_root()
        # Marker should exist
        assert (subject_root / ".wave1-subject-root").exists()


class TestWaveCli:
    def test_wave_prepare_writes_manifest(
        self, tmp_path: Path, monkeypatch, capsys
    ):
        suite = _fake_suite(tasks_per_tier=4)
        suite_path = tmp_path / "suite.private.json"
        suite_path.write_text(json.dumps(suite), encoding="utf-8")
        control = tmp_path / "control"
        control.mkdir()
        out = tmp_path / "wave-1"
        monkeypatch.setattr(
            wave, "collect_provider_metadata", lambda: {
                "instruction_hash": canonical_hash(BASE_INSTRUCTIONS),
                "invocation_hash": "i",
                "tool_policy_hash": "t",
                "codex_version": "test",
                "claude_version": "test",
            }
        )
        assert tb.main([
            "wave", "prepare",
            "--suite", str(suite_path),
            "--out", str(out),
            "--control-root", str(control),
        ]) == 0
        manifest = json.loads(
            (out / "manifest.json").read_text(encoding="utf-8")
        )
        assert manifest["manifest_hash"] in capsys.readouterr().out
        assert (out / "suite.private.json").exists()

    def test_wave_prepare_requires_existing_control_root(self, tmp_path: Path):
        suite = _fake_suite(tasks_per_tier=4)
        suite_path = tmp_path / "suite.private.json"
        suite_path.write_text(json.dumps(suite), encoding="utf-8")
        out = tmp_path / "wave-1"
        assert tb.main([
            "wave", "prepare",
            "--suite", str(suite_path),
            "--out", str(out),
            "--control-root", str(tmp_path / "missing"),
        ]) == 2
        assert not out.exists()

    def test_wave_preflight_prints_only_sanitized_metadata(
        self, tmp_path: Path, monkeypatch, capsys
    ):
        manifest, _, control, out = _prepared_wave(tmp_path)
        subject = tmp_path / "subject"
        subject.mkdir()

        class FakeProvider:
            auth_mode = "subscription"
            expected_model = "claude-opus-5"
            invocation_hash = manifest["lane_metadata"]["claude-opus-5"]["invocation_hash"]
            tool_policy_hash = manifest["lane_metadata"]["claude-opus-5"]["tool_policy_hash"]

            def preflight(self):
                return {
                    "resolved_model": "claude-opus-5",
                    "session_id": "raw-secret-session",
                }

        monkeypatch.setattr(
            wave.WaveController,
            "build_provider",
            lambda self, lane_id, persistent=False: FakeProvider(),
        )
        assert tb.main([
            "wave", "preflight",
            "--manifest", str(out / "manifest.json"),
            "--lane", "claude-opus-5",
            "--subject-root", str(subject),
        ]) == 0
        output = capsys.readouterr().out
        assert "subscription" in output
        assert "claude-opus-5" in output
        assert "raw-secret-session" not in output


class TestWaveLaneExecution:
    def _controller(
        self,
        *,
        manifest: dict,
        control: Path,
        out: Path,
        subject: Path,
        suite: dict,
        fail_primary_on: int | None = None,
    ) -> tuple[wave.WaveController, list[WaveOracleProvider]]:
        providers: list[WaveOracleProvider] = []

        def factory(lane_id: str, persistent: bool):
            provider = WaveOracleProvider(
                suite,
                manifest,
                lane_id,
                persistent=persistent,
                fail_on=fail_primary_on if persistent else None,
            )
            providers.append(provider)
            return provider

        return (
            wave.WaveController(
                manifest_path=out / "manifest.json",
                control_root=control,
                subject_root=subject,
                wave_dir=out,
                provider_factory=factory,
            ),
            providers,
        )

    def test_wave_run_calibrates_then_publishes_three_repeats(
        self, tmp_path: Path
    ):
        manifest, suite_path, control, out = _prepared_wave(tmp_path)
        suite = tb.load_suite(suite_path)
        subject = tmp_path / "subject"
        subject.mkdir()
        controller, providers = self._controller(
            manifest=manifest,
            control=control,
            out=out,
            subject=subject,
            suite=suite,
        )
        assert controller.run_lane("claude-opus-5") == 0
        state = wave.LaneState.load(out / "lanes" / "claude-opus-5")
        assert state.status == "complete"
        assert len(state.accepted_run_ids) == 3
        assert state.completed_primary_repeat_numbers == [1, 2, 3]
        calibration = json.loads(
            (
                out / "runs" / state.calibration_run_id / "run.json"
            ).read_text(encoding="utf-8")
        )
        assert calibration["task_ids"] == manifest["calibration_ids"]
        assert (out / "reports" / "lane-claude-opus-5" / "lane.json").exists()
        assert len(providers[0].calls) == 8
        assert len(providers[1].calls) == 32 * 3
        for run_id in state.accepted_run_ids:
            text = (out / "runs" / run_id / "run.json").read_text(
                encoding="utf-8"
            )
            assert "raw-session-" not in text

    def test_wave_run_abandons_and_restarts_current_repeat(
        self, tmp_path: Path
    ):
        manifest, suite_path, control, out = _prepared_wave(tmp_path)
        suite = tb.load_suite(suite_path)
        subject = tmp_path / "subject"
        subject.mkdir()
        controller, providers = self._controller(
            manifest=manifest,
            control=control,
            out=out,
            subject=subject,
            suite=suite,
            fail_primary_on=3,
        )
        assert controller.run_lane("claude-opus-5") == 2
        state = wave.LaneState.load(out / "lanes" / "claude-opus-5")
        assert state.calibration_run_id
        assert state.accepted_run_ids == []
        assert len(state.abandoned_run_ids) == 1
        assert len(providers[-1].calls) == 3
        abandoned = state.abandoned_run_ids[0]
        envelope = (
            out / "envelopes" / f"{abandoned}.envelope.json"
        ).read_text(encoding="utf-8")
        assert "raw-session-" not in envelope

        resumed, resumed_providers = self._controller(
            manifest=manifest,
            control=control,
            out=out,
            subject=subject,
            suite=suite,
        )
        assert resumed.run_lane("claude-opus-5") == 0
        final = wave.LaneState.load(out / "lanes" / "claude-opus-5")
        assert final.status == "complete"
        assert final.calibration_run_id == state.calibration_run_id
        assert final.abandoned_run_ids == [abandoned]
        assert len(resumed_providers) == 2

    def test_lane_report_rejects_incomplete_state(self, tmp_path: Path):
        manifest, _, _, out = _prepared_wave(tmp_path)
        state = wave.LaneState(
            lane="claude-opus-5",
            pair_index=1,
            manifest_hash=manifest["manifest_hash"],
            provider_fingerprint="x",
            status="running",
            calibration_run_id="calibration",
        )
        with pytest.raises(BenchError, match="exactly three"):
            wave.publish_lane_report(state, manifest, out)


class TestWavePairAggregation:
    def test_pair_aggregation_uses_six_primary_runs_and_opens_barrier(
        self, tmp_path: Path
    ):
        manifest, suite_path, control, out = _prepared_wave(tmp_path)
        suite = tb.load_suite(suite_path)
        subject = tmp_path / "subject"
        subject.mkdir()

        for lane_id in manifest["pairs"][0]:
            def factory(
                requested_lane: str,
                persistent: bool,
                lane_id=lane_id,
            ):
                assert requested_lane == lane_id
                return WaveOracleProvider(
                    suite,
                    manifest,
                    lane_id,
                    persistent=persistent,
                )

            controller = wave.WaveController(
                manifest_path=out / "manifest.json",
                control_root=control,
                subject_root=subject,
                wave_dir=out,
                provider_factory=factory,
            )
            assert controller.run_lane(lane_id) == 0

        report = wave.aggregate_pair(out / "manifest.json", 1)
        matrix = json.loads(
            (report / "matrix.json").read_text(encoding="utf-8")
        )
        assert len(matrix["accepted_run_ids"]) == 6
        assert len(matrix["runs"]) == 6
        assert wave.pair_can_start(manifest, control, 2)
        assert wave.aggregate_pair(out / "manifest.json", 1) == report

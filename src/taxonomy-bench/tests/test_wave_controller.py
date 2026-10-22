"""Wave 1 controller tests with fake providers."""

from __future__ import annotations

import json
import hashlib
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
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
        assert wave.subject_root_marker(
            subject_root, ctrl.manifest["manifest_hash"]
        ).exists()


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
            wave, "collect_provider_metadata", lambda lane_set="wave-1": {
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

    def test_fake_cli_end_to_end_runs_two_families_concurrently(
        self, tmp_path: Path, monkeypatch
    ):
        suite = _fake_suite(tasks_per_tier=4)
        suite_path = tmp_path / "suite.private.json"
        suite_path.write_text(json.dumps(suite), encoding="utf-8")
        control = tmp_path / "control"
        control.mkdir()
        out = tmp_path / "wave-1"
        subjects = {
            "claude": tmp_path / "subject-claude",
            "codex": tmp_path / "subject-codex",
        }
        for subject in subjects.values():
            subject.mkdir()

        answers = {
            task["prompt"]: correct_answer(task)
            for task in suite["tasks"]
        }
        concurrency = {"active": 0, "maximum": 0}
        concurrency_lock = threading.Lock()
        sessions: dict[str, list[str]] = {"claude": [], "codex": []}

        def answer_for(stdin_text: str) -> str:
            matches = [
                answer for prompt, answer in answers.items()
                if prompt in stdin_text
            ]
            assert len(matches) == 1
            return matches[0]

        def model_call(family: str, callback):
            with concurrency_lock:
                concurrency["active"] += 1
                concurrency["maximum"] = max(
                    concurrency["maximum"], concurrency["active"]
                )
            try:
                time.sleep(0.001)
                return callback()
            finally:
                with concurrency_lock:
                    concurrency["active"] -= 1

        def claude_runner(args, stdin_text, cwd, timeout, env):
            if "--version" in args:
                return ProcessResult(
                    tuple(args), 0, "claude-test-1", "", 1.0
                )
            if "auth" in args:
                return ProcessResult(
                    tuple(args),
                    0,
                    json.dumps({
                        "loggedIn": True,
                        "authMethod": "claude.ai",
                        "apiProvider": "firstParty",
                        "subscriptionType": "max",
                    }),
                    "",
                    1.0,
                )

            def complete():
                session = f"claude-session-{len(sessions['claude']) + 1}"
                sessions["claude"].append(session)
                return ProcessResult(
                    tuple(args),
                    0,
                    json.dumps({
                        "type": "result",
                        "subtype": "success",
                        "is_error": False,
                        "result": answer_for(stdin_text),
                        "session_id": session,
                        "stop_reason": "completed",
                        "usage": {},
                        "modelUsage": {"claude-opus-5": {
                            "inputTokens": 1, "outputTokens": 1,
                        }},
                    }),
                    "",
                    1.0,
                )

            return model_call("claude", complete)

        def codex_runner(args, stdin_text, cwd, timeout, env):
            if "--version" in args:
                return ProcessResult(tuple(args), 0, "codex-test-1", "", 1.0)
            if "login" in args:
                return ProcessResult(
                    tuple(args), 0, "Logged in using ChatGPT", "", 1.0
                )

            def complete():
                session = f"codex-session-{len(sessions['codex']) + 1}"
                sessions["codex"].append(session)
                stdout = "\n".join([
                    json.dumps({"type": "thread.started", "thread_id": session}),
                    json.dumps({
                        "type": "item.completed",
                        "item": {
                            "type": "agent_message",
                            "text": answer_for(stdin_text),
                        },
                    }),
                    json.dumps({"type": "turn.completed", "usage": {}}),
                ])
                return ProcessResult(tuple(args), 0, stdout, "", 1.0)

            return model_call("codex", complete)

        monkeypatch.setattr(
            taxonomy_bench_cli.shutil,
            "which",
            lambda name: f"C:/fake/{name}.exe",
        )

        metadata = {
            "instruction_hash": canonical_hash(BASE_INSTRUCTIONS),
            "cli_versions": {
                "claude": "claude-test-1",
                "codex": "codex-test-1",
            },
            "lanes": {},
        }
        for lane_id, lane in wave.WAVE1_LANES.items():
            provider = (
                taxonomy_bench_cli.ClaudeCliProvider(
                    selector=lane["selector"],
                    expected_model=lane["expected_model"],
                    subject_root=subjects["claude"],
                    runner=claude_runner,
                )
                if lane["family"] == "claude"
                else taxonomy_bench_cli.CodexCliProvider(
                    selector=lane["selector"],
                    expected_model=lane["expected_model"],
                    subject_root=subjects["codex"],
                    runner=codex_runner,
                )
            )
            metadata["lanes"][lane_id] = {
                "family": lane["family"],
                "requested_model": lane["selector"],
                "expected_model": lane["expected_model"],
                "cli_version": metadata["cli_versions"][lane["family"]],
                "invocation_hash": provider.invocation_hash,
                "tool_policy_hash": provider.tool_policy_hash,
                "auth_mode": "subscription",
            }
        manifest = wave.prepare_manifest(
            suite, suite_path, control, metadata, out
        )

        def run_lane(lane_id: str) -> int:
            family = manifest["lanes"][lane_id]["family"]

            def factory(requested_lane: str, persistent: bool):
                lane = manifest["lanes"][requested_lane]
                provider_class = (
                    taxonomy_bench_cli.ClaudeCliProvider
                    if family == "claude"
                    else taxonomy_bench_cli.CodexCliProvider
                )
                return provider_class(
                    selector=lane["selector"],
                    expected_model=lane["expected_model"],
                    subject_root=subjects[family],
                    persistent=persistent,
                    runner=claude_runner if family == "claude" else codex_runner,
                )

            return wave.WaveController(
                manifest_path=out / "manifest.json",
                control_root=control,
                subject_root=subjects[family],
                wave_dir=out,
                provider_factory=factory,
            ).run_lane(lane_id)

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(run_lane, manifest["pairs"][0]))
        assert results == [0, 0]
        assert concurrency["maximum"] == 2
        assert len(sessions["claude"]) == 104
        assert len(sessions["codex"]) == 104
        assert len(set(sessions["claude"])) == 104
        assert len(set(sessions["codex"])) == 104
        report = wave.aggregate_pair(out / "manifest.json", 1)
        matrix = json.loads(
            (report / "matrix.json").read_text(encoding="utf-8")
        )
        assert len(matrix["accepted_run_ids"]) == 6


# ---------------------------------------------------------------------------
# Calibration-only lane mode
# ---------------------------------------------------------------------------


def _oracle_controller(
    manifest: dict, control: Path, out: Path, subject: Path, suite: dict
) -> tuple[wave.WaveController, list[WaveOracleProvider]]:
    providers: list[WaveOracleProvider] = []

    def factory(lane_id: str, persistent: bool):
        provider = WaveOracleProvider(suite, manifest, lane_id, persistent=persistent)
        providers.append(provider)
        return provider

    controller = wave.WaveController(
        manifest_path=out / "manifest.json",
        control_root=control,
        subject_root=subject,
        wave_dir=out,
        provider_factory=factory,
    )
    return controller, providers


class TestCalibrationOnly:
    def test_calibration_only_stops_before_primary_repeats(self, tmp_path: Path):
        manifest, suite_path, control, out = _prepared_wave(tmp_path)
        suite = tb.load_suite(suite_path)
        subject = tmp_path / "subject"
        subject.mkdir()
        controller, providers = _oracle_controller(manifest, control, out, subject, suite)

        assert controller.run_lane("claude-opus-5", calibration_only=True) == 0
        state = wave.LaneState.load(out / "lanes" / "claude-opus-5")
        assert state.status == "calibrated"
        assert state.calibration_run_id
        assert state.accepted_run_ids == []
        assert [provider.persistent for provider in providers] == [False]
        assert len(providers[0].calls) == 8

        assert controller.run_lane("claude-opus-5", calibration_only=True) == 0
        assert sum(len(provider.calls) for provider in providers) == 8

        assert controller.run_lane("claude-opus-5") == 0
        final = wave.LaneState.load(out / "lanes" / "claude-opus-5")
        assert final.status == "complete"
        assert final.calibration_run_id == state.calibration_run_id
        assert sum(
            len(provider.calls) for provider in providers if not provider.persistent
        ) == 8

    def test_wave_run_cli_passes_calibration_only_and_google_lanes(
        self, tmp_path: Path, monkeypatch
    ):
        _, _, control, out = _prepared_wave(tmp_path)
        _, google_out = _prepared_google_wave(tmp_path, control)
        subject = tmp_path / "subject"
        subject.mkdir()
        seen: list[tuple[str, bool]] = []

        def fake_run_lane(self, lane_id, calibration_only=False):
            seen.append((lane_id, calibration_only))
            return 0

        monkeypatch.setattr(wave.WaveController, "run_lane", fake_run_lane)
        for manifest_dir, lane_id, extra in (
            (out, "claude-opus-5", ["--calibration-only"]),
            (google_out, "gemini-4-argon-medium", []),
        ):
            assert tb.main([
                "wave", "run",
                "--manifest", str(manifest_dir / "manifest.json"),
                "--lane", lane_id,
                "--subject-root", str(subject),
                *extra,
            ]) == 0
        assert seen == [("claude-opus-5", True), ("gemini-4-argon-medium", False)]


# ---------------------------------------------------------------------------
# Google lane set (agy) sharing the controller roots with Wave 1
# ---------------------------------------------------------------------------

GOOGLE_LANES = ("gemini-4-argon-medium", "gemini-3.8-flash-medium")


def _prepared_google_wave(tmp_path: Path, control_root: Path) -> tuple[dict, Path]:
    suite_path = tmp_path / "suite.private.json"
    if not suite_path.exists():
        suite_path.write_text(
            json.dumps(_fake_suite(tasks_per_tier=4)), encoding="utf-8"
        )
    out_dir = tmp_path / "google-1"
    metadata = {
        "instruction_hash": canonical_hash(BASE_INSTRUCTIONS),
        "cli_versions": {"antigravity": "1.4.4"},
        "lanes": {},
    }
    for lane_id in GOOGLE_LANES:
        invocation, tool_policy = taxonomy_bench_cli.agy_policy_hashes(lane_id)
        metadata["lanes"][lane_id] = {
            "family": "antigravity",
            "requested_model": lane_id,
            "expected_model": lane_id,
            "cli_version": "1.4.4",
            "invocation_hash": invocation,
            "tool_policy_hash": tool_policy,
            "auth_mode": "subscription",
        }
    manifest = wave.prepare_manifest(
        tb.load_suite(suite_path),
        suite_path,
        control_root,
        metadata,
        out_dir,
        lane_set="google-1",
    )
    return manifest, out_dir


def _fake_agy_runner(suite: dict, conversations: dict[str, str]):
    answers = {task["prompt"]: correct_answer(task) for task in suite["tasks"]}
    first_prompt = suite["tasks"][0]["prompt"]

    def ok(args, stdout: str) -> ProcessResult:
        return ProcessResult(tuple(args), 0, stdout, "", 1.0)

    def runner(args, stdin_text, cwd, timeout, env):
        if "--version" in args:
            return ok(args, "1.4.4\n")
        if "models" in args:
            return ok(args, "".join(f"{lane}\t{lane}\n" for lane in GOOGLE_LANES))
        selector = args[args.index("--model") + 1]
        if "--print=/quota" in args:
            return ok(args, json.dumps({
                "status": "SUCCESS", "num_turns": 0,
                "command": {"name": "usage", "data": {"groups": [{"name": "Gemini Models"}]}},
            }))
        if "--print=/model" in args:
            return ok(args, json.dumps({
                "status": "SUCCESS", "num_turns": 0,
                "command": {"name": "model", "data": {"id": selector, "label": selector}},
            }))
        assert Path(env["USERPROFILE"]).name in {"calibration", "primary"}
        content = json.loads(stdin_text)["message"]["content"]
        if "--conversation" in args:
            conversation = args[args.index("--conversation") + 1]
            response = answers[conversations[conversation]]
        else:
            matches = [prompt for prompt in answers if prompt in content]
            assert len(matches) == 1
            conversation = f"agy-conversation-{len(conversations) + 1}"
            conversations[conversation] = matches[0]
            # Miss the first task on its first attempt so retries resume it.
            response = '{"ids":[]}' if matches[0] == first_prompt else answers[matches[0]]
        return ok(args, "\n".join([
            json.dumps({"event": "init", "conversation_id": conversation, "init": {
                "model": selector, "tools": ["view_file"], "permission_mode": "request-review",
            }}),
            json.dumps({"event": "result", "result": {
                "conversation_id": conversation, "status": "SUCCESS",
                "response": response, "num_turns": 1, "usage": {},
            }}),
        ]) + "\n")

    return runner


class TestGoogleLaneSet:
    def test_google_lane_set_is_one_antigravity_pair(self):
        assert wave.GOOGLE1_PAIRS == (GOOGLE_LANES,)
        lanes = wave.LANE_SETS["google-1"]["lanes"]
        assert set(lanes) == set(GOOGLE_LANES)
        for lane_id, lane in lanes.items():
            assert lane == {
                "family": "antigravity",
                "selector": lane_id,
                "expected_model": lane_id,
            }
        assert wave.LANE_SETS["wave-1"]["lanes"] == wave.WAVE1_LANES

    def test_google_manifest_shares_protocol_and_suite_with_wave_one(
        self, tmp_path: Path
    ):
        wave1, _, control, _ = _prepared_wave(tmp_path)
        google, _ = _prepared_google_wave(tmp_path, control)
        assert google["pairs"] == [list(GOOGLE_LANES)]
        assert set(google["lanes"]) == set(GOOGLE_LANES)
        for key in (
            "protocol_version",
            "protocol_hash",
            "suite_sha256",
            "calibration_ids",
            "base_instruction_hash",
            "control_root",
        ):
            assert google[key] == wave1[key]
        assert google["manifest_hash"] != wave1["manifest_hash"]

    def test_collect_provider_metadata_is_scoped_to_lane_set_families(
        self, monkeypatch
    ):
        monkeypatch.setattr(wave, "_cli_version", lambda executable: f"{executable}-test")
        google = wave.collect_provider_metadata("google-1")
        assert google["cli_versions"] == {"antigravity": "agy-test"}
        for lane_id in GOOGLE_LANES:
            invocation, tool_policy = taxonomy_bench_cli.agy_policy_hashes(lane_id)
            assert google["lanes"][lane_id]["invocation_hash"] == invocation
            assert google["lanes"][lane_id]["tool_policy_hash"] == tool_policy
            assert google["lanes"][lane_id]["cli_version"] == "agy-test"
        assert set(wave.collect_provider_metadata("wave-1")["cli_versions"]) == {
            "claude",
            "codex",
        }

    def test_cli_version_probe_disables_agy_self_update(self, monkeypatch):
        import subprocess

        seen: dict = {}

        def fake_run(args, **kwargs):
            seen["env"] = kwargs.get("env")
            return subprocess.CompletedProcess(args, 0, "1.4.5\n", "")

        monkeypatch.setattr(wave.shutil, "which", lambda name: f"C:/fake/{name}.exe")
        monkeypatch.setattr(wave.subprocess, "run", fake_run)
        assert wave._cli_version("agy") == "1.4.5"
        assert seen["env"]["AGY_CLI_DISABLE_AUTO_UPDATE"] == "1"

    def test_wave_prepare_cli_selects_google_lane_set(
        self, tmp_path: Path, monkeypatch
    ):
        suite_path = tmp_path / "suite.private.json"
        suite_path.write_text(json.dumps(_fake_suite(tasks_per_tier=4)), encoding="utf-8")
        control = tmp_path / "control"
        control.mkdir()
        out = tmp_path / "google-1"
        monkeypatch.setattr(wave, "_cli_version", lambda executable: f"{executable}-test")
        assert tb.main([
            "wave", "prepare",
            "--suite", str(suite_path),
            "--out", str(out),
            "--control-root", str(control),
            "--lanes", "google-1",
        ]) == 0
        manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["pairs"] == [list(GOOGLE_LANES)]
        assert manifest["cli_versions"] == {"antigravity": "agy-test"}

    def test_build_provider_isolates_agy_home_per_lane_and_phase(
        self, tmp_path: Path, monkeypatch
    ):
        _, _, control, _ = _prepared_wave(tmp_path)
        _, out = _prepared_google_wave(tmp_path, control)
        subject = tmp_path / "subject"
        subject.mkdir()
        monkeypatch.setattr(
            taxonomy_bench_cli.shutil, "which", lambda name: f"C:/fake/{name}.exe"
        )
        controller = wave.WaveController(
            manifest_path=out / "manifest.json",
            control_root=control,
            subject_root=subject,
            wave_dir=out,
        )
        calibration = controller.build_provider("gemini-4-argon-medium", persistent=False)
        primary = controller.build_provider("gemini-4-argon-medium", persistent=True)
        assert isinstance(calibration, taxonomy_bench_cli.AgyCliProvider)
        lane_home = out / "agy-home" / "gemini-4-argon-medium"
        assert calibration.home == (lane_home / "calibration").resolve()
        assert primary.home == (lane_home / "primary").resolve()
        assert calibration.subject_root == subject
        assert primary.persistent and not calibration.persistent

    def test_google_pair_runs_with_fake_agy_and_leaves_wave_one_barrier_alone(
        self, tmp_path: Path, monkeypatch
    ):
        wave1, _, control, _ = _prepared_wave(tmp_path)
        google, out = _prepared_google_wave(tmp_path, control)
        suite = tb.load_suite(out / "suite.private.json")
        subject = tmp_path / "subject"
        subject.mkdir()
        monkeypatch.setattr(
            taxonomy_bench_cli.shutil, "which", lambda name: f"C:/fake/{name}.exe"
        )
        conversations: dict[str, str] = {}
        runner = _fake_agy_runner(suite, conversations)

        def factory(lane_id: str, persistent: bool):
            return taxonomy_bench_cli.AgyCliProvider(
                selector=lane_id,
                subject_root=subject,
                persistent=persistent,
                home=out / "agy-home" / lane_id / ("primary" if persistent else "calibration"),
                runner=runner,
            )

        for lane_id in GOOGLE_LANES:
            controller = wave.WaveController(
                manifest_path=out / "manifest.json",
                control_root=control,
                subject_root=subject,
                wave_dir=out,
                provider_factory=factory,
            )
            assert controller.run_lane(lane_id) == 0
            state = wave.LaneState.load(out / "lanes" / lane_id)
            assert state.status == "complete"
            assert len(state.accepted_run_ids) == 3
            for run_id in (state.calibration_run_id, *state.accepted_run_ids):
                text = (out / "runs" / run_id / "run.json").read_text(encoding="utf-8")
                assert "agy-conversation-" not in text

        report = wave.aggregate_pair(out / "manifest.json", 1)
        matrix = json.loads((report / "matrix.json").read_text(encoding="utf-8"))
        assert len(matrix["accepted_run_ids"]) == 6
        assert wave.pair_can_start(google, control, 2)
        assert not wave.pair_can_start(wave1, control, 2)
        assert (out / "agy-home" / GOOGLE_LANES[0] / "primary" / ".gemini"
                / "antigravity-cli" / "settings.json").exists()


class TestSharedControllerRoots:
    def test_aggregation_markers_are_scoped_to_their_manifest(self, tmp_path: Path):
        wave.record_aggregation(tmp_path, "manifest-a", 1)
        wave.record_aggregation(tmp_path, "manifest-b", 1)
        assert wave.pair_can_start({"manifest_hash": "manifest-a"}, tmp_path, 2)
        assert wave.pair_can_start({"manifest_hash": "manifest-b"}, tmp_path, 2)
        assert not wave.pair_can_start({"manifest_hash": "manifest-c"}, tmp_path, 2)

    def test_pair_locks_are_scoped_to_their_manifest(self, tmp_path: Path):
        lock_a = wave.PairLock(tmp_path, 1, "manifest-a")
        lock_b = wave.PairLock(tmp_path, 1, "manifest-b")
        try:
            with pytest.raises(BenchError):
                wave.PairLock(tmp_path, 1, "manifest-a")
        finally:
            lock_a.release()
            lock_b.release()

    def test_subject_root_keeps_one_marker_per_manifest(self, tmp_path: Path):
        wave1, _, control, wave1_out = _prepared_wave(tmp_path)
        google, google_out = _prepared_google_wave(tmp_path, control)
        subject = tmp_path / "subject"
        subject.mkdir()

        def controller(out: Path) -> wave.WaveController:
            return wave.WaveController(
                manifest_path=out / "manifest.json",
                control_root=control,
                subject_root=subject,
                wave_dir=out,
            )

        for out in (wave1_out, google_out, wave1_out):
            controller(out).validate_subject_root()
        for manifest in (wave1, google):
            marker = wave.subject_root_marker(subject, manifest["manifest_hash"])
            assert json.loads(marker.read_text(encoding="utf-8"))[
                "manifest_hash"
            ] == manifest["manifest_hash"]

        wave.subject_root_marker(subject, google["manifest_hash"]).write_text(
            json.dumps({"manifest_hash": "tampered"}), encoding="utf-8"
        )
        with pytest.raises(BenchError, match="marker"):
            controller(google_out).validate_subject_root()

    @pytest.mark.parametrize("name", ["GEMINI.md", ".gemini", "AGENTS.md"])
    def test_subject_root_rejects_agent_instruction_files(self, tmp_path: Path, name: str):
        _, _, control, out = _prepared_wave(tmp_path)
        subject = tmp_path / "subject"
        subject.mkdir()
        (subject / name).write_text("rules", encoding="utf-8")
        controller = wave.WaveController(
            manifest_path=out / "manifest.json",
            control_root=control,
            subject_root=subject,
            wave_dir=out,
        )
        with pytest.raises(BenchError, match="forbidden entry"):
            controller.validate_subject_root()

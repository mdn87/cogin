"""Wave 1 controller tests with fake providers."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

import taxonomy_bench as tb
import taxonomy_bench_cli
import taxonomy_bench_protocol
import taxonomy_bench_wave as wave
from taxonomy_bench_cli import Completion, ProcessResult
from taxonomy_bench_protocol import BASE_INSTRUCTIONS, BenchError, canonical_hash

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
    pass  # Expanded in later tests with run orchestration


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
"""Wave 1 benchmark orchestration.

Immutable manifests, deterministic calibration selection, family locks,
restartable lane state, admission barriers, and pair aggregation for
subscription-backed CLI benchmarks.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import hashlib
import json
import os
import sys
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from taxonomy_bench_cli import ClaudeCliProvider, CodexCliProvider, Completion, Provider
from taxonomy_bench_protocol import BenchError, canonical_hash, canonical_json


# ---------------------------------------------------------------------------
# Wave 1 protocol constants
# ---------------------------------------------------------------------------

WAVE1_VERSION = "1.0.0"
WAVE1_PROTOCOL = {
    "version": WAVE1_VERSION,
    "medium_effort": True,
    "isolated_sessions": True,
    "prompt_output_mode": True,
    "zero_transport_retries": True,
    "primary_repeats": 3,
    "max_feedback_retries": 2,
    "strict_pair_barrier": True,
    "calibration_task_count": 8,
}

WAVE1_PAIRS = (
    ("claude-opus-5", "gpt-5.6-sol"),
    ("claude-sonnet-5", "gpt-5.6-terra"),
    ("claude-fable-5", "gpt-5.6-luna"),
)

# Lane registry: selector -> family + expected resolved model pattern
WAVE1_LANES: dict[str, dict[str, str]] = {}
for pair in WAVE1_PAIRS:
    WAVE1_LANES[pair[0]] = {"family": "claude", "selector": pair[0], "expected_model": pair[0]}
    WAVE1_LANES[pair[1]] = {"family": "codex", "selector": pair[1], "expected_model": pair[1]}


# ---------------------------------------------------------------------------
# Manifest hashing and preparation
# ---------------------------------------------------------------------------


def compute_suite_sha256(suite_path: Path) -> str:
    """Compute SHA-256 of the private suite file."""
    return hashlib.sha256(suite_path.read_bytes()).hexdigest()


def deterministic_calibration_ids(suite: Mapping[str, Any]) -> list[str]:
    """Select exactly 8 calibration task IDs (first 2 per tier 1-4)."""
    by_tier: dict[int, list[str]] = {}
    for task in suite.get("tasks", []):
        tier = int(task.get("tier", 0))
        by_tier.setdefault(tier, []).append(task["id"])
    selected: list[str] = []
    for tier in sorted(by_tier):
        if tier > 4:
            break
        tier_ids = sorted(by_tier[tier])
        selected.extend(tier_ids[:2])
    if len(selected) != 8:
        raise BenchError(f"Calibration selection expected 8 IDs, got {len(selected)}")
    return selected


def prepare_manifest(
    suite: Mapping[str, Any],
    suite_path: Path,
    control_root: Path,
    provider_metadata: Mapping[str, Any],
    out_dir: Path,
) -> dict[str, Any]:
    """Create an immutable Wave 1 manifest.

    Idempotent: returns existing manifest if the deterministic input
    fingerprint matches. Never overwrites an existing manifest.
    """
    manifest_path = out_dir / "manifest.json"

    # Compute deterministic input fingerprint first
    input_fingerprint_data: dict[str, Any] = {
        "protocol_version": WAVE1_VERSION,
        "protocol_hash": canonical_hash(WAVE1_PROTOCOL),
        "suite_sha256": compute_suite_sha256(suite_path),
        "suite_path": str(suite_path.absolute()),
        "calibration_ids": deterministic_calibration_ids(suite),
        "base_instruction_hash": provider_metadata.get("instruction_hash", canonical_hash(
            __import__("taxonomy_bench_protocol", fromlist=["BASE_INSTRUCTIONS"]).BASE_INSTRUCTIONS
        )),
        "diagnostic_feedback_policy_hash": canonical_hash({"feedback": True, "max_retries": WAVE1_PROTOCOL["max_feedback_retries"]}),
        "provider_invocation_hash": provider_metadata.get("invocation_hash", "unknown"),
        "tool_policy_hash": provider_metadata.get("tool_policy_hash", "unknown"),
        "control_root": str(control_root.absolute()),
        "lanes": WAVE1_LANES,
        "pairs": [list(p) for p in WAVE1_PAIRS],
        "cli_versions": {
            "codex": provider_metadata.get("codex_version", "unknown"),
            "claude": provider_metadata.get("claude_version", "unknown"),
        },
    }
    input_fingerprint = canonical_hash(input_fingerprint_data)

    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        existing_fingerprint = existing.get("input_fingerprint")
        if existing_fingerprint == input_fingerprint:
            # Validate stored content hash
            stored_hash = existing.get("manifest_hash")
            content = {k: v for k, v in existing.items() if k != "manifest_hash"}
            actual_hash = canonical_hash(content)
            if stored_hash == actual_hash:
                return existing
            raise BenchError("Existing manifest has invalid content hash; won't overwrite")
        raise BenchError(
            "Input fingerprint differs from existing manifest. "
            "Delete the manifest manually if you intend to regenerate."
        )

    # Build manifest
    manifest: dict[str, Any] = {
        **input_fingerprint_data,
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "input_fingerprint": input_fingerprint,
    }
    manifest["manifest_hash"] = canonical_hash(manifest)

    out_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = manifest_path.with_suffix(".tmp")
    tmp_path.write_text(canonical_json(manifest) + "\n", encoding="utf-8")
    tmp_path.replace(manifest_path)
    return manifest


# ---------------------------------------------------------------------------
# Family locks (cross-process advisory file locks on Windows)
# ---------------------------------------------------------------------------


class FamilyLock:
    """Advisory file lock for a provider family."""

    def __init__(self, control_root: Path, family: str) -> None:
        self._path = control_root / f"{family}.lock"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = open(str(self._path), "w")
        try:
            import msvcrt
            msvcrt.locking(self._handle.fileno(), msvcrt.LK_NBLCK, 1)
        except (ImportError, OSError):
            try:
                import fcntl
                fcntl.flock(self._handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except (ImportError, OSError):
                self._handle.close()
                raise BenchError(f"Cannot acquire {family} lock; another process may hold it")

    def release(self) -> None:
        try:
            if self._handle and not self._handle.closed:
                self._handle.close()
        except Exception:
            pass

    def __del__(self) -> None:
        self.release()


# ---------------------------------------------------------------------------
# Lane state (restartable execution)
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class LaneState:
    lane: str
    pair_index: int
    manifest_hash: str
    provider_fingerprint: str
    status: str  # "pending", "calibrating", "running", "complete", "invalidated"
    calibration_run_id: str | None = None
    completed_primary_repeat_numbers: list[int] = dataclasses.field(default_factory=list)
    accepted_run_ids: list[str] = dataclasses.field(default_factory=list)
    abandoned_run_ids: list[str] = dataclasses.field(default_factory=list)
    current_phase: str = "init"
    invalidation_reason: str | None = None
    completed_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "LaneState":
        field_names = {f.name for f in dataclasses.fields(cls)}
        kwargs = {k: data.get(k) for k in field_names if k in data}
        return cls(**kwargs)

    def save(self, state_dir: Path) -> None:
        state_dir.mkdir(parents=True, exist_ok=True)
        payload = canonical_json(self.to_dict()) + "\n"
        tmp = state_dir / "state.json.tmp"
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(state_dir / "state.json")

    @classmethod
    def load(cls, state_dir: Path) -> "LaneState":
        path = state_dir / "state.json"
        if not path.exists():
            raise BenchError(f"No lane state at {state_dir}")
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def validate_continuation(self, manifest: Mapping[str, Any], provider: Provider) -> None:
        """Raise BenchError if the provider fingerprint changed."""
        expected_manifest_hash = manifest.get("manifest_hash", "")
        if self.manifest_hash != expected_manifest_hash:
            raise BenchError(f"Manifest hash changed; lane {self.lane} is invalidated")

        # Check provider hashes
        invocation = getattr(provider, "invocation_hash", "")
        tool_policy = getattr(provider, "tool_policy_hash", "")
        combined = canonical_hash({"invocation": invocation, "tool_policy": tool_policy})
        if self.provider_fingerprint != combined:
            raise BenchError(
                f"Provider fingerprint drift for lane {self.lane}; lane is invalidated"
            )


# ---------------------------------------------------------------------------
# Pair barriers
# ---------------------------------------------------------------------------


def _aggregation_complete_marker(control_root: Path, pair_index: int) -> Path:
    return control_root / f"pair-{pair_index}.aggregated"


def pair_can_start(
    manifest: Mapping[str, Any],
    control_root: Path,
    pair_index: int,
) -> bool:
    """Pair N can start only when Pair N-1 has an aggregation marker."""
    if pair_index <= 1:
        return True
    prev_marker = _aggregation_complete_marker(control_root, pair_index - 1)
    if not prev_marker.exists():
        return False
    # Verify the marker's manifest hash
    try:
        data = json.loads(prev_marker.read_text(encoding="utf-8"))
        return data.get("manifest_hash") == manifest.get("manifest_hash")
    except Exception:
        return False


def pair_can_aggregate(
    manifest: Mapping[str, Any],
    control_root: Path,
    pair_index: int,
    lane_states: Sequence[LaneState],
) -> bool:
    """Pair aggregation requires both lane states to be complete with 3 accepted runs."""
    pair_lanes = [s for s in lane_states if s.pair_index == pair_index]
    if len(pair_lanes) != 2:
        return False
    for state in pair_lanes:
        if state.status != "complete":
            return False
        if len(state.accepted_run_ids) < 3:
            return False
    return True


def record_aggregation(control_root: Path, manifest_hash: str, pair_index: int) -> None:
    marker = _aggregation_complete_marker(control_root, pair_index)
    marker.write_text(canonical_json({"manifest_hash": manifest_hash, "pair": pair_index}), encoding="utf-8")


# ---------------------------------------------------------------------------
# Wave controller
# ---------------------------------------------------------------------------


class WaveController:
    """Orchestrates Wave 1 preparation, calibration, and lane execution."""

    def __init__(
        self,
        manifest_path: Path,
        control_root: Path,
        subject_root: Path,
        wave_dir: Path,
    ) -> None:
        self.manifest_path = manifest_path
        self.control_root = control_root
        self.subject_root = subject_root
        self.wave_dir = wave_dir
        self.manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self._validate_manifest()

    def _validate_manifest(self) -> None:
        required = {"manifest_hash", "input_fingerprint", "pairs", "lanes", "calibration_ids",
                     "suite_sha256", "base_instruction_hash", "control_root"}
        missing = required - set(self.manifest.keys())
        if missing:
            raise BenchError(f"Manifest missing required fields: {missing}")
        stored = self.manifest["manifest_hash"]
        content = {k: v for k, v in self.manifest.items() if k != "manifest_hash"}
        actual = canonical_hash(content)
        if stored != actual:
            raise BenchError("Manifest content hash mismatch")

    def validate_subject_root(self) -> None:
        """Ensure the subject root is a sterile directory outside Cogin."""
        subject = self.subject_root.resolve()
        if not subject.exists() or not subject.is_dir():
            raise BenchError(f"Subject root {subject} does not exist or is not a directory")
        # Check for disallowed contents
        disallowed = {".git", "AGENTS.md", "CLAUDE.md", "manifest.json"}
        entries = set()
        for entry in subject.iterdir():
            entries.add(entry.name)
            if entry.name in disallowed:
                raise BenchError(f"Subject root contains forbidden entry: {entry.name}")
            if entry.is_symlink():
                raise BenchError(f"Subject root contains symlink: {entry.name}")

        # Check marker
        marker = subject / ".wave1-subject-root"
        if marker.exists():
            data = json.loads(marker.read_text(encoding="utf-8"))
            if data.get("manifest_hash") != self.manifest.get("manifest_hash"):
                raise BenchError("Subject root marker manifest hash mismatch")
        else:
            # Write marker on first validation
            marker.write_text(canonical_json({
                "manifest_hash": self.manifest["manifest_hash"],
                "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            }), encoding="utf-8")

    def build_provider(self, lane_id: str, persistent: bool = False) -> Provider:
        """Build a subscription provider for the given lane."""
        lanes = self.manifest.get("lanes", {})
        lane_info = lanes.get(lane_id)
        if not lane_info:
            raise BenchError(f"Lane {lane_id} not found in manifest")

        family = lane_info["family"]
        selector = lane_info["selector"]
        expected_model = lane_info.get("expected_model", selector)

        if family == "claude":
            return ClaudeCliProvider(
                selector=selector,
                expected_model=expected_model,
                subject_root=self.subject_root,
                persistent=persistent,
            )
        elif family == "codex":
            return CodexCliProvider(
                selector=selector,
                expected_model=expected_model,
                subject_root=self.subject_root,
                persistent=persistent,
            )
        raise BenchError(f"Unknown family: {family}")
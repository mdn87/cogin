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
import shutil
import subprocess
import sys
import time
import uuid
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Callable, MutableMapping

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


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _atomic_write_json(path: Path, value: Mapping[str, Any]) -> None:
    """Durably replace one JSON file without deleting prior evidence."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    payload = (canonical_json(value) + "\n").encode("utf-8")
    with tmp.open("wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def _cli_version(executable: str) -> str:
    path = shutil.which(executable)
    if path is None:
        return "unavailable"
    try:
        result = subprocess.run(
            [path, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    text = (result.stdout or result.stderr).strip()
    return text or "unknown"


def collect_provider_metadata() -> dict[str, Any]:
    """Collect deterministic invocation policy and installed CLI versions.

    This preparation step never checks authentication or invokes a model.
    """
    versions = {"claude": _cli_version("claude"), "codex": _cli_version("codex")}
    lanes: dict[str, dict[str, str]] = {}
    for lane_id, lane in WAVE1_LANES.items():
        family = lane["family"]
        selector = lane["selector"]
        if family == "claude":
            invocation = canonical_hash({
                "selector": selector,
                "effort": "medium",
                "tools": "",
                "safe_mode": True,
                "no_chrome": True,
                "disable_slash_commands": True,
            })
            tool_policy = canonical_hash({
                "tools": "",
                "safe_mode": True,
                "strict_mcp_config": True,
            })
        else:
            invocation = canonical_hash({
                "selector": selector,
                "sandbox": "read-only",
                "ignore_user_config": True,
                "ignore_rules": True,
            })
            tool_policy = canonical_hash({
                "sandbox": "read-only",
                "ignore_user_config": True,
                "ignore_rules": True,
            })
        lanes[lane_id] = {
            "family": family,
            "requested_model": selector,
            "expected_model": lane["expected_model"],
            "cli_version": versions[family],
            "invocation_hash": invocation,
            "tool_policy_hash": tool_policy,
            "auth_mode": "subscription",
        }
    return {
        "instruction_hash": canonical_hash(
            __import__(
                "taxonomy_bench_protocol", fromlist=["BASE_INSTRUCTIONS"]
            ).BASE_INSTRUCTIONS
        ),
        "cli_versions": versions,
        "lanes": lanes,
    }


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
    if not control_root.exists() or not control_root.is_dir():
        raise BenchError(
            f"Control root {control_root} must already exist and be a directory"
        )
    manifest_path = out_dir / "manifest.json"
    lane_metadata = dict(provider_metadata.get("lanes", {}))
    cli_versions = dict(provider_metadata.get("cli_versions", {}))
    if not cli_versions:
        cli_versions = {
            "codex": provider_metadata.get("codex_version", "unknown"),
            "claude": provider_metadata.get("claude_version", "unknown"),
        }
    if not lane_metadata:
        for lane_id, lane in WAVE1_LANES.items():
            lane_metadata[lane_id] = {
                "family": lane["family"],
                "requested_model": lane["selector"],
                "expected_model": lane["expected_model"],
                "cli_version": cli_versions.get(lane["family"], "unknown"),
                "invocation_hash": provider_metadata.get("invocation_hash", "unknown"),
                "tool_policy_hash": provider_metadata.get("tool_policy_hash", "unknown"),
                "auth_mode": "subscription",
            }

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
        "lane_metadata": lane_metadata,
        "control_root": str(control_root.absolute()),
        "suite_filename": "suite.private.json",
        "lanes": WAVE1_LANES,
        "pairs": [list(p) for p in WAVE1_PAIRS],
        "cli_versions": cli_versions,
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
                suite_copy = out_dir / existing.get("suite_filename", "suite.private.json")
                if (
                    not suite_copy.exists()
                    or compute_suite_sha256(suite_copy) != existing["suite_sha256"]
                ):
                    raise BenchError("Wave private suite copy is missing or has changed")
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
    suite_copy = out_dir / manifest["suite_filename"]
    if suite_copy.exists():
        if suite_copy.read_bytes() != suite_path.read_bytes():
            raise BenchError("Existing Wave private suite copy conflicts with input")
    else:
        tmp_suite = out_dir / f".suite.private.{uuid.uuid4().hex}.tmp"
        with tmp_suite.open("wb") as handle:
            handle.write(suite_path.read_bytes())
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_suite, suite_copy)
    _atomic_write_json(manifest_path, manifest)
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

    def __enter__(self) -> "FamilyLock":
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.release()

    def __del__(self) -> None:
        self.release()


class PairLock(FamilyLock):
    def __init__(self, control_root: Path, pair_index: int) -> None:
        super().__init__(control_root, f"pair-{pair_index}")


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
        _atomic_write_json(state_dir / "state.json", self.to_dict())

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
    _atomic_write_json(
        marker, {"manifest_hash": manifest_hash, "pair": pair_index}
    )


# ---------------------------------------------------------------------------
# Calibration admission and Wave-only attempt persistence
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class AdmissionResult:
    passed: bool
    reasons: tuple[str, ...]


def _record_value(run_record: Mapping[str, Any], key: str) -> Any:
    if key in run_record:
        return run_record.get(key)
    return run_record.get("configuration", {}).get(key)


def _ordered_attempts(
    run_record: Mapping[str, Any],
) -> tuple[list[str], list[Mapping[str, Any]]]:
    if "tasks" in run_record:
        tasks = list(run_record.get("tasks", []))
        return (
            [str(task.get("task_id", "")) for task in tasks],
            [
                attempt
                for task in tasks
                for attempt in list(task.get("attempts", []))[:1]
            ],
        )
    attempts = list(run_record.get("attempts", []))
    task_ids = list(run_record.get("task_ids", []))
    if not task_ids:
        task_ids = [str(attempt.get("task_id", "")) for attempt in attempts]
    return [str(value) for value in task_ids], attempts


def admit_calibration(
    run_record: Mapping[str, Any],
    manifest: Mapping[str, Any],
    lane_id: str,
) -> AdmissionResult:
    """Apply the objective structural gate to a completed calibration."""
    reasons: list[str] = []
    lane = manifest["lanes"][lane_id]
    lane_meta = manifest.get("lane_metadata", {}).get(lane_id, {})
    task_ids, attempts = _ordered_attempts(run_record)
    calibration_ids = [str(value) for value in manifest["calibration_ids"]]

    if task_ids != calibration_ids:
        reasons.append("task_ids_mismatch")
    if len(attempts) != len(calibration_ids):
        reasons.append("attempt_count")
    for index, attempt in enumerate(attempts):
        task_id = task_ids[index] if index < len(task_ids) else f"attempt-{index + 1}"
        scored = attempt.get("scored")
        if scored is None:
            scored = attempt.get("score") is not None
        if not scored:
            reasons.append(f"unscored:{task_id}")
        latency = attempt.get("latency_ms")
        if not isinstance(latency, (int, float)) or latency < 0:
            reasons.append(f"latency:{task_id}")
        if attempt.get("error_kind"):
            reasons.append(
                f"infrastructure:{task_id}:{attempt.get('error_kind')}"
            )

    if _record_value(run_record, "suite_sha256") != manifest["suite_sha256"]:
        reasons.append("suite_hash_mismatch")
    requested = _record_value(run_record, "requested_model")
    if requested is None:
        requested = _record_value(run_record, "model")
    if requested != lane["selector"]:
        reasons.append("requested_model_mismatch")
    resolved = _record_value(run_record, "resolved_model")
    if resolved is None:
        resolved_models = run_record.get("summary", {}).get("resolved_models", [])
        if len(resolved_models) == 1:
            resolved = resolved_models[0]
    if resolved != lane["expected_model"]:
        reasons.append("resolved_model_mismatch")

    expected_hashes = {
        "base_instruction_hash": manifest["base_instruction_hash"],
        "tool_policy_hash": lane_meta.get(
            "tool_policy_hash", manifest.get("tool_policy_hash")
        ),
        "invocation_hash": lane_meta.get(
            "invocation_hash", manifest.get("provider_invocation_hash")
        ),
    }
    for key, expected in expected_hashes.items():
        if _record_value(run_record, key) != expected:
            reasons.append(f"{key}_mismatch")

    run_versions = _record_value(run_record, "cli_versions")
    if run_versions is None:
        run_version = _record_value(run_record, "cli_version")
        expected_version = lane_meta.get("cli_version")
        if run_version != expected_version:
            reasons.append("cli_version_mismatch")
    elif run_versions != manifest["cli_versions"]:
        reasons.append("cli_version_mismatch")
    return AdmissionResult(not reasons, tuple(sorted(set(reasons))))


class WaveInfrastructureAbort(BenchError):
    def __init__(self, error_kind: str, run_id: str) -> None:
        super().__init__(f"infrastructure {error_kind} in run {run_id}")
        self.error_kind = error_kind
        self.run_id = run_id


def redact_task_sessions(
    task_record: MutableMapping[str, Any], *, final: bool
) -> None:
    """Clear resumable identifiers once a task's retry window is closed."""
    if not final:
        return
    trace_values: list[str] = []
    base = task_record.pop("base_previous_response_id", None)
    if base:
        trace_values.append(str(base))
    for attempt in task_record.get("attempts", []):
        raw = attempt.pop("response_id", None)
        if raw:
            raw_text = str(raw)
            trace_values.append(raw_text)
            attempt["session_trace_hash"] = hashlib.sha256(
                raw_text.encode("utf-8")
            ).hexdigest()
    if trace_values:
        task_record["session_trace_hash"] = canonical_hash(trace_values)


def make_wave_checkpoint(state_dir: Path) -> Callable[[str, Mapping[str, Any]], None]:
    """Persist every attempt, redact closed sessions, then abort on infra."""

    def checkpoint(run_id: str, envelope: Mapping[str, Any]) -> None:
        mutable = envelope  # execute_run supplies its live mutable envelope
        tasks = list(mutable.get("tasks", []))
        if not tasks:
            return
        current = tasks[-1]
        attempts = list(current.get("attempts", []))
        last = attempts[-1]
        error_kind = last.get("error_kind")
        if error_kind:
            for task in tasks:
                redact_task_sessions(task, final=True)
        else:
            exact = bool((last.get("score") or {}).get("exact"))
            retries = int(mutable.get("configuration", {}).get("retries", 0))
            exhausted = int(last.get("attempt", 1)) >= retries + 1
            redact_task_sessions(current, final=exact or exhausted)
        _atomic_write_json(state_dir / f"{run_id}.envelope.json", mutable)
        if error_kind:
            raise WaveInfrastructureAbort(str(error_kind), run_id)

    return checkpoint


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
        provider_factory: Callable[[str, bool], Provider] | None = None,
    ) -> None:
        self.manifest_path = manifest_path
        self.control_root = control_root
        self.subject_root = subject_root
        self.wave_dir = wave_dir
        self.provider_factory = provider_factory
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
        recorded_control = Path(self.manifest["control_root"]).resolve()
        if recorded_control != self.control_root.resolve():
            raise BenchError(
                "Controller root does not match the immutable manifest"
            )

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
        if self.provider_factory is not None:
            return self.provider_factory(lane_id, persistent)
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

    def preflight_lane(self, lane_id: str) -> dict[str, Any]:
        self.validate_subject_root()
        provider = self.build_provider(lane_id, persistent=False)
        result = provider.preflight()
        lane = self.manifest["lanes"][lane_id]
        lane_meta = self.manifest.get("lane_metadata", {}).get(lane_id, {})
        cli_version = (
            provider._cli_version()
            if hasattr(provider, "_cli_version")
            else result.get("cli_version", lane_meta.get("cli_version", "unknown"))
        )
        return {
            "lane": lane_id,
            "auth_mode": getattr(provider, "auth_mode", "subscription"),
            "requested_model": lane["selector"],
            "resolved_model": result.get(
                "resolved_model", getattr(provider, "expected_model", lane["expected_model"])
            ),
            "cli_version": cli_version,
            "tool_policy_hash": getattr(
                provider, "tool_policy_hash", lane_meta.get("tool_policy_hash")
            ),
            "invocation_hash": getattr(
                provider, "invocation_hash", lane_meta.get("invocation_hash")
            ),
        }

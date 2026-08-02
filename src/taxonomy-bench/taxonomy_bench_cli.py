"""Subscription CLI provider infrastructure.

This module defines the base provider contract for subscription-backed
CLI invocation (Claude Code, Codex). It imports from taxonomy_bench_protocol
but never from taxonomy_bench (the main module imports from here).
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class Completion:
    """Result of a single provider completion call."""

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
    """Abstract base for all benchmark providers."""

    supports_sessions: bool = False

    def complete(
        self,
        prompt: str,
        output_schema: Mapping[str, Any],
        previous_response_id: str | None = None,
    ) -> Completion:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Infrastructure error classification
# ---------------------------------------------------------------------------

INFRA_ERROR_KINDS = frozenset({
    "authentication",
    "entitlement",
    "rate_limit",
    "timeout",
    "process",
    "malformed_provider_output",
    "model_mismatch",
    "fallback",
    "isolation",
})


# ---------------------------------------------------------------------------
# Process runner seam (injectable for testing)
# ---------------------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class ProcessResult:
    """Result of a subprocess invocation."""

    args: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str
    latency_ms: float


ProcessRunner = Callable[
    [Sequence[str], str, Path, float, Mapping[str, str]],
    ProcessResult,
]
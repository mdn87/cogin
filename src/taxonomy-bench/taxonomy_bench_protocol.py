"""Benchmark protocol constants and shared helpers.

This module owns the base instructions, canonical representations, and
shared exception types. It never imports taxonomy_bench, taxonomy_bench_cli,
or taxonomy_bench_wave.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


BASE_INSTRUCTIONS = (
    "You are being evaluated on closed-book reasoning over a supplied graph. "
    "Use only the supplied context. Follow the requested output schema exactly. "
    "Return one JSON object and no explanation, markdown, or surrounding text."
)


class BenchError(RuntimeError):
    """Raised for invalid benchmark configuration or data."""


def canonical_json(obj: Any) -> str:
    """Produce a UTF-8 canonical JSON string with sorted keys and compact separators."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical_hash(obj: Any) -> str:
    """SHA-256 of canonical_json(obj)."""
    raw = canonical_json(obj).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def compose_subject_prompt(prompt: str) -> str:
    """Join the base instructions and a task prompt for a fresh CLI subject session."""
    return f"{BASE_INSTRUCTIONS}\n\n{prompt}"
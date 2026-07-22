from __future__ import annotations

import math
from typing import Any, Mapping


KIND_SCORERS = {
    "semantic_match": "id",
    "direct_prerequisites": "ids_set",
    "reverse_unlocks": "ids_set",
    "transitive_prerequisites": "ids_set",
    "topological_order": "topological_order",
    "shortest_path": "shortest_path",
    "mastery_plan": "mastery_plan",
    "integrity_audit": "issues_set",
}

UNSUPPORTED_OUTPUT_CODES = {
    "set.extra",
    "path.invalid_edge",
    "integrity.false_positive",
}


def wilson_interval(
    successes: int,
    total: int,
    z: float = 1.96,
) -> tuple[float | None, float | None]:
    if total <= 0:
        return None, None
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total) / denominator
    return max(0.0, center - margin), min(1.0, center + margin)


def derive_attempt_outcome(kind: str, attempt: Mapping[str, Any]) -> dict[str, Any]:
    usage = attempt.get("usage")
    tokens = usage.get("total_tokens") if usage else None
    latency_ms = attempt.get("latency_ms")
    error = attempt.get("error")
    score = attempt.get("score")

    if error or score is None:
        return {
            "exact": None,
            "partial": None,
            "outcome": "unscored",
            "label": "Unscored",
            "codes": ["infrastructure"],
            "failure_summary": str(error) if error else "Score unavailable.",
            "latency_ms": latency_ms,
            "tokens": tokens,
        }

    exact = bool(score.get("exact"))
    partial = score.get("partial")
    if exact:
        return {
            "exact": True,
            "partial": partial,
            "outcome": "exact",
            "label": "Exact",
            "codes": [],
            "failure_summary": None,
            "latency_ms": latency_ms,
            "tokens": tokens,
        }

    details = score.get("details") or {}
    feedback = score.get("feedback") or "Non-exact response."
    if not score.get("strict_json") and not score.get("recovered_json"):
        codes = ["format.unparseable"]
    elif (
        (kind == "semantic_match" and details.get("actual_type") != "str")
        or "must be an array of strings." in feedback
    ):
        codes = ["format.wrong_shape"]
    else:
        codes = _derive_kind_codes(kind, details)

    return {
        "exact": False,
        "partial": partial,
        "outcome": "non-exact",
        "label": "Non-exact",
        "codes": codes,
        "failure_summary": feedback,
        "latency_ms": latency_ms,
        "tokens": tokens,
    }


def _derive_kind_codes(kind: str, details: Mapping[str, Any]) -> list[str]:
    codes: list[str] = []
    if kind == "semantic_match":
        codes.append("selection.incorrect")
    elif KIND_SCORERS.get(kind) == "ids_set":
        if details.get("missing_count", 0) > 0:
            codes.append("set.missing")
        if details.get("extra_count", 0) > 0:
            codes.append("set.extra")
        if details.get("duplicate_count", 0) > 0:
            codes.append("sequence.duplicate")
    elif kind == "topological_order":
        if details.get("node_f1", 1.0) < 1.0:
            codes.append("order.node_coverage")
        if details.get("violated_edges", 0) > 0:
            codes.append("order.precedence")
        if details.get("duplicate_count", 0) > 0:
            codes.append("sequence.duplicate")
    elif kind == "shortest_path":
        if not details.get("endpoints_ok", True):
            codes.append("path.endpoint")
        if details.get("step_compliance", 1.0) < 1.0:
            codes.append("path.invalid_edge")
        if not details.get("length_ok", True):
            codes.append("path.non_shortest")
        if not details.get("unique", True):
            codes.append("sequence.duplicate")
    elif kind == "mastery_plan":
        if details.get("set_f1", 1.0) < 1.0:
            codes.append("plan.coverage")
        if details.get("edge_compliance", 1.0) < 1.0:
            codes.append("plan.dependency")
        if not details.get("target_last", True):
            codes.append("plan.target_not_last")
        if details.get("duplicate_count", 0) > 0:
            codes.append("sequence.duplicate")
    elif kind == "integrity_audit":
        if details.get("missing_count", 0) > 0:
            codes.append("integrity.miss")
        if details.get("extra_count", 0) > 0:
            codes.append("integrity.false_positive")
        if details.get("duplicate_count", 0) > 0:
            codes.append("sequence.duplicate")
    return codes

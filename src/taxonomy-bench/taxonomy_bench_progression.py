from __future__ import annotations

import math
import statistics
from collections import Counter, defaultdict, deque
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


def infer_typical_tier_size(records: list[Mapping[str, Any]]) -> int:
    counts = Counter(record.get("tier") for record in records if record.get("tier") is not None)
    return math.ceil(statistics.median(counts.values())) if counts else 0


def derive_tier_rows(task_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    for row in task_rows:
        if row.get("tier") is not None:
            grouped[row["tier"]].append(row)

    tiers: list[dict[str, Any]] = []
    for tier in sorted(grouped):
        tasks = grouped[tier]
        scored = [row for row in tasks if row.get("exact") is not None]
        exact_count = sum(row["exact"] is True for row in scored)
        partials = [float(row["partial"]) for row in scored if row.get("partial") is not None]
        latencies = [float(row["latency_ms"]) for row in scored if row.get("latency_ms") is not None]
        scored_count = len(scored)
        limited = scored_count < 4
        tiers.append(
            {
                "tier": tier,
                "task_count": len(tasks),
                "scored_count": scored_count,
                "exact_count": exact_count,
                "exact_rate": exact_count / scored_count if scored_count else None,
                "partial_mean": statistics.fmean(partials) if partials else None,
                "median_latency_ms": statistics.median(latencies) if latencies else None,
                "limited_evidence": limited,
                "evidence_note": (
                    f"limited evidence · {scored_count} scored"
                    if limited
                    else f"{scored_count} scored"
                ),
                "tasks": tasks,
            }
        )
    return tiers


def _derive_task_family_rows(task_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in task_rows:
        grouped[row["kind"]].append(row)

    families: list[dict[str, Any]] = []
    for kind, tasks in grouped.items():
        scored = [row for row in tasks if row.get("exact") is not None]
        exact_count = sum(row["exact"] is True for row in scored)
        partials = [float(row["partial"]) for row in scored if row.get("partial") is not None]
        unsupported_count = sum(
            any(code in UNSUPPORTED_OUTPUT_CODES for code in row["codes"])
            for row in scored
        )
        families.append(
            {
                "kind": kind,
                "task_count": len(tasks),
                "scored_count": len(scored),
                "exact_count": exact_count,
                "exact_rate": exact_count / len(scored) if scored else None,
                "partial_mean": statistics.fmean(partials) if partials else None,
                "unsupported_output_count": unsupported_count,
                "unsupported_output_rate": unsupported_count / len(scored) if scored else None,
            }
        )
    return families


def derive_rolling_points(
    task_rows: list[dict[str, Any]],
    window_size: int,
) -> list[dict[str, Any]]:
    window: deque[dict[str, Any]] = deque(maxlen=window_size or None)
    points: list[dict[str, Any]] = []
    for row in task_rows:
        identity = {
            "sequence_index": row["sequence_index"],
            "task_id": row["task_id"],
            "sample_count": len(window),
            "window_size": window_size,
        }
        if row.get("exact") is None:
            points.append({**identity, "exact_rate": None, "partial_mean": None})
            continue
        window.append(row)
        partials = [float(item["partial"]) for item in window if item.get("partial") is not None]
        points.append(
            {
                **identity,
                "sample_count": len(window),
                "exact_rate": sum(item["exact"] is True for item in window) / len(window),
                "partial_mean": statistics.fmean(partials) if partials else None,
            }
        )
    return points


def derive_markers(
    task_rows: list[dict[str, Any]],
    tier_rows: list[dict[str, Any]],
    summary: Mapping[str, Any],
) -> dict[str, Any]:
    frontier = summary.get("reliable_frontier_first", 0)
    peak = summary.get("peak_tier_first", 0)
    first_miss_row = next((row for row in task_rows if row.get("exact") is False), None)
    first_miss = (
        {
            "sequence_index": first_miss_row["sequence_index"],
            "task_id": first_miss_row["task_id"],
            "tier": first_miss_row["tier"],
            "label": f"Task {first_miss_row['sequence_index']} · {first_miss_row['task_id']}",
        }
        if first_miss_row
        else {"sequence_index": None, "task_id": None, "tier": None, "label": "not observed"}
    )
    scored_tiers = [row for row in tier_rows if row["scored_count"]]
    if not scored_tiers:
        instability = {"tier": None, "label": "not measurable"}
    else:
        onset = next((row for row in scored_tiers if row["tier"] > frontier), None)
        if onset is None:
            instability = {"tier": None, "label": "not observed"}
        else:
            count_label = f"{onset['exact_count']}/{onset['scored_count']} exact"
            prefix = "No reliable tier · " if frontier == 0 else ""
            instability = {
                "tier": onset["tier"],
                "label": f"{prefix}Tier {onset['tier']} · {count_label}",
                "exact_count": onset["exact_count"],
                "scored_count": onset["scored_count"],
            }
    sustained = {"tier": None, "label": "not established"}
    for first, second in zip(scored_tiers, scored_tiers[1:]):
        combined = first["scored_count"] + second["scored_count"]
        if (
            second["tier"] == first["tier"] + 1
            and first["exact_rate"] + 1e-12 < 2 / 3
            and second["exact_rate"] + 1e-12 < 2 / 3
            and combined >= 8
        ):
            sustained = {
                "tier": first["tier"],
                "label": f"Tier {first['tier']} · {combined} scored across two tiers",
                "combined_scored_count": combined,
            }
            break
    return {
        "first_miss": first_miss,
        "reliable_frontier": {
            "tier": frontier,
            "label": f"Tier {frontier}" if frontier else "No reliable tier",
        },
        "instability_onset": instability,
        "sustained_breakdown": sustained,
        "peak_isolated_success": {
            "tier": peak,
            "label": f"Tier {peak}" if peak else "not observed",
        },
    }


def derive_progression_view(run: Mapping[str, Any]) -> dict[str, Any]:
    task_rows: list[dict[str, Any]] = []
    for sequence_index, record in enumerate(run.get("tasks", ()), start=1):
        attempts = list(record.get("attempts", ()))
        first = next((item for item in attempts if item.get("phase") == "first"), None)
        if first is None:
            continue
        kind = str(record.get("kind", ""))
        retries = [
            {**derive_attempt_outcome(kind, item), "phase": "retry"}
            for item in attempts
            if item.get("phase") == "retry"
        ]
        task_rows.append(
            {
                "sequence_index": sequence_index,
                "task_id": record.get("task_id"),
                "tier": record.get("tier"),
                "kind": kind,
                **derive_attempt_outcome(kind, first),
                "retries": retries,
            }
        )
    tier_rows = derive_tier_rows(task_rows)
    family_rows = _derive_task_family_rows(task_rows)
    typical_tier_size = infer_typical_tier_size(task_rows)
    rolling_window_size = max(8, 2 * typical_tier_size)
    summary = run.get("summary", {})
    scored_rows = [row for row in task_rows if row.get("exact") is not None]
    unsupported_count = sum(
        any(code in UNSUPPORTED_OUTPUT_CODES for code in row["codes"])
        for row in scored_rows
    )
    unsupported_output_proxy = {
        "label": "unsupported-output proxy",
        "count": unsupported_count,
        "scored_count": len(scored_rows),
        "rate": unsupported_count / len(scored_rows) if scored_rows else None,
    }
    latencies = [float(row["latency_ms"]) for row in scored_rows if row.get("latency_ms") is not None]
    usage = summary.get("usage_first") or {}
    retry_recovery_rate = summary.get("retry_recovery_rate")
    scorecards = {
        "first_attempt_latency_ms": {
            "median": statistics.median(latencies) if latencies else None,
        },
        "retry_recovery": {
            "rate": retry_recovery_rate,
            "label": "measured" if retry_recovery_rate is not None else "not measured",
        },
        "usage": {
            "reasoning_tokens": usage.get("reasoning_tokens"),
            "total_tokens": usage.get("total_tokens"),
        },
    }
    condition = {
        "run_id": run.get("run_id"),
        "suite_hash": run.get("suite_hash"),
        "suite_seed": run.get("suite_seed"),
        "benchmark_version": run.get("benchmark_version"),
        "taxonomy": run.get("taxonomy"),
        "resolved_models": summary.get("resolved_models", []),
        **dict(run.get("configuration", {})),
    }
    markers = derive_markers(task_rows, tier_rows, summary)
    retry_branches = [
        {
            "sequence_index": row["sequence_index"],
            "task_id": row["task_id"],
            "attempts": row["retries"],
        }
        for row in task_rows
        if row["retries"]
    ]
    return {
        "condition": condition,
        "tasks": task_rows,
        "tiers": tier_rows,
        "markers": markers,
        "rolling_window_size": rolling_window_size,
        "rolling": derive_rolling_points(task_rows, rolling_window_size),
        "task_families": family_rows,
        "unsupported_output_proxy": unsupported_output_proxy,
        "risk_proxy": unsupported_output_proxy,
        "scorecards": scorecards,
        "retry_branches": retry_branches,
        "routing_input": {
            "reliable_frontier": markers["reliable_frontier"],
            "task_families": family_rows,
            "median_latency_ms": scorecards["first_attempt_latency_ms"]["median"],
            "retry_recovery_rate": retry_recovery_rate,
            "unsupported_output_proxy": unsupported_output_proxy,
        },
    }

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from taxonomy_bench_progression import derive_attempt_outcome, wilson_interval


def attempt(
    *,
    exact=False,
    partial=0.0,
    details=None,
    feedback="Incorrect.",
    strict=True,
    recovered=False,
    error=None,
    usage=None,
):
    return {
        "phase": "first",
        "latency_ms": 120.0,
        "usage": {} if usage is None else usage,
        "error": error,
        "score": None
        if error
        else {
            "exact": exact,
            "partial": partial,
            "strict_json": strict,
            "recovered_json": recovered,
            "feedback": feedback,
            "details": {} if details is None else details,
        },
    }


def test_wilson_interval_handles_empty_and_known_samples():
    assert wilson_interval(0, 0) == (None, None)
    assert wilson_interval(8, 10) == pytest.approx((0.4902, 0.9433), abs=0.0001)


def test_format_and_infrastructure_codes_take_precedence():
    unparseable = derive_attempt_outcome(
        "direct_prerequisites",
        attempt(
            strict=False,
            feedback="The response was not parseable as the required JSON object.",
        ),
    )
    wrong_shape = derive_attempt_outcome(
        "direct_prerequisites",
        attempt(feedback="The 'ids' field must be an array of strings."),
    )
    infrastructure = derive_attempt_outcome(
        "direct_prerequisites",
        attempt(error="TimeoutError: timed out"),
    )

    assert unparseable["codes"] == ["format.unparseable"]
    assert wrong_shape["codes"] == ["format.wrong_shape"]
    assert infrastructure["codes"] == ["infrastructure"]


@pytest.mark.parametrize(
    ("kind", "details", "expected"),
    [
        ("semantic_match", {"actual_type": "str"}, ["selection.incorrect"]),
        (
            "direct_prerequisites",
            {"missing_count": 1, "extra_count": 1, "duplicate_count": 1},
            ["set.missing", "set.extra", "sequence.duplicate"],
        ),
        (
            "reverse_unlocks",
            {"missing_count": 1, "extra_count": 0, "duplicate_count": 0},
            ["set.missing"],
        ),
        (
            "transitive_prerequisites",
            {"missing_count": 0, "extra_count": 1, "duplicate_count": 0},
            ["set.extra"],
        ),
        (
            "topological_order",
            {"node_f1": 0.8, "violated_edges": 1, "duplicate_count": 1},
            ["order.node_coverage", "order.precedence", "sequence.duplicate"],
        ),
        (
            "shortest_path",
            {
                "endpoints_ok": False,
                "step_compliance": 0.5,
                "length_ok": False,
                "unique": False,
            },
            [
                "path.endpoint",
                "path.invalid_edge",
                "path.non_shortest",
                "sequence.duplicate",
            ],
        ),
        (
            "mastery_plan",
            {
                "set_f1": 0.8,
                "edge_compliance": 0.5,
                "target_last": False,
                "duplicate_count": 1,
            },
            [
                "plan.coverage",
                "plan.dependency",
                "plan.target_not_last",
                "sequence.duplicate",
            ],
        ),
        (
            "integrity_audit",
            {"missing_count": 1, "extra_count": 1, "duplicate_count": 1},
            ["integrity.miss", "integrity.false_positive", "sequence.duplicate"],
        ),
    ],
)
def test_kind_specific_diagnostic_codes(kind, details, expected):
    outcome = derive_attempt_outcome(kind, attempt(partial=0.5, details=details))

    assert outcome["codes"] == expected


def test_semantic_match_wrong_shape_suppresses_selection_code():
    outcome = derive_attempt_outcome(
        "semantic_match",
        attempt(details={"actual_type": "list"}),
    )

    assert outcome["codes"] == ["format.wrong_shape"]


@pytest.mark.parametrize(
    ("kind", "field"),
    [
        ("direct_prerequisites", "ids"),
        ("integrity_audit", "issues"),
        ("topological_order", "ids"),
        ("shortest_path", "ids"),
        ("mastery_plan", "ids"),
    ],
)
def test_list_output_wrong_shape_is_detected_for_every_scorer_family(kind, field):
    outcome = derive_attempt_outcome(
        kind,
        attempt(feedback=f"The '{field}' field must be an array of strings."),
    )

    assert outcome["codes"] == ["format.wrong_shape"]


def test_unparseable_precedes_wrong_shape_feedback():
    outcome = derive_attempt_outcome(
        "topological_order",
        attempt(
            strict=False,
            feedback="The 'ids' field must be an array of strings.",
        ),
    )

    assert outcome["codes"] == ["format.unparseable"]


def test_exact_and_unscored_outcomes_have_factual_metadata():
    exact = derive_attempt_outcome(
        "semantic_match",
        attempt(exact=True, partial=1.0, feedback="Correct.", usage={"total_tokens": 0}),
    )
    missing_score_attempt = attempt()
    missing_score_attempt["score"] = None
    unscored = derive_attempt_outcome("semantic_match", missing_score_attempt)

    assert exact == {
        "exact": True,
        "partial": 1.0,
        "outcome": "exact",
        "label": "Exact",
        "codes": [],
        "failure_summary": None,
        "latency_ms": 120.0,
        "tokens": 0,
    }
    assert unscored == {
        "exact": None,
        "partial": None,
        "outcome": "unscored",
        "label": "Unscored",
        "codes": ["infrastructure"],
        "failure_summary": "Score unavailable.",
        "latency_ms": 120.0,
        "tokens": None,
    }


def test_non_exact_outcome_preserves_feedback_and_missing_token_measurement():
    outcome = derive_attempt_outcome(
        "semantic_match",
        attempt(details={"actual_type": "str"}, feedback="The selected topic ID is incorrect."),
    )

    assert outcome["exact"] is False
    assert outcome["partial"] == 0.0
    assert outcome["outcome"] == "non-exact"
    assert outcome["label"] == "Non-exact"
    assert outcome["failure_summary"] == "The selected topic ID is incorrect."
    assert outcome["tokens"] is None

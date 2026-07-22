from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import taxonomy_bench_progression as progression
import taxonomy_bench as tb
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
    phase="first",
):
    return {
        "phase": phase,
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


def make_run(tier_outcomes, infra_indexes=()):
    tasks = []
    index = 0
    for tier, outcomes in tier_outcomes.items():
        for exact in outcomes:
            first = attempt(exact=exact, partial=1.0 if exact else 0.5)
            if index in infra_indexes:
                first = attempt(error="TimeoutError: timed out")
            tasks.append(
                {
                    "task_id": f"task-{index + 1}",
                    "tier": tier,
                    "kind": "semantic_match",
                    "attempts": [first],
                }
            )
            index += 1

    scored_by_tier = {}
    for task in tasks:
        first = next(item for item in task["attempts"] if item["phase"] == "first")
        if first.get("score") is None:
            continue
        row = scored_by_tier.setdefault(task["tier"], [0, 0])
        row[0] += int(first["score"]["exact"])
        row[1] += 1
    frontier = 0
    for tier in sorted(scored_by_tier):
        exact_count, scored_count = scored_by_tier[tier]
        if exact_count / scored_count + 1e-12 < 2 / 3:
            break
        frontier = tier
    peak = max(
        (
            task["tier"]
            for task in tasks
            for first in task["attempts"]
            if first["phase"] == "first"
            and first.get("score")
            and first["score"]["exact"]
        ),
        default=0,
    )
    return {
        "run_id": "run-1",
        "suite_hash": "suite-a",
        "suite_seed": 42,
        "benchmark_version": "test",
        "taxonomy": {"version": "fixture"},
        "configuration": {
            "provider": "fixture",
            "model": "model-a",
            "effort": "test",
            "output_mode": "prompt",
            "session_mode": "isolated",
            "retries": 0,
            "retry_policy": "feedback",
            "retry_context": "fresh",
            "transport_retries": 0,
            "tool_access": False,
            "condition_label": "fixture",
        },
        "tasks": tasks,
        "summary": {
            "reliable_frontier_first": frontier,
            "peak_tier_first": peak,
            "retry_recovery_rate": None,
            "usage_first": {},
        },
    }


def make_repeat_run(
    run_id,
    outcomes=(True,),
    *,
    repeat=1,
    suite_hash="suite-a",
    suite_seed=42,
    **configuration,
):
    run = make_run({1: list(outcomes)})
    run["run_id"] = run_id
    run["suite_hash"] = suite_hash
    run["suite_seed"] = suite_seed
    run["configuration"].update(configuration)
    run["configuration"]["repeat"] = repeat
    return run


def test_progression_preserves_order_and_selects_first_phase_explicitly():
    run = make_run({1: [True, True]})
    run["tasks"][0]["attempts"] = [
        attempt(exact=True, partial=1.0, phase="retry"),
        attempt(exact=False, partial=0.25, phase="first"),
    ]

    view = progression.derive_progression_view(run)

    assert [row["task_id"] for row in view["tasks"]] == ["task-1", "task-2"]
    assert [row["sequence_index"] for row in view["tasks"]] == [1, 2]
    assert view["tasks"][0]["outcome"] == "non-exact"
    assert view["tasks"][0]["retries"][0]["outcome"] == "exact"


def test_progression_infers_tier_size_and_leaves_infrastructure_gap():
    run = make_run({1: [True] * 4, 2: [True, False, True, False]}, infra_indexes={4})

    view = progression.derive_progression_view(run)

    assert view["rolling_window_size"] == 8
    assert view["tiers"][0]["median_latency_ms"] == 120.0
    assert view["rolling"][4]["exact_rate"] is None
    assert view["rolling"][3]["sample_count"] == 4
    assert view["tasks"][4]["outcome"] == "unscored"
    assert view["tiers"][0]["limited_evidence"] is False


def test_two_scored_task_tier_is_labeled_limited_evidence():
    view = progression.derive_progression_view(make_run({1: [True, False]}))

    assert view["tiers"][0]["limited_evidence"] is True
    assert view["tiers"][0]["evidence_note"] == "limited evidence · 2 scored"


def test_frontier_zero_has_explicit_instability_meaning():
    view = progression.derive_progression_view(make_run({1: [True, False, False, False]}))

    assert view["markers"]["instability_onset"]["label"] == (
        "No reliable tier · Tier 1 · 1/4 exact"
    )


def test_fully_reliable_run_has_no_observed_instability():
    view = progression.derive_progression_view(make_run({1: [True] * 4, 2: [True] * 4}))

    assert view["markers"]["instability_onset"]["label"] == "not observed"


def test_run_without_scored_tasks_has_unmeasurable_instability():
    view = progression.derive_progression_view(make_run({1: [True, True]}, infra_indexes={0, 1}))

    assert view["markers"]["instability_onset"]["label"] == "not measurable"


def test_two_adjacent_subthreshold_tiers_establish_sustained_breakdown():
    run = make_run(
        {
            1: [True] * 4,
            2: [True, False, False, False],
            3: [True, False, False, False],
        }
    )

    marker = progression.derive_progression_view(run)["markers"]["sustained_breakdown"]

    assert marker["tier"] == 2
    assert marker["combined_scored_count"] == 8


def test_single_subthreshold_tier_does_not_establish_sustained_breakdown():
    run = make_run({1: [True] * 4, 2: [True, False, False, False]})

    marker = progression.derive_progression_view(run)["markers"]["sustained_breakdown"]

    assert marker["label"] == "not established"


def test_first_miss_and_peak_success_are_separate_frontier_markers():
    run = make_run({1: [True, False], 2: [False], 3: [True]}, infra_indexes={0})

    markers = progression.derive_progression_view(run)["markers"]

    assert markers["first_miss"]["task_id"] == "task-2"
    assert markers["first_miss"]["sequence_index"] == 2
    assert markers["reliable_frontier"]["tier"] == 0
    assert markers["peak_isolated_success"]["tier"] == 3


def test_progression_composes_grounded_aggregates_and_missing_measurements():
    run = make_run({1: [False]})
    run["tasks"][0]["kind"] = "direct_prerequisites"
    run["tasks"][0]["attempts"] = [
        attempt(partial=0.5, details={"extra_count": 1})
    ]

    view = progression.derive_progression_view(run)

    assert view["condition"]["suite_hash"] == "suite-a"
    assert view["task_families"][0]["kind"] == "direct_prerequisites"
    assert view["unsupported_output_proxy"] == {
        "label": "unsupported-output proxy",
        "count": 1,
        "scored_count": 1,
        "rate": 1.0,
    }
    assert view["risk_proxy"] == view["unsupported_output_proxy"]
    assert view["scorecards"]["usage"]["total_tokens"] is None
    assert view["scorecards"]["retry_recovery"] == {
        "rate": None,
        "label": "not measured",
    }
    assert view["routing_input"]["unsupported_output_proxy"]["rate"] == 1.0


def test_retry_attempts_do_not_contaminate_first_pass_metrics_or_markers():
    run = make_run({1: [True, False, True, False]})
    baseline = progression.derive_progression_view(run)
    run["tasks"][1]["attempts"].append(
        attempt(exact=True, partial=1.0, phase="retry")
    )

    retried = progression.derive_progression_view(run)

    first_pass_fields = ("outcome", "exact", "partial", "latency_ms", "tokens")
    assert [
        {field: row[field] for field in first_pass_fields}
        for row in retried["tasks"]
    ] == [
        {field: row[field] for field in first_pass_fields}
        for row in baseline["tasks"]
    ]
    assert retried["rolling"] == baseline["rolling"]
    assert [
        {key: tier[key] for key in tier if key != "tasks"}
        for tier in retried["tiers"]
    ] == [
        {key: tier[key] for key in tier if key != "tasks"}
        for tier in baseline["tiers"]
    ]
    assert retried["markers"] == baseline["markers"]
    assert retried["tasks"][1]["retries"][0]["outcome"] == "exact"


def test_condition_grouping_uses_exact_configuration_key_without_repeat():
    assert progression.CONDITION_CONFIG_KEYS == (
        "provider",
        "model",
        "effort",
        "output_mode",
        "session_mode",
        "retries",
        "retry_policy",
        "retry_context",
        "transport_retries",
        "tool_access",
        "condition_label",
    )
    first = make_repeat_run("run-1", repeat=1)
    second = make_repeat_run("run-2", repeat=99)

    assert progression.condition_key(first) == (
        "suite-a",
        *(first["configuration"][key] for key in progression.CONDITION_CONFIG_KEYS),
    )
    assert progression.condition_key(first) == progression.condition_key(second)


def test_condition_evidence_separates_session_modes_and_labels_repeat_strength():
    runs = [
        make_repeat_run(f"isolated-{repeat}", repeat=repeat)
        for repeat in range(1, 4)
    ]
    runs.append(make_repeat_run("continuous-1", session_mode="continuous"))

    conditions = progression.derive_condition_evidence(runs)

    assert len(conditions) == 2
    isolated = next(
        item for item in conditions if item["configuration"]["session_mode"] == "isolated"
    )
    assert isolated["repeat_count"] == 3
    assert isolated["evidence_level"] == "repeated model evidence"
    assert isolated["run_ids"] == ["isolated-1", "isolated-2", "isolated-3"]


def test_condition_evidence_does_not_align_different_suites_or_output_modes():
    runs = [
        make_repeat_run("prompt-a"),
        make_repeat_run("schema-a", output_mode="schema"),
        make_repeat_run("prompt-b", suite_hash="suite-b", suite_seed=43),
    ]

    conditions = progression.derive_condition_evidence(runs)

    assert len(conditions) == 3
    assert all(condition["repeat_count"] == 1 for condition in conditions)


def test_same_task_repeat_evidence_precomputes_consistency_and_confidence():
    runs = [
        make_repeat_run("run-1", (True,), repeat=1),
        make_repeat_run("run-2", (True,), repeat=2),
        make_repeat_run("run-3", (False,), repeat=3),
    ]

    condition = progression.derive_condition_evidence(runs)[0]
    task = condition["tasks"][0]

    assert {
        key: task[key]
        for key in (
            "task_id",
            "tier",
            "kind",
            "exact_count",
            "observed_count",
            "exact_rate",
            "median_partial",
            "flip_rate",
        )
    } == {
        "task_id": "task-1",
        "tier": 1,
        "kind": "semantic_match",
        "exact_count": 2,
        "observed_count": 3,
        "exact_rate": pytest.approx(2 / 3),
        "median_partial": pytest.approx(1.0),
        "flip_rate": pytest.approx(1 / 3),
    }
    assert condition["consistency"]["flip_rate"] == pytest.approx(1 / 3)
    assert condition["exact_rate_confidence"]["sample_count"] == 3
    assert condition["exact_rate_confidence"]["wilson_95"] == pytest.approx(
        progression.wilson_interval(2, 3)
    )
    assert [item["run_id"] for item in task["observations"]] == [
        "run-1",
        "run-2",
        "run-3",
    ]
    assert [item["run_id"] for item in condition["run_traces"]] == condition["run_ids"]


def test_unscored_repeat_observations_do_not_enter_confidence_or_flip_rates():
    runs = [
        make_repeat_run("run-1", (True,), repeat=1),
        make_repeat_run("run-2", (False,), repeat=2),
        make_repeat_run("run-infra", (True,), repeat=3),
    ]
    runs[-1]["tasks"][0]["attempts"] = [attempt(error="network unavailable")]

    condition = progression.derive_condition_evidence(runs)[0]

    assert condition["tasks"][0]["observed_count"] == 2
    assert condition["exact_rate_confidence"]["sample_count"] == 2
    assert condition["consistency"]["flip_rate"] == pytest.approx(0.5)


@pytest.mark.parametrize(
    ("repeat_count", "expected"),
    [
        (1, "session evidence"),
        (2, "limited repeat evidence"),
        (3, "repeated model evidence"),
    ],
)
def test_condition_evidence_levels_are_exact(repeat_count, expected):
    runs = [make_repeat_run(f"run-{index}", repeat=index) for index in range(1, repeat_count + 1)]

    assert progression.derive_condition_evidence(runs)[0]["evidence_level"] == expected


def test_routing_evidence_is_precomputed_descriptive_and_source_grounded():
    runs = [
        make_repeat_run(f"run-{repeat}", (True, False), repeat=repeat)
        for repeat in range(1, 4)
    ]
    for index, run in enumerate(runs):
        run["tasks"][0]["kind"] = "reverse_unlocks"
        run["tasks"][1]["kind"] = "integrity_audit"
        run["tasks"][1]["attempts"] = [
            attempt(partial=0.25, details={"extra_count": 1})
        ]
        run["tasks"][0]["attempts"][0]["resolved_model"] = (
            "resolved-a" if index < 2 else "resolved-b"
        )

    condition = progression.derive_condition_evidence(runs)[0]

    assert next(
        row for row in condition["task_families"] if row["kind"] == "reverse_unlocks"
    )["proxy_label"] == "reverse-dependency impact analysis"
    assert condition["resolved_models"] == ["resolved-a", "resolved-b"]
    assert condition["resolved_model_changed"] is True
    assert condition["frontier_distribution"]["sample_count"] == 3
    assert condition["first_pass_latency_ms"]["sample_count"] == 6
    assert condition["unsupported_output_proxy"]["label"] == "unsupported-output proxy"

    routing = condition["routing_interpretation"]
    assert routing["heuristic"] is True
    assert "independent verification beyond" in routing["recommendation"]
    assert {reference["metric"] for reference in routing["evidence_references"]} == {
        "reliable_frontier",
        "strongest_capability_proxy",
        "weakest_capability_proxy",
        "median_first_pass_latency_ms",
        "repeat_consistency",
        "unsupported_output_proxy",
    }
    serialized = json.dumps(condition).lower()
    assert "hallucination" not in serialized
    assert "winner" not in serialized


def test_matrix_preserves_run_rows_adds_conditions_and_keeps_missing_usage_null():
    missing = make_repeat_run("missing-usage")
    explicit_zero = make_repeat_run("zero-usage", session_mode="continuous")
    explicit_zero["summary"]["usage_first"] = {
        "reasoning_tokens": 0,
        "total_tokens": 0,
    }

    matrix = tb.aggregate_matrix([missing, explicit_zero])

    assert [row["run_id"] for row in matrix["runs"]] == ["missing-usage", "zero-usage"]
    assert matrix["runs"][0]["reasoning_tokens"] is None
    assert matrix["runs"][0]["total_tokens"] is None
    assert matrix["runs"][1]["reasoning_tokens"] == 0
    assert matrix["runs"][1]["total_tokens"] == 0
    assert len(matrix["conditions"]) == 2


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

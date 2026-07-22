from __future__ import annotations

import copy
import re
import sys
from html import escape
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import taxonomy_bench as tb
import taxonomy_bench_report as report
from taxonomy_bench_progression import derive_progression_view


ATTRIBUTION = "Fixture attribution · https://example.invalid/source"


def _attempt(
    *,
    exact: bool = False,
    partial: float = 0.0,
    phase: str = "first",
    attempt_number: int = 1,
    strict: bool = True,
    recovered: bool = False,
    feedback: str = "Incorrect.",
    details: dict | None = None,
    text: str = '{"id":"answer"}',
    latency_ms: float = 125.0,
    usage: dict | None = None,
    error: str | None = None,
) -> dict:
    return {
        "attempt": attempt_number,
        "phase": phase,
        "text": text,
        "latency_ms": latency_ms,
        "usage": usage,
        "resolved_model": "resolved-model",
        "status": "completed" if error is None else "failed",
        "incomplete_reason": None,
        "error": error,
        "score": None
        if error
        else {
            "exact": exact,
            "partial": partial,
            "strict_json": strict,
            "recovered_json": recovered,
            "feedback": feedback,
            "details": details or {},
        },
    }


def make_run(*, with_retry: bool = True) -> dict:
    private_scorer = {
        "type": "shortest_path",
        "expected": "PRIVATE_EXPECTED_ANSWER",
        "required": ["PRIVATE_REQUIRED_NODE"],
        "edges": [["PRIVATE_EDGE_SOURCE", "PRIVATE_EDGE_TARGET"]],
        "minimum_edges": 99,
        "source": "PRIVATE_SOURCE_CONSTRAINT",
        "target": "PRIVATE_TARGET_CONSTRAINT",
    }
    tasks = [
        {
            "task_id": "reverse-1",
            "tier": 1,
            "kind": "reverse_unlocks",
            "attempts": [
                _attempt(
                    exact=True,
                    partial=1.0,
                    feedback="Exact.",
                    usage={"input_tokens": 9, "output_tokens": 3, "total_tokens": 12},
                )
            ],
        },
        {
            "task_id": "topology-<script>alert(1)</script>",
            "tier": 1,
            "kind": "shortest_path",
            "scorer": private_scorer,
            "attempts": [
                _attempt(
                    partial=0.72,
                    feedback="The minimum edge count is 99 for PRIVATE_EXPECTED_ANSWER.",
                    details={
                        "endpoints_ok": True,
                        "step_compliance": 1.0,
                        "length_ok": False,
                        "unique": True,
                        "nodes": ["PRIVATE_REQUIRED_NODE"],
                        "edges": [["PRIVATE_EDGE_SOURCE", "PRIVATE_EDGE_TARGET"]],
                    },
                    text='<svg onload="alert(1)"></svg>',
                    usage=None,
                )
            ],
        },
        {
            "task_id": "unparseable-3",
            "tier": 2,
            "kind": "semantic_match",
            "attempts": [
                _attempt(
                    partial=0.0,
                    strict=False,
                    recovered=False,
                    feedback="Required JSON object not found. <img src=x onerror=alert(1)>",
                    details={"actual_type": "none"},
                    text="not json",
                    usage={"total_tokens": 4},
                )
            ],
        },
        {
            "task_id": "infra-4",
            "tier": 2,
            "kind": "integrity_audit",
            "attempts": [
                _attempt(
                    error="network <b>offline</b>",
                    text="",
                    usage=None,
                )
            ],
        },
    ]
    if with_retry:
        tasks[1]["attempts"].append(
            _attempt(
                exact=True,
                partial=1.0,
                phase="retry",
                attempt_number=2,
                feedback="Exact.",
                text='{"ids":["fixed"]}',
                usage={"total_tokens": 7},
            )
        )

    return {
        "format_version": 1,
        "benchmark_version": "0.1.0",
        "run_id": "fixture-<run>",
        "created_at": "2026-07-21T12:00:00+00:00",
        "suite_hash": "suite-fixture",
        "suite_seed": 42,
        "taxonomy": {"version": "fixture-taxonomy"},
        "configuration": {
            "provider": "fixture",
            "model": "model-<operator>",
            "effort": "medium",
            "output_mode": "prompt",
            "session_mode": "isolated",
            "retries": 1 if with_retry else 0,
            "retry_policy": "feedback",
            "retry_context": "continued",
            "transport_retries": 0,
            "tool_access": False,
            "condition_label": "fixture-condition",
            "repeat": 1,
        },
        "tasks": tasks,
        "summary": {
            "reliable_frontier_first": 1,
            "peak_tier_first": 1,
            "retry_recovery_rate": 1.0 if with_retry else None,
            "usage_first": {},
            "resolved_models": ["resolved-model"],
        },
    }


class _DocumentAudit(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags: list[tuple[str, dict[str, str | None]]] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        self.tags.append((tag, dict(attrs)))


def test_run_report_renders_progression_trace_and_recovery_semantics():
    rendered = report.render_run_html(make_run(), ATTRIBUTION)

    for expected in (
        "Benchmark Progression",
        "Reliable frontier",
        "Instability onset",
        "Sustained breakdown",
        "1.00 exact",
        'data-kind="reverse_unlocks"',
        "Recovery phase",
        "routing heuristic",
    ):
        assert expected in rendered
    assert "PASS</" not in rendered
    assert "FAIL</" not in rendered


def test_recovery_evidence_is_one_compact_collapsed_disclosure_per_retry():
    run = make_run()
    template = run["tasks"][1]
    run["tasks"] = []
    for sequence in range(1, 33):
        task = copy.deepcopy(template)
        task["task_id"] = f"retry-task-{sequence:02d}"
        task["tier"] = 1 + (sequence - 1) // 4
        run["tasks"].append(task)

    rendered = report.render_run_html(run, ATTRIBUTION)
    branches = list(
        re.finditer(
            r'<details class="recovery-branch" data-phase="retry"([^>]*)>\s*'
            r'<summary>([^<]+)</summary>',
            rendered,
        )
    )
    task_positions = [
        match.start()
        for match in re.finditer(r'<article class="task-entry" id="task-\d+"', rendered)
    ]

    assert len(branches) == 32
    assert all(not match.group(1).strip() for match in branches)
    assert all(
        match.group(2) == "Recovery phase · attempt 2 · 1.00 exact"
        for match in branches
    )
    assert '<section class="recovery-branch"' not in rendered
    assert "<summary>Recovery evidence</summary>" not in rendered
    assert all(
        task_positions[index] < branches[index].start() < task_positions[index + 1]
        for index in range(31)
    )
    assert "row.querySelectorAll('.recovery-branch')" in rendered
    assert re.search(
        r'<div class="task-row">.*?'
        r'<details class="task-details"><summary>Attempt evidence</summary>.*?'
        r'</details></div><details class="recovery-branch"',
        rendered,
        flags=re.DOTALL,
    )
    trace_height = int(
        re.search(r"\.trace-scroll\s*\{[^}]*max-height:\s*(\d+)px", rendered).group(1)
    )
    assert 690 <= trace_height <= 720
    assert re.search(
        r"\.recovery-branch\s*>\s*summary\s*\{[^}]*font-size:\s*(?:1[5-9]|[2-9]\d)px",
        rendered,
    )


def test_frontier_strip_renders_only_derived_marker_labels_definitions_and_evidence():
    view = derive_progression_view(make_run())
    marker_labels = {
        "first_miss": "First miss",
        "reliable_frontier": "Reliable frontier",
        "instability_onset": "Instability onset",
        "sustained_breakdown": "Sustained breakdown",
        "peak_isolated_success": "Peak isolated success",
    }
    for key in marker_labels:
        view["markers"][key]["definition"] = f"derived definition {key}"
        view["markers"][key]["evidence_label"] = f"derived evidence {key}"

    rendered = report._render_frontier_strip(view)

    assert rendered.count('<details class="marker-detail">') == 5
    for key, label in marker_labels.items():
        marker = view["markers"][key]
        assert f"<dt>{label}</dt><dd>{escape(marker['label'])}</dd>" in rendered
        assert escape(marker["definition"]) in rendered
        assert escape(marker["evidence_label"]) in rendered
    assert rendered.count("<summary>Definition and evidence</summary>") == 5


def test_run_condition_identity_reports_repeat_index_or_missing_value():
    run = make_run()
    run["configuration"]["repeat"] = 7
    reported = report.render_run_html(run, ATTRIBUTION)
    run["configuration"].pop("repeat")
    missing = report.render_run_html(run, ATTRIBUTION)

    assert "<dt>Repeat</dt><dd>7</dd>" in reported
    assert "<dt>Repeat</dt><dd>not reported</dd>" in missing
    assert "session evidence" in reported


def test_run_report_has_accessible_offline_document_structure():
    rendered = report.render_run_html(make_run(), ATTRIBUTION)
    audit = _DocumentAudit()
    audit.feed(rendered)

    assert rendered.startswith("<!doctype html>")
    assert '<html lang="en">' in rendered
    assert "<title>Benchmark Progression · fixture-&lt;run&gt;</title>" in rendered
    assert len(re.findall(r"<h1(?:\s|>)", rendered)) == 1
    assert any(tag == "button" for tag, _ in audit.tags)
    assert any(tag == "select" for tag, _ in audit.tags)
    minimap_links = [
        attrs
        for tag, attrs in audit.tags
        if tag == "a" and "minimap-link" in (attrs.get("class") or "")
    ]
    assert minimap_links
    assert all((attrs.get("href") or "").startswith("#") for attrs in minimap_links)
    assert ":focus-visible" in rendered
    assert "@media (prefers-reduced-motion: reduce)" in rendered
    assert re.search(r"body\s*\{[^}]*font-size:\s*(?:1[5-9]|[2-9]\d)px", rendered)
    assert all(int(size) >= 13 for size in re.findall(r"font-size:\s*(\d+)px", rendered))

    lowered = rendered.lower()
    assert not re.search(r"<script\b[^>]*\bsrc\s*=", lowered)
    assert not re.search(r"<link\b[^>]*\brel=[\"']?stylesheet", lowered)
    assert "url(" not in lowered
    assert all(term not in lowered for term in ("fetch(", "xmlhttprequest", "websocket"))
    assert 'href="https://example.invalid/source"' not in rendered


def test_run_report_escapes_run_text_and_omits_private_constraint_data():
    rendered = report.render_run_html(make_run(), ATTRIBUTION)

    assert "<script>alert(1)</script>" not in rendered
    assert "<img src=x" not in rendered
    assert '<svg onload="alert(1)">' not in rendered
    assert "topology-&lt;script&gt;alert(1)&lt;/script&gt;" in rendered
    assert "model-&lt;operator&gt;" in rendered
    for private_text in (
        "PRIVATE_EXPECTED_ANSWER",
        "PRIVATE_REQUIRED_NODE",
        "PRIVATE_EDGE_SOURCE",
        "PRIVATE_EDGE_TARGET",
        "minimum_edges",
        "PRIVATE_SOURCE_CONSTRAINT",
        "PRIVATE_TARGET_CONSTRAINT",
        "minimum edge count is 99",
    ):
        assert private_text not in rendered


def test_run_report_labels_missing_measurements_and_all_outcome_classes_textually():
    rendered = report.render_run_html(make_run(with_retry=False), ATTRIBUTION)
    lowered = rendered.lower()

    assert "not reported" in lowered
    assert "not measured" in lowered
    assert "1.00 exact" in lowered
    assert "0.72 non-exact" in lowered
    assert "unparseable" in lowered
    assert "unscored · infrastructure error" in lowered


def test_non_exact_filter_includes_only_rows_with_non_exact_outcome_data():
    rendered = report.render_run_html(make_run(with_retry=False), ATTRIBUTION)
    audit = _DocumentAudit()
    audit.feed(rendered)
    row_outcomes = [
        attrs.get("data-outcome")
        for tag, attrs in audit.tags
        if tag == "article" and "task-entry" in (attrs.get("class") or "")
    ]

    assert row_outcomes == ["exact", "non-exact", "non-exact", "unscored"]
    assert "mode === 'non-exact' && row.dataset.outcome === 'non-exact'" in rendered
    assert "row.dataset.outcome !== 'exact'" not in rendered


def test_run_report_exposes_safe_details_and_rolling_svg_metadata():
    rendered = report.render_run_html(make_run(), ATTRIBUTION)

    assert "Model response" in rendered
    assert "Scorer feedback" in rendered
    assert "Scorer details" in rendered
    assert "Retry policy" in rendered
    assert "Retry context" in rendered
    assert "Infrastructure error" in rendered
    assert "Full usage" in rendered
    assert "Rolling exact and partial progression" in rendered
    assert "sample count" in rendered
    assert "window size 8" in rendered
    assert '<svg aria-labelledby="rolling-title rolling-desc"' in rendered
    assert 'role="status" aria-live="polite"' in rendered


def test_minimap_has_one_ordered_native_task_anchor_per_task_for_dense_runs():
    run = make_run(with_retry=False)
    template = run["tasks"][0]
    run["tasks"] = []
    for sequence in range(1, 37):
        task = copy.deepcopy(template)
        task["task_id"] = f"dense-task-{sequence:02d}"
        task["tier"] = 1 + (sequence - 1) // 4
        run["tasks"].append(task)
    rendered = report.render_run_html(run, ATTRIBUTION)
    audit = _DocumentAudit()
    audit.feed(rendered)
    task_marks = [
        attrs
        for tag, attrs in audit.tags
        if tag == "a" and "task-mark" in (attrs.get("class") or "")
    ]

    assert len(task_marks) == 36
    assert [attrs.get("href") for attrs in task_marks] == [
        f"#task-{sequence}" for sequence in range(1, 37)
    ]
    assert [attrs.get("aria-label") for attrs in task_marks] == [
        f"Task {sequence} · dense-task-{sequence:02d} · exact"
        for sequence in range(1, 37)
    ]
    assert all(f">{sequence}</a>" in rendered for sequence in range(1, 37))
    assert re.search(r"\.task-mark-rail\s*\{[^}]*flex-wrap:\s*wrap", rendered)
    assert re.search(r"\.task-mark-rail\s*\{[^}]*overflow-y:\s*auto", rendered)
    assert re.search(r"\.task-mark\s*\{[^}]*font-size:\s*13px", rendered)


def test_save_run_emits_the_progression_report(tmp_path: Path):
    tb.save_run(make_run(), tmp_path)

    rendered = (tmp_path / "report.html").read_text(encoding="utf-8")
    assert "Benchmark Progression" in rendered


def make_matrix() -> dict:
    isolated_runs = []
    for repeat in range(1, 4):
        run = make_run()
        run["run_id"] = f"z-isolated-{repeat}"
        run["configuration"]["model"] = "z-model"
        run["configuration"]["effort"] = "low"
        run["configuration"]["repeat"] = repeat
        isolated_runs.append(run)
    isolated_runs[-1]["tasks"][0]["attempts"][0]["score"].update(
        exact=False,
        partial=0.25,
        feedback="One downstream dependency was missed.",
        details={"missing_count": 1},
    )
    isolated_runs[-1]["tasks"][0]["attempts"][0]["resolved_model"] = "resolved-model-v2"

    continuous = make_run(with_retry=False)
    continuous["run_id"] = "z-continuous-1"
    continuous["configuration"].update(
        model="z-model",
        effort="low",
        session_mode="continuous",
        repeat=1,
    )

    alpha_low = make_run(with_retry=False)
    alpha_low["run_id"] = "a-low-1"
    alpha_low["configuration"].update(model="a-model", effort="low", repeat=1)
    alpha_high = make_run(with_retry=False)
    alpha_high["run_id"] = "a-high-1"
    alpha_high["configuration"].update(model="a-model", effort="high", repeat=1)

    matrix = tb.aggregate_matrix([*isolated_runs, continuous, alpha_low, alpha_high])
    matrix["conditions"] = list(reversed(matrix["conditions"]))
    for index, condition in enumerate(matrix["conditions"]):
        condition["composite_score"] = 10_000 - index
    return matrix


def test_matrix_report_renders_repeat_evidence_without_ranking_language():
    matrix = make_matrix()
    rendered = report.render_matrix_html(matrix, ATTRIBUTION)
    lowered = rendered.lower()

    for expected in (
        "repeated model evidence",
        "95% Wilson interval",
        "outcome flip rate",
        "unsupported-output proxy",
        "success by task family",
    ):
        assert expected in rendered
    assert "winner" not in lowered
    assert "composite" not in lowered


def test_matrix_report_links_every_trace_and_separates_session_conditions():
    matrix = make_matrix()
    rendered = report.render_matrix_html(matrix, ATTRIBUTION)

    for run in matrix["runs"]:
        assert f'href="./{run["run_id"]}/report.html"' in rendered
    assert '<article class="condition-card" data-session="isolated"' in rendered
    assert '<article class="condition-card" data-session="continuous"' in rendered
    assert "not reported" in rendered


def test_matrix_report_sorts_conditions_by_requested_model_then_effort():
    rendered = report.render_matrix_html(make_matrix(), ATTRIBUTION)

    alpha_high = rendered.index("a-model · high")
    alpha_low = rendered.index("a-model · low")
    z_model = rendered.index("z-model · low")
    assert alpha_high < alpha_low < z_model


def test_matrix_report_warns_when_resolved_model_changes():
    rendered = report.render_matrix_html(make_matrix(), ATTRIBUTION)

    assert 'role="alert"' in rendered
    assert "Resolved model changed" in rendered
    assert "resolved-model-v2" in rendered


def test_matrix_report_supports_exact_legacy_v1_runs_only_shape():
    legacy = {
        "format_version": 1,
        "benchmark_version": "0.1.0",
        "runs": [
            {
                "run_id": "legacy-run",
                "model": "legacy-model",
                "effort": "low",
                "base_strength": 50.0,
                "frontier_first": 3,
                "median_latency_ms": 250.0,
            }
        ],
    }

    rendered = report.render_matrix_html(legacy, ATTRIBUTION)
    lowered = rendered.lower()

    assert "Legacy matrix · repeat evidence unavailable" in rendered
    assert "legacy-model" in rendered
    assert 'href="./legacy-run/report.html"' in rendered
    assert all(
        forbidden not in lowered
        for forbidden in ("confidence", "consistency", "task family", "routing")
    )


def test_core_matrix_wrapper_uses_repeat_evidence_renderer():
    rendered = tb.render_matrix_html(make_matrix())

    assert "95% Wilson interval" in rendered
    assert "winner" not in rendered.lower()


def test_safe_run_report_href_accepts_only_one_allowlisted_path_segment():
    valid = ("run-1", "Run_2.0", "20260722T103000Z-model-effort")
    invalid = (
        None,
        "",
        ".",
        "..",
        "javascript:alert(1)",
        "//host",
        "../escape",
        "slash/name",
        "slash\\name",
        "run?query",
        "run#fragment",
        "%2e%2e",
        "has space",
        "line\nfeed",
        '<b onclick="alert(1)">markup</b>',
        "café",
    )

    assert [report._safe_run_report_href(value) for value in valid] == [
        f"./{value}/report.html" for value in valid
    ]
    assert all(report._safe_run_report_href(value) is None for value in invalid)


def test_invalid_run_ids_are_escaped_text_without_links_in_all_matrix_locations():
    invalid_ids = [
        "javascript:alert(1)",
        "//host",
        "../escape",
        "slash/name",
        "slash\\name",
        "run?query",
        "run#fragment",
        "%2e%2e",
        '<b onclick="alert(1)">markup</b>',
    ]
    valid_id = "valid-run_1.0"
    matrix = make_matrix()
    matrix["conditions"] = [matrix["conditions"][0]]
    matrix["conditions"][0]["run_traces"] = [
        {"run_id": run_id} for run_id in [*invalid_ids, valid_id]
    ]
    matrix["runs"] = [
        {"run_id": run_id, "model": "fixture", "effort": "low"}
        for run_id in [*invalid_ids, valid_id]
    ]
    modern = report.render_matrix_html(matrix, ATTRIBUTION)
    legacy = report.render_matrix_html(
        {"format_version": 1, "runs": matrix["runs"]},
        ATTRIBUTION,
    )

    assert modern.count(f'href="./{valid_id}/report.html"') == 2
    assert legacy.count(f'href="./{valid_id}/report.html"') == 1
    for run_id in invalid_ids:
        escaped = escape(run_id, quote=True)
        assert modern.count(escaped) >= 2
        assert escaped in legacy
        assert f'href="{escaped}' not in modern
        assert f'href="{escaped}' not in legacy
    for rendered in (modern, legacy):
        assert "javascript:" not in " ".join(
            match.group(1) for match in re.finditer(r'href="([^"]*)"', rendered)
        )

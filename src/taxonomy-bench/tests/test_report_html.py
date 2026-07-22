from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import taxonomy_bench as tb
import taxonomy_bench_report as report


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


def test_save_run_emits_the_progression_report(tmp_path: Path):
    tb.save_run(make_run(), tmp_path)

    rendered = (tmp_path / "report.html").read_text(encoding="utf-8")
    assert "Benchmark Progression" in rendered

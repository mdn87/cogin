from __future__ import annotations

import html
import json
from typing import Any, Mapping

from taxonomy_bench_progression import derive_condition_evidence, derive_progression_view


def _esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _fmt_number(value: Any, digits: int = 2, missing: str = "not reported") -> str:
    if value is None:
        return missing
    return f"{float(value):.{digits}f}"


def _fmt_percent(value: Any, missing: str = "not measured") -> str:
    if value is None:
        return missing
    return f"{100 * float(value):.1f}%"


def _fmt_latency(value: Any) -> str:
    return "not reported" if value is None else f"{float(value):.0f} ms"


def _fmt_tokens(value: Any) -> str:
    return "not reported" if value is None else f"{int(value):,}"


def _json_text(value: Any) -> str:
    if value is None:
        return "not reported"
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)


def _render_condition_header(
    view: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> str:
    condition = view["condition"]
    resolved = condition.get("resolved_models") or evidence.get("resolved_models") or []
    resolved_label = ", ".join(str(item) for item in resolved) or "not reported"
    retry_label = (
        f"{condition.get('retries', 0)} · {condition.get('retry_policy') or 'not reported'}"
        f" / {condition.get('retry_context') or 'not reported'}"
    )
    identity = (
        ("Requested model", condition.get("model")),
        ("Resolved model", resolved_label),
        ("Effort", condition.get("effort")),
        ("Session / output", f"{condition.get('session_mode') or 'not reported'} / {condition.get('output_mode') or 'not reported'}"),
        ("Retry", retry_label),
        ("Suite / seed", f"{condition.get('suite_hash') or 'not reported'} / {condition.get('suite_seed') if condition.get('suite_seed') is not None else 'not reported'}"),
        ("Benchmark", condition.get("benchmark_version")),
        ("Taxonomy", (condition.get("taxonomy") or {}).get("version") if isinstance(condition.get("taxonomy"), Mapping) else condition.get("taxonomy")),
    )
    identity_html = "".join(
        f"<div><dt>{_esc(label)}</dt><dd>{_esc(value if value is not None else 'not reported')}</dd></div>"
        for label, value in identity
    )
    routing = evidence.get("routing_interpretation") or {}
    return (
        '<header class="condition-header">'
        '<p class="eyebrow">Taxonomy Bench · operator evidence</p>'
        '<h1>Benchmark Progression</h1>'
        f'<p class="run-id">{_esc(condition.get("run_id") or "unidentified run")}</p>'
        f'<dl class="identity">{identity_html}</dl>'
        '<section class="routing" aria-labelledby="routing-heading">'
        '<h2 id="routing-heading">Routing recommendation</h2>'
        f'<p>{_esc(routing.get("recommendation") or "Routing evidence is not measured.")}</p>'
        f'<p class="support"><strong>routing heuristic</strong> · {_esc(evidence.get("evidence_level") or "session evidence")}</p>'
        '</section>'
        '</header>'
    )


def _render_frontier_strip(view: Mapping[str, Any]) -> str:
    markers = view["markers"]
    scorecards = view["scorecards"]
    recovery = scorecards["retry_recovery"]
    proxy = view["unsupported_output_proxy"]
    values = (
        ("Reliable frontier", markers["reliable_frontier"].get("label")),
        ("Instability onset", markers["instability_onset"].get("label")),
        ("Sustained breakdown", markers["sustained_breakdown"].get("label")),
        ("Peak isolated success", markers["peak_isolated_success"].get("label")),
        ("Median first-attempt latency", _fmt_latency(scorecards["first_attempt_latency_ms"].get("median"))),
        ("Retry recovery", _fmt_percent(recovery.get("rate"), recovery.get("label") or "not measured")),
        ("Unsupported-output proxy", f"{proxy.get('count', 0)}/{proxy.get('scored_count', 0)} · {_fmt_percent(proxy.get('rate'))}"),
    )
    items = "".join(
        f"<div><dt>{_esc(label)}</dt><dd>{_esc(value)}</dd></div>" for label, value in values
    )
    return f'<section class="frontier-strip" aria-label="Progression markers"><dl>{items}</dl></section>'


def _svg_paths(points: list[Mapping[str, Any]], key: str) -> list[str]:
    if not points:
        return []
    denominator = max(1, len(points) - 1)
    segments: list[list[str]] = []
    active: list[str] = []
    for index, point in enumerate(points):
        value = point.get(key)
        if value is None:
            if active:
                segments.append(active)
                active = []
            continue
        x = 16 + (568 * index / denominator)
        y = 18 + 124 * (1 - float(value))
        active.append(f"{x:.1f},{y:.1f}")
    if active:
        segments.append(active)
    return [" ".join(segment) for segment in segments]


def _render_progression_svg(view: Mapping[str, Any]) -> str:
    points = list(view.get("rolling") or [])
    exact_paths = "".join(
        f'<polyline class="series exact-series" points="{_esc(path)}" />'
        for path in _svg_paths(points, "exact_rate")
    )
    partial_paths = "".join(
        f'<polyline class="series partial-series" points="{_esc(path)}" />'
        for path in _svg_paths(points, "partial_mean")
    )
    denominator = max(1, len(points) - 1)
    point_metadata = "".join(
        (
            f'<circle class="sample-point" cx="{16 + (568 * index / denominator):.1f}" '
            f'cy="{18 + 124 * (1 - float(point["partial_mean"])):.1f}" r="3">'
            f'<title>Task {_esc(point.get("sequence_index"))}: sample count {_esc(point.get("sample_count"))} '
            f'/ window size {_esc(point.get("window_size"))}</title></circle>'
        )
        for index, point in enumerate(points)
        if point.get("partial_mean") is not None
    )
    latest = next((point for point in reversed(points) if point.get("partial_mean") is not None), None)
    latest_sample = latest.get("sample_count") if latest else 0
    latest_window = latest.get("window_size") if latest else view.get("rolling_window_size")
    return (
        '<figure class="rolling-chart">'
        '<figcaption><strong>Rolling exact and partial progression</strong>'
        f'<span>Latest sample count {_esc(latest_sample)} / window size {_esc(latest_window)}</span></figcaption>'
        '<svg aria-labelledby="rolling-title rolling-desc" role="img" viewBox="0 0 600 160" preserveAspectRatio="none">'
        '<title id="rolling-title">Rolling exact and partial progression</title>'
        '<desc id="rolling-desc">Trailing exact rate and mean partial score. Gaps denote unscored infrastructure attempts.</desc>'
        '<line class="chart-rule" x1="16" y1="18" x2="584" y2="18" />'
        '<line class="chart-rule" x1="16" y1="80" x2="584" y2="80" />'
        '<line class="chart-rule" x1="16" y1="142" x2="584" y2="142" />'
        f'{exact_paths}{partial_paths}{point_metadata}'
        '</svg>'
        '<p class="chart-legend"><span>Solid rail · exact rate</span><span>Dashed rail · mean partial</span></p>'
        '</figure>'
    )


def _outcome_text(task: Mapping[str, Any]) -> str:
    codes = set(task.get("codes") or [])
    if task.get("exact") is True:
        return f"{_fmt_number(task.get('partial'), 2)} exact"
    if task.get("exact") is None:
        return "unscored · infrastructure error"
    summary = task.get("failure_summary") or "No diagnostic summary reported."
    if "format.unparseable" in codes:
        return f"unparseable · {summary}"
    if "format.wrong_shape" in codes:
        return f"non-exact · unsupported output shape · {summary}"
    return f"{_fmt_number(task.get('partial'), 2)} non-exact · {summary}"


def _render_attempt_details(attempt: Mapping[str, Any], *, recovery: bool = False) -> str:
    detail_items = (
        ("Attempt / phase", f"{attempt.get('attempt_number') or 'not reported'} / {attempt.get('phase') or 'not reported'}"),
        ("Model response", attempt.get("response_text") if attempt.get("response_text") is not None else "not reported"),
        ("Scorer feedback", attempt.get("scorer_feedback") or "not reported"),
        ("Scorer details", _json_text(attempt.get("scorer_details") or {})),
        ("Latency", _fmt_latency(attempt.get("latency_ms"))),
        ("Full usage", _json_text(attempt.get("usage"))),
        ("Retry policy", attempt.get("retry_policy") if recovery else "not applicable"),
        ("Retry context", attempt.get("retry_context") if recovery else "not applicable"),
        ("Infrastructure error", attempt.get("error") or "none reported"),
    )
    return "".join(
        f"<div><dt>{_esc(label)}</dt><dd><pre>{_esc(value)}</pre></dd></div>"
        for label, value in detail_items
    )


def _render_task_row(task: Mapping[str, Any]) -> str:
    sequence = task.get("sequence_index")
    task_id = task.get("task_id")
    outcome = _outcome_text(task)
    retries = list(task.get("retries") or [])
    details = _render_attempt_details(task)
    recovery_html = "".join(
        (
            '<section class="recovery-branch" data-phase="retry">'
            f'<h4>Recovery phase · attempt {_esc(retry.get("attempt_number"))}</h4>'
            f'<p class="outcome-text">{_esc(_outcome_text(retry))}</p>'
            '<details><summary>Recovery evidence</summary>'
            f'<dl class="attempt-details">{_render_attempt_details(retry, recovery=True)}</dl>'
            '</details></section>'
        )
        for retry in retries
    )
    return (
        f'<article class="task-entry" id="task-{_esc(sequence)}" data-kind="{_esc(task.get("kind"))}" '
        f'data-outcome="{_esc(task.get("outcome"))}" data-has-retries="{str(bool(retries)).lower()}" tabindex="0">'
        '<div class="task-row">'
        f'<span class="sequence">{_esc(sequence)}</span>'
        f'<span class="task-identity"><strong>{_esc(task_id)}</strong><small>Tier {_esc(task.get("tier"))} · {_esc(task.get("kind"))}</small></span>'
        f'<span class="outcome-text">{_esc(outcome)}</span>'
        f'<span><small>Partial</small>{_esc(_fmt_number(task.get("partial"), 2))}</span>'
        f'<span><small>Latency</small>{_esc(_fmt_latency(task.get("latency_ms")))}</span>'
        f'<span><small>Tokens</small>{_esc(_fmt_tokens(task.get("tokens")))}</span>'
        '</div>'
        '<details class="task-details"><summary>Attempt evidence</summary>'
        f'<dl class="attempt-details">{details}</dl></details>'
        f'{recovery_html}'
        '</article>'
    )


def _render_tier_group(tier: Mapping[str, Any]) -> str:
    exact_rate = _fmt_percent(tier.get("exact_rate"), "not measured")
    partial = _fmt_number(tier.get("partial_mean"), 2, "not measured")
    heading = (
        f"{tier.get('scored_count')}/{tier.get('task_count')} scored · "
        f"{tier.get('exact_count')} exact ({exact_rate}) · partial mean {partial} · "
        f"median {_fmt_latency(tier.get('median_latency_ms'))} · {tier.get('evidence_note')}"
    )
    rows = "".join(_render_task_row(task) for task in tier.get("tasks", ()))
    return (
        f'<section class="tier-group" id="tier-{_esc(tier.get("tier"))}">'
        f'<header class="tier-header"><h3>Tier {_esc(tier.get("tier"))}</h3><p>{_esc(heading)}</p></header>'
        f'{rows}</section>'
    )


def _render_diagnostic_sidebar(view: Mapping[str, Any]) -> str:
    tasks = list(view.get("tasks") or [])
    selected = next((task for task in tasks if task.get("exact") is not True), tasks[0] if tasks else None)
    if selected is None:
        diagnostic = '<p class="support">No task evidence reported.</p>'
    else:
        diagnostic = (
            f'<p class="diagnostic-task">{_esc(selected.get("task_id"))}</p>'
            f'<p>{_esc(_outcome_text(selected))}</p>'
            f'<p class="support">Codes · {_esc(", ".join(selected.get("codes") or []) or "none")}</p>'
        )
    tier_links = "".join(
        f'<a class="minimap-link" href="#tier-{_esc(tier.get("tier"))}" aria-label="Jump to tier {_esc(tier.get("tier"))}">Tier {_esc(tier.get("tier"))}</a>'
        for tier in view.get("tiers", ())
    )
    marker_links = []
    for name, marker in view.get("markers", {}).items():
        if marker.get("sequence_index") is not None:
            target = f"task-{marker['sequence_index']}"
        elif marker.get("tier") is not None:
            target = f"tier-{marker['tier']}"
        else:
            target = "progression-top"
        marker_links.append(
            f'<a class="minimap-link anomaly" href="#{_esc(target)}" aria-label="Jump to {_esc(name.replace("_", " "))}">{_esc(name.replace("_", " "))}</a>'
        )
    return (
        '<aside class="diagnostic-sidebar" aria-labelledby="diagnostic-heading">'
        '<h2 id="diagnostic-heading">Diagnostic context</h2>'
        f'{diagnostic}'
        '<p class="support">Open a task row for its safe response, scorer evidence, usage, and recovery record.</p>'
        '<nav class="minimap" aria-label="Progression minimap">'
        f'{tier_links}{"".join(marker_links)}'
        '</nav></aside>'
    )


def _render_metadata(view: Mapping[str, Any], attribution: str) -> str:
    condition = view.get("condition") or {}
    return (
        '<section class="metadata" aria-labelledby="metadata-heading">'
        '<h2 id="metadata-heading">Run metadata</h2>'
        '<details><summary>Reproducibility configuration</summary>'
        f'<pre>{_esc(_json_text(condition))}</pre></details>'
        '</section>'
        f'<footer>{_esc(attribution)}</footer>'
    )


def _render_aggregate_scorecards(view: Mapping[str, Any]) -> str:
    scorecards = view["scorecards"]
    usage = scorecards["usage"]
    recovery = scorecards["retry_recovery"]
    values = (
        ("Median first-attempt latency", _fmt_latency(scorecards["first_attempt_latency_ms"].get("median"))),
        ("Retry recovery", _fmt_percent(recovery.get("rate"), recovery.get("label") or "not measured")),
        ("Reasoning tokens", _fmt_tokens(usage.get("reasoning_tokens"))),
        ("Total tokens", _fmt_tokens(usage.get("total_tokens"))),
    )
    score_html = "".join(
        f"<div><dt>{_esc(label)}</dt><dd>{_esc(value)}</dd></div>" for label, value in values
    )
    family_rows = "".join(
        (
            f'<tr><th scope="row">{_esc(family.get("kind"))}</th>'
            f'<td>{_esc(family.get("exact_count"))}/{_esc(family.get("scored_count"))}</td>'
            f'<td>{_esc(_fmt_percent(family.get("exact_rate")))}</td>'
            f'<td>{_esc(_fmt_number(family.get("partial_mean"), 2, "not measured"))}</td>'
            f'<td>{_esc(family.get("unsupported_output_count"))}</td></tr>'
        )
        for family in view.get("task_families", ())
    )
    return (
        '<section class="aggregate" aria-labelledby="aggregate-heading">'
        '<h2 id="aggregate-heading">Aggregate scorecards</h2>'
        f'<dl class="scorecard-rail">{score_html}</dl>'
        '<div class="table-wrap"><table><caption>Task-family evidence</caption>'
        '<thead><tr><th>Task family</th><th>Exact</th><th>Exact rate</th><th>Partial mean</th><th>Unsupported output</th></tr></thead>'
        f'<tbody>{family_rows}</tbody></table></div></section>'
    )


_RUN_CSS = """
:root { color-scheme: dark; font-family: ui-sans-serif, system-ui, sans-serif; background: #090d12; color: #e6edf3; }
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body { margin: 0; background: #090d12; color: #e6edf3; font-size: 15px; line-height: 1.4; }
button, select { font: inherit; color: inherit; }
button:focus-visible, select:focus-visible, a:focus-visible, summary:focus-visible, .task-entry:focus-visible { outline: 2px solid #f5c451; outline-offset: 3px; }
main { max-width: 1580px; margin: auto; padding: 22px 24px 48px; }
h1 { margin: 0; font-size: clamp(32px, 4vw, 54px); line-height: 1; letter-spacing: -.035em; }
h2 { margin: 0 0 10px; font-size: 20px; }
h3, h4, p { margin: 0; }
.eyebrow, .support, small, figcaption span, .chart-legend, footer { color: #9aa9b8; font-size: 13px; }
.eyebrow { letter-spacing: .1em; text-transform: uppercase; margin-bottom: 8px; }
.run-id { color: #b9c5d1; margin-top: 7px; }
.identity { display: flex; flex-wrap: wrap; gap: 0; margin: 18px 0 14px; border-block: 1px solid #26313d; }
.identity div { min-width: 180px; padding: 8px 18px 8px 0; margin-right: 18px; }
dt { color: #8fa0b1; font-size: 13px; }
dd { margin: 2px 0 0; }
.routing { max-width: 1060px; border-left: 3px solid #75a7c7; padding: 10px 14px; background: #0e151c; }
.routing .support { margin-top: 5px; }
.frontier-strip { margin: 18px 0; border-block: 1px solid #2b3947; background: #0d131a; }
.frontier-strip dl, .scorecard-rail { display: flex; overflow-x: auto; margin: 0; }
.frontier-strip dl > div, .scorecard-rail > div { min-width: 175px; padding: 10px 14px; border-right: 1px solid #26313d; }
.workspace-heading { display: flex; align-items: end; justify-content: space-between; gap: 16px; margin: 22px 0 8px; }
.filters { display: flex; flex-wrap: wrap; gap: 7px; align-items: center; }
.filters button, .filters select { border: 1px solid #3a4a59; background: #101820; border-radius: 3px; padding: 6px 9px; min-height: 34px; }
.filters button[aria-pressed="true"] { border-color: #f5c451; color: #fff2c8; }
.result-count { color: #aebbc7; font-size: 13px; min-width: 80px; text-align: right; }
.progression-layout { display: grid; grid-template-columns: minmax(0, 1fr) minmax(260px, 340px); gap: 14px; align-items: start; }
.trace-panel { min-width: 0; border: 1px solid #2a3744; background: #0c1218; }
.rolling-chart { margin: 0; padding: 9px 12px; border-bottom: 1px solid #2a3744; }
.rolling-chart figcaption { display: flex; justify-content: space-between; gap: 12px; }
.rolling-chart svg { display: block; width: 100%; height: 118px; margin-top: 4px; }
.chart-rule { stroke: #263442; stroke-width: 1; }
.series { fill: none; stroke: #75a7c7; stroke-width: 3; vector-effect: non-scaling-stroke; }
.partial-series { stroke: #f5c451; stroke-dasharray: 7 5; }
.sample-point { fill: #e6edf3; stroke: #090d12; }
.chart-legend { display: flex; gap: 18px; }
.trace-scroll { max-height: 590px; overflow: auto; scroll-behavior: smooth; }
.tier-header { position: sticky; top: 0; z-index: 2; display: flex; align-items: baseline; gap: 12px; padding: 7px 10px; background: #17212b; border-block: 1px solid #344454; }
.tier-header h3 { font-size: 16px; white-space: nowrap; }
.tier-header p { color: #b8c4cf; font-size: 13px; }
.task-entry { border-bottom: 1px solid #222e39; scroll-margin-top: 40px; }
.task-entry:focus, .task-entry:hover { background: #111b24; }
.task-entry[hidden] { display: none; }
.task-row { display: grid; grid-template-columns: 36px minmax(170px, 1.15fr) minmax(220px, 1.8fr) 75px 75px 85px; gap: 9px; align-items: center; min-height: 52px; padding: 6px 10px; }
.sequence { color: #7e91a4; font-variant-numeric: tabular-nums; }
.task-identity { min-width: 0; }
.task-identity strong { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.task-identity small, .task-row > span > small { display: block; }
.outcome-text { line-height: 1.25; }
.task-details { padding: 0 10px 8px 55px; }
summary { cursor: pointer; color: #b9c9d7; font-size: 13px; }
.attempt-details { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px 14px; margin: 8px 0; }
.attempt-details div { min-width: 0; }
pre { margin: 3px 0 0; padding: 8px; overflow: auto; white-space: pre-wrap; overflow-wrap: anywhere; background: #080d12; color: #dbe5ed; font: inherit; font-size: 13px; }
.recovery-branch { margin: 0 10px 8px 55px; padding: 8px 10px; border-left: 2px solid #f5c451; background: #131a20; }
.recovery-branch h4 { font-size: 15px; }
.diagnostic-sidebar { position: sticky; top: 12px; border: 1px solid #2a3744; background: #0e151c; padding: 14px; min-height: 310px; }
.diagnostic-task { font-weight: 700; overflow-wrap: anywhere; }
.diagnostic-sidebar > p + p { margin-top: 7px; }
.minimap { display: grid; grid-template-columns: repeat(2, 1fr); gap: 5px; margin-top: 16px; }
.minimap-link { color: #bdd1e2; border-left: 2px solid #47647b; padding: 5px 7px; font-size: 13px; text-decoration: none; }
.minimap-link.anomaly { border-left-color: #f5c451; }
.aggregate, .metadata { margin-top: 28px; }
.scorecard-rail { border-block: 1px solid #2a3744; }
.table-wrap { margin-top: 12px; overflow-x: auto; }
table { width: 100%; border-collapse: collapse; }
caption { text-align: left; font-weight: 700; margin-bottom: 6px; }
th, td { padding: 8px 10px; border-bottom: 1px solid #26313d; text-align: left; }
thead th { color: #9aa9b8; font-size: 13px; }
.metadata details { border-top: 1px solid #2a3744; padding-top: 8px; }
footer { margin-top: 24px; border-top: 1px solid #26313d; padding-top: 12px; }
@media (max-width: 900px) {
  main { padding-inline: 14px; }
  .progression-layout { grid-template-columns: 1fr; }
  .diagnostic-sidebar { position: static; }
  .task-row { grid-template-columns: 32px minmax(150px, 1fr) minmax(190px, 1.6fr) 70px 70px 80px; overflow-x: auto; }
}
@media (max-width: 768px) {
  .workspace-heading { align-items: stretch; flex-direction: column; }
  .result-count { text-align: left; }
  .trace-scroll { max-height: none; }
  .task-row { display: grid; grid-template-columns: 30px 1fr; }
  .task-row > span:nth-child(n+3) { grid-column: 2; }
  .attempt-details { grid-template-columns: 1fr; }
  .task-details, .recovery-branch { margin-left: 0; padding-left: 10px; }
}
@media (prefers-reduced-motion: reduce) {
  html, .trace-scroll { scroll-behavior: auto; }
}
"""


_RUN_JS = """
(() => {
  'use strict';
  const rows = Array.from(document.querySelectorAll('.task-entry'));
  const buttons = Array.from(document.querySelectorAll('[data-filter]'));
  const family = document.getElementById('family-filter');
  const count = document.getElementById('visible-count');
  let mode = 'all';

  const applyFilters = () => {
    let visible = 0;
    rows.forEach((row) => {
      const familyMatch = family.value === 'all' || row.dataset.kind === family.value;
      const modeMatch = mode === 'all'
        || (mode === 'non-exact' && row.dataset.outcome !== 'exact')
        || (mode === 'retries' && row.dataset.hasRetries === 'true');
      row.hidden = !(familyMatch && modeMatch);
      row.querySelectorAll('.recovery-branch').forEach((branch) => {
        branch.hidden = row.hidden;
      });
      if (!row.hidden) visible += 1;
    });
    count.textContent = `${visible} result${visible === 1 ? '' : 's'}`;
  };

  buttons.forEach((button) => button.addEventListener('click', () => {
    mode = button.dataset.filter;
    buttons.forEach((item) => item.setAttribute('aria-pressed', String(item === button)));
    applyFilters();
  }));
  family.addEventListener('change', applyFilters);
  applyFilters();
})();
"""


def render_run_html(run: Mapping[str, Any], attribution: str) -> str:
    view = derive_progression_view(run)
    evidence = derive_condition_evidence([run])[0]
    tiers = "".join(_render_tier_group(tier) for tier in view["tiers"])
    kinds = sorted({str(task.get("kind")) for task in view["tasks"]})
    family_options = "".join(
        f'<option value="{_esc(kind)}">{_esc(kind)}</option>' for kind in kinds
    )
    run_id = view["condition"].get("run_id") or "unidentified run"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Benchmark Progression · {_esc(run_id)}</title>
<style>{_RUN_CSS}</style>
</head>
<body>
<main>
{_render_condition_header(view, evidence)}
{_render_frontier_strip(view)}
<section class="progression" id="progression-top" aria-labelledby="progression-heading">
  <div class="workspace-heading">
    <div><h2 id="progression-heading">Benchmark Progression trace</h2><p class="support">First-pass sequence with later retries attached as recovery evidence.</p></div>
    <div class="filters" aria-label="Trace filters">
      <button type="button" data-filter="all" aria-pressed="true">All</button>
      <button type="button" data-filter="non-exact" aria-pressed="false">Non-exact</button>
      <button type="button" data-filter="retries" aria-pressed="false">Retries</button>
      <label for="family-filter" class="support">Task family</label>
      <select id="family-filter"><option value="all">All families</option>{family_options}</select>
      <div class="result-count" id="visible-count" role="status" aria-live="polite">{len(view['tasks'])} results</div>
    </div>
  </div>
  <div class="progression-layout">
    <div class="trace-panel">
      {_render_progression_svg(view)}
      <div class="trace-scroll">{tiers}</div>
    </div>
    {_render_diagnostic_sidebar(view)}
  </div>
</section>
{_render_aggregate_scorecards(view)}
{_render_metadata(view, attribution)}
</main>
<script>{_RUN_JS}</script>
</body>
</html>"""


def _render_repeat_task_table(condition: Mapping[str, Any]) -> str:
    rows = "".join(
        (
            f'<tr><th scope="row">{_esc(task.get("task_id"))}</th>'
            f'<td>{_esc(task.get("tier"))}</td>'
            f'<td>{_esc(task.get("kind"))}</td>'
            f'<td>{_esc(task.get("exact_count"))}/{_esc(task.get("observed_count"))}</td>'
            f'<td>{_esc(_fmt_number(task.get("median_partial"), 2, "not measured"))}</td>'
            f'<td>{_esc(_fmt_percent(task.get("flip_rate")))}</td></tr>'
        )
        for task in condition.get("tasks", ())
    )
    return (
        '<div class="matrix-table-wrap"><table class="repeat-task-table">'
        '<caption>Aligned task evidence</caption>'
        '<thead><tr><th>Task</th><th>Tier</th><th>Family</th><th>Exact sample</th><th>Median partial</th><th>Outcome flip rate</th></tr></thead>'
        f'<tbody>{rows}</tbody></table></div>'
    )


def _render_condition_card(condition: Mapping[str, Any]) -> str:
    configuration = condition.get("configuration") or {}
    requested_model = configuration.get("model") or "not reported"
    effort = configuration.get("effort") or "not reported"
    resolved_models = condition.get("resolved_models") or []
    resolved_label = ", ".join(str(model) for model in resolved_models) or "not reported"
    confidence = condition.get("exact_rate_confidence") or {}
    interval = confidence.get("wilson_95") or [None, None]
    lower = interval[0] if len(interval) > 0 else None
    upper = interval[1] if len(interval) > 1 else None
    frontier = condition.get("frontier_distribution") or {}
    consistency = condition.get("consistency") or {}
    flip_rate = consistency.get("flip_rate") if consistency.get("measured") else None
    unsupported = condition.get("unsupported_output_proxy") or {}
    routing = condition.get("routing_interpretation") or {}
    identity = (
        ("Requested model", requested_model),
        ("Resolved model", resolved_label),
        ("Effort", effort),
        ("Session / output", f"{configuration.get('session_mode') or 'not reported'} / {configuration.get('output_mode') or 'not reported'}"),
        ("Retry identity", f"{configuration.get('retries', 0)} · {configuration.get('retry_policy') or 'not reported'} / {configuration.get('retry_context') or 'not reported'}"),
        ("Evidence", f"{condition.get('evidence_level') or 'session evidence'} · {condition.get('repeat_count', 0)} repeat(s)"),
    )
    identity_html = "".join(
        f'<div><dt>{_esc(label)}</dt><dd>{_esc(value)}</dd></div>' for label, value in identity
    )
    warning = (
        '<p class="resolved-warning" role="alert"><strong>Resolved model changed</strong> · '
        f'{_esc(resolved_label)}</p>'
        if condition.get("resolved_model_changed")
        else ""
    )
    metrics = (
        (
            "Aggregate exact sample",
            f"{confidence.get('exact_count', 0)}/{confidence.get('sample_count', 0)} exact · {_fmt_percent(confidence.get('exact_rate'))}",
        ),
        (
            "95% Wilson interval",
            f"{_fmt_percent(lower)} – {_fmt_percent(upper)} · n={confidence.get('sample_count', 0)}",
        ),
        (
            "Reliable frontier min / median / max",
            f"{_fmt_number(frontier.get('minimum'), 0, 'not measured')} / {_fmt_number(frontier.get('median'), 1, 'not measured')} / {_fmt_number(frontier.get('maximum'), 0, 'not measured')}",
        ),
        ("Median first-pass latency", _fmt_latency((condition.get("first_pass_latency_ms") or {}).get("median"))),
        ("outcome flip rate", _fmt_percent(flip_rate)),
        (
            unsupported.get("label") or "unsupported-output proxy",
            f"{unsupported.get('count', 0)}/{unsupported.get('scored_count', 0)} · {_fmt_percent(unsupported.get('rate'))}",
        ),
    )
    metrics_html = "".join(
        f'<div><dt>{_esc(label)}</dt><dd>{_esc(value)}</dd></div>' for label, value in metrics
    )
    traces = "".join(
        f'<li><a href="{_esc(str(trace.get("run_id")) + "/report.html")}">{_esc(trace.get("run_id"))}</a></li>'
        for trace in condition.get("run_traces", ())
        if trace.get("run_id") is not None
    )
    family_rows = "".join(
        (
            f'<tr><th scope="row">{_esc(family.get("kind"))}</th>'
            f'<td>{_esc(family.get("proxy_label") or "not reported")}</td>'
            f'<td>{_esc(family.get("exact_count"))}/{_esc(family.get("sample_count"))}</td>'
            f'<td>{_esc(_fmt_percent(family.get("exact_rate")))}</td>'
            f'<td>{_esc(_fmt_number(family.get("median_partial"), 2, "not measured"))}</td></tr>'
        )
        for family in condition.get("task_families", ())
    )
    return (
        f'<article class="condition-card" data-session="{_esc(configuration.get("session_mode") or "not reported")}">'
        '<header class="condition-card-header">'
        f'<p class="matrix-eyebrow">Requested condition</p><h2>{_esc(requested_model)} · {_esc(effort)}</h2>'
        f'{warning}<dl class="condition-identity">{identity_html}</dl>'
        '</header>'
        f'<dl class="condition-metrics">{metrics_html}</dl>'
        '<section class="condition-routing" aria-label="Routing interpretation">'
        '<h3>Routing heuristic</h3>'
        f'<p>{_esc(routing.get("recommendation") or "Routing evidence is not measured.")}</p>'
        '</section>'
        '<section class="trace-links"><h3>Individual run traces</h3>'
        f'<ul>{traces}</ul></section>'
        '<section class="family-evidence"><h3>success by task family</h3>'
        '<div class="matrix-table-wrap"><table><thead><tr><th>Task family</th><th>Capability proxy</th><th>Exact sample</th><th>Exact rate</th><th>Median partial</th></tr></thead>'
        f'<tbody>{family_rows}</tbody></table></div></section>'
        f'{_render_repeat_task_table(condition)}'
        '</article>'
    )


def _render_legacy_matrix(runs: list[Mapping[str, Any]]) -> str:
    rows = "".join(
        (
            f'<tr><th scope="row"><a href="{_esc(str(run.get("run_id")) + "/report.html")}">{_esc(run.get("run_id"))}</a></th>'
            f'<td>{_esc(run.get("model") if run.get("model") is not None else "not reported")}</td>'
            f'<td>{_esc(run.get("effort") if run.get("effort") is not None else "not reported")}</td>'
            f'<td>{_esc(_fmt_number(run.get("base_strength"), 1))}</td>'
            f'<td>{_esc(run.get("frontier_first") if run.get("frontier_first") is not None else "not reported")}</td>'
            f'<td>{_esc(_fmt_latency(run.get("median_latency_ms")))}</td></tr>'
        )
        for run in runs
    )
    return (
        '<h1>Legacy matrix · repeat evidence unavailable</h1>'
        '<p class="matrix-lede">Historical run rows are shown as recorded.</p>'
        '<div class="matrix-table-wrap legacy-table"><table>'
        '<thead><tr><th>Run</th><th>Model</th><th>Effort</th><th>Base strength</th><th>Frontier</th><th>Median latency</th></tr></thead>'
        f'<tbody>{rows}</tbody></table></div>'
    )


_MATRIX_CSS = """
:root { color-scheme: dark; font-family: ui-sans-serif, system-ui, sans-serif; background: #090d12; color: #e6edf3; }
* { box-sizing: border-box; }
body { margin: 0; background: #090d12; color: #e6edf3; font-size: 15px; line-height: 1.45; }
a { color: #b9dbf3; }
a:focus-visible, summary:focus-visible { outline: 2px solid #f5c451; outline-offset: 3px; }
main { max-width: 1500px; margin: auto; padding: 26px 24px 52px; }
h1 { margin: 0; font-size: clamp(32px, 4vw, 52px); letter-spacing: -.035em; line-height: 1.05; }
h2 { margin: 0; font-size: 23px; }
h3 { margin: 18px 0 7px; font-size: 16px; }
p { margin: 0; }
.matrix-eyebrow, .matrix-lede, dt, footer { color: #98a8b7; font-size: 13px; }
.matrix-lede { margin-top: 8px; max-width: 860px; }
.matrix-conditions { display: grid; gap: 16px; margin-top: 22px; }
.condition-card { border: 1px solid #2c3946; background: #0d141b; }
.condition-card-header { padding: 15px 16px 0; }
.condition-identity, .condition-metrics { display: flex; flex-wrap: wrap; margin: 13px 0 0; border-block: 1px solid #293642; }
.condition-identity > div, .condition-metrics > div { min-width: 190px; flex: 1 1 190px; padding: 8px 14px 8px 0; margin-right: 14px; border-right: 1px solid #25313c; }
dd { margin: 2px 0 0; }
.resolved-warning { margin-top: 9px; border-left: 3px solid #f5c451; background: #211b10; padding: 8px 10px; }
.condition-metrics { margin-inline: 16px; }
.condition-routing, .trace-links, .family-evidence { margin-inline: 16px; }
.condition-routing { border-left: 3px solid #75a7c7; padding: 8px 11px; background: #101a23; }
.condition-routing h3 { margin-top: 0; }
.trace-links ul { display: flex; flex-wrap: wrap; gap: 7px 16px; margin: 0; padding-left: 20px; }
.matrix-table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; }
caption { color: #e6edf3; font-weight: 700; text-align: left; padding: 16px; }
th, td { padding: 8px 10px; border-bottom: 1px solid #26323d; text-align: left; white-space: nowrap; }
thead th { color: #98a8b7; font-size: 13px; }
.family-evidence .matrix-table-wrap { border-top: 1px solid #26323d; }
.repeat-task-table { margin-top: 10px; }
.run-index { margin-top: 26px; }
.run-index h2 { margin-bottom: 8px; }
.legacy-table { margin-top: 20px; border: 1px solid #2c3946; }
footer { margin-top: 26px; padding-top: 12px; border-top: 1px solid #26323d; }
@media (max-width: 768px) {
  main { padding-inline: 14px; }
  .condition-identity, .condition-metrics { display: grid; grid-template-columns: 1fr; }
  .condition-identity > div, .condition-metrics > div { border-right: 0; }
}
@media (prefers-reduced-motion: reduce) {
  * { scroll-behavior: auto; }
}
"""


_LEGACY_MATRIX_CSS = """
:root { color-scheme: dark; font-family: ui-sans-serif, system-ui, sans-serif; background: #090d12; color: #e6edf3; }
* { box-sizing: border-box; }
body { margin: 0; background: #090d12; color: #e6edf3; font-size: 15px; line-height: 1.45; }
main { max-width: 1200px; margin: auto; padding: 26px 24px 52px; }
h1 { margin: 0; font-size: clamp(32px, 4vw, 52px); letter-spacing: -.035em; }
.matrix-lede, footer { color: #98a8b7; font-size: 13px; }
.matrix-lede { margin-top: 8px; }
.matrix-table-wrap { overflow-x: auto; }
.legacy-table { margin-top: 20px; border: 1px solid #2c3946; }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 8px 10px; border-bottom: 1px solid #26323d; text-align: left; white-space: nowrap; }
thead th { color: #98a8b7; font-size: 13px; }
a { color: #b9dbf3; }
a:focus-visible { outline: 2px solid #f5c451; outline-offset: 3px; }
footer { margin-top: 26px; padding-top: 12px; border-top: 1px solid #26323d; }
@media (max-width: 768px) { main { padding-inline: 14px; } }
@media (prefers-reduced-motion: reduce) { * { scroll-behavior: auto; } }
"""


def render_matrix_html(matrix: Mapping[str, Any], attribution: str) -> str:
    runs = list(matrix.get("runs") or [])
    if "conditions" not in matrix:
        legacy_content = _render_legacy_matrix(runs)
        return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Legacy Taxonomy Bench matrix</title><style>{_LEGACY_MATRIX_CSS}</style></head>
<body><main>{legacy_content}<footer>{_esc(attribution)}</footer></main></body></html>"""

    conditions = sorted(
        matrix.get("conditions") or [],
        key=lambda condition: (
            str((condition.get("configuration") or {}).get("model") or ""),
            str((condition.get("configuration") or {}).get("effort") or ""),
        ),
    )
    cards = "".join(_render_condition_card(condition) for condition in conditions)
    run_rows = "".join(
        (
            f'<tr><th scope="row"><a href="{_esc(str(run.get("run_id")) + "/report.html")}">{_esc(run.get("run_id"))}</a></th>'
            f'<td>{_esc(run.get("model") if run.get("model") is not None else "not reported")}</td>'
            f'<td>{_esc(run.get("effort") if run.get("effort") is not None else "not reported")}</td>'
            f'<td>{_esc(_fmt_tokens(run.get("reasoning_tokens")))}</td>'
            f'<td>{_esc(_fmt_tokens(run.get("total_tokens")))}</td>'
            f'<td>{_esc(_fmt_latency(run.get("median_latency_ms")))}</td></tr>'
        )
        for run in runs
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Taxonomy Bench · repeat evidence matrix</title>
<style>{_MATRIX_CSS}</style>
</head>
<body><main>
<header><p class="matrix-eyebrow">Taxonomy Bench · operator evidence</p><h1>Repeat evidence matrix</h1>
<p class="matrix-lede">Condition scorecards preserve uncertainty, consistency, task-family behavior, and links to each benchmark progression trace.</p></header>
<section class="matrix-conditions" aria-label="Benchmark conditions">{cards}</section>
<section class="run-index" aria-labelledby="run-index-heading"><h2 id="run-index-heading">Individual run index</h2>
<div class="matrix-table-wrap"><table><thead><tr><th>Run trace</th><th>Requested model</th><th>Effort</th><th>Reasoning tokens</th><th>Total tokens</th><th>Median latency</th></tr></thead>
<tbody>{run_rows}</tbody></table></div></section>
<footer>{_esc(attribution)}</footer>
</main></body>
</html>"""

# Cogin HUD Benchmark Progression Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Taxonomy Bench's summary-heavy HTML reports with an evidence-first benchmark progression trace and repeat-aware routing scorecards grounded entirely in existing run records.

**Architecture:** Add a pure `taxonomy_bench_progression.py` module for task outcomes, diagnostic codes, progression markers, repeat evidence, and routing interpretations. Add a separate `taxonomy_bench_report.py` module that turns those view models into standalone HTML; keep `taxonomy_bench.py` responsible for benchmark execution, artifact orchestration, and backward-compatible public entry points.

**Tech Stack:** Python 3.10+, Python standard library, pytest, standalone HTML/CSS/vanilla JavaScript

---

## Source of truth

- Approved design: `docs/superpowers/specs/2026-07-21-hud-benchmark-progression-design.md`
- Existing benchmark semantics: `src/taxonomy-bench/BENCHMARK_SPEC.md`
- Existing implementation: `src/taxonomy-bench/taxonomy_bench.py`

## File structure

- Create `src/taxonomy-bench/taxonomy_bench_progression.py`: presentation-neutral derivation, statistics, diagnostic-code mapping, repeated-condition evidence, and routing interpretation.
- Create `src/taxonomy-bench/taxonomy_bench_report.py`: standalone run and matrix HTML renderers, embedded CSS/JavaScript, filters, details, minimap, and charts.
- Create `src/taxonomy-bench/tests/test_progression.py`: focused unit tests for the pure derivation layer.
- Create `src/taxonomy-bench/tests/test_report_html.py`: report structure, accessibility, privacy, and integration tests.
- Create `src/taxonomy-bench/scripts/package-release.ps1`: deterministic checksum and tracked-archive builder using an explicit release manifest.
- Modify `src/taxonomy-bench/taxonomy_bench.py`: import the new seams, preserve existing public function names, enrich matrix artifacts, and remove the old inline renderers.
- Modify `src/taxonomy-bench/pyproject.toml`: package both new modules and bump the feature version.
- Modify `src/taxonomy-bench/README.md`: document progression reports, repeat evidence, and interpretation boundaries.
- Modify `src/taxonomy-bench/VALIDATION.md`: record the new automated and visual checks.
- Regenerate `src/taxonomy-bench/SHA256SUMS` and `src/taxonomy-bench.zip` after validation.

No runtime dependency or frontend framework is added.

## Command convention

Run every command in this plan from the Cogin repository root: `C:\Users\Matt\Desktop\MyDocs\cogin`. Python/test/build commands therefore use paths rooted at `src/taxonomy-bench`, and the shown `git add` paths remain valid without changing directories.

### Task 1: Extract the shared statistics and reporting seams

**Files:**
- Create: `src/taxonomy-bench/taxonomy_bench_progression.py`
- Create: `src/taxonomy-bench/tests/test_progression.py`
- Modify: `src/taxonomy-bench/taxonomy_bench.py:1-40,1589-1606,1721`
- Modify: `src/taxonomy-bench/pyproject.toml:22-24`

- [ ] **Step 1: Write the failing Wilson-interval compatibility test**

```python
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from taxonomy_bench_progression import wilson_interval


def test_wilson_interval_handles_empty_and_known_samples():
    assert wilson_interval(0, 0) == (None, None)
    lower, upper = wilson_interval(8, 10)
    assert lower == pytest.approx(0.4902, abs=0.0001)
    assert upper == pytest.approx(0.9433, abs=0.0001)
```

- [ ] **Step 2: Run the test and verify the new module is missing**

Run: `python -m pytest src/taxonomy-bench/tests/test_progression.py::test_wilson_interval_handles_empty_and_known_samples -q`

Expected: FAIL during collection with `ModuleNotFoundError: taxonomy_bench_progression`.

- [ ] **Step 3: Create the module and move the existing formula without changing it**

```python
from __future__ import annotations

import math
from typing import Any, Mapping, Sequence


def wilson_interval(
    successes: int,
    total: int,
    z: float = 1.96,
) -> tuple[float | None, float | None]:
    if total <= 0:
        return None, None
    proportion = successes / total
    denominator = 1 + z * z / total
    center = (proportion + z * z / (2 * total)) / denominator
    margin = (
        z
        * math.sqrt(
            proportion * (1 - proportion) / total
            + z * z / (4 * total * total)
        )
        / denominator
    )
    return max(0.0, center - margin), min(1.0, center + margin)
```

Import `wilson_interval` in `taxonomy_bench.py`, remove `_wilson_interval`, and replace its one call in `summarize_run`.

- [ ] **Step 4: Package the new modules**

Change:

```toml
[tool.setuptools]
py-modules = [
    "taxonomy_bench",
    "taxonomy_bench_progression",
    "taxonomy_bench_report",
]
```

Create an empty importable `taxonomy_bench_report.py` for now; its renderer is added in Task 5.

- [ ] **Step 5: Run focused and full regression tests**

Run: `python -m pytest src/taxonomy-bench/tests/test_progression.py src/taxonomy-bench/tests/test_taxonomy_bench.py -q`

Expected: all existing tests and the new interval test PASS.

- [ ] **Step 6: Commit the extraction**

```bash
git add src/taxonomy-bench/taxonomy_bench.py src/taxonomy-bench/taxonomy_bench_progression.py src/taxonomy-bench/taxonomy_bench_report.py src/taxonomy-bench/tests/test_progression.py src/taxonomy-bench/pyproject.toml
git commit -m "refactor: extract benchmark reporting seams"
```

### Task 2: Derive factual task outcomes and diagnostic codes

**Files:**
- Modify: `src/taxonomy-bench/taxonomy_bench_progression.py`
- Modify: `src/taxonomy-bench/tests/test_progression.py`

- [ ] **Step 1: Add a compact attempt factory and failing precedence tests**

```python
def attempt(*, exact=False, partial=0.0, details=None, feedback="Incorrect.", strict=True, recovered=False, error=None, usage=None):
    return {
        "phase": "first",
        "latency_ms": 120.0,
        "usage": {} if usage is None else usage,
        "error": error,
        "score": None if error else {
            "exact": exact,
            "partial": partial,
            "strict_json": strict,
            "recovered_json": recovered,
            "feedback": feedback,
            "details": {} if details is None else details,
        },
    }


def test_format_and_infrastructure_codes_take_precedence():
    unparseable = derive_attempt_outcome(
        "direct_prerequisites",
        attempt(strict=False, feedback="The response was not parseable as the required JSON object."),
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
```

- [ ] **Step 2: Add a parametrized test covering all eight task kinds**

The cases must assert these exact mappings:

```python
@pytest.mark.parametrize(
    ("kind", "details", "expected"),
    [
        ("semantic_match", {"actual_type": "str"}, {"selection.incorrect"}),
        ("direct_prerequisites", {"missing_count": 1, "extra_count": 1, "duplicate_count": 1}, {"set.missing", "set.extra", "sequence.duplicate"}),
        ("reverse_unlocks", {"missing_count": 1, "extra_count": 0, "duplicate_count": 0}, {"set.missing"}),
        ("transitive_prerequisites", {"missing_count": 0, "extra_count": 1, "duplicate_count": 0}, {"set.extra"}),
        ("topological_order", {"node_f1": 0.8, "violated_edges": 1, "duplicate_count": 1}, {"order.node_coverage", "order.precedence", "sequence.duplicate"}),
        ("shortest_path", {"endpoints_ok": False, "step_compliance": 0.5, "length_ok": False, "unique": False}, {"path.endpoint", "path.invalid_edge", "path.non_shortest", "sequence.duplicate"}),
        ("mastery_plan", {"set_f1": 0.8, "edge_compliance": 0.5, "target_last": False, "duplicate_count": 1}, {"plan.coverage", "plan.dependency", "plan.target_not_last", "sequence.duplicate"}),
        ("integrity_audit", {"missing_count": 1, "extra_count": 1, "duplicate_count": 1}, {"integrity.miss", "integrity.false_positive", "sequence.duplicate"}),
    ],
)
def test_kind_specific_diagnostic_codes(kind, details, expected):
    outcome = derive_attempt_outcome(kind, attempt(partial=0.5, details=details))
    assert set(outcome["codes"]) == expected
```

Also test `semantic_match` with `actual_type != "str"` returns only `format.wrong_shape`.

- [ ] **Step 3: Run the tests and verify the derivation function is missing**

Run: `python -m pytest src/taxonomy-bench/tests/test_progression.py -q`

Expected: FAIL because `derive_attempt_outcome` is not defined.

- [ ] **Step 4: Implement the explicit kind-to-detail mapping**

Add:

```python
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
```

Implement `derive_attempt_outcome(kind, attempt)` with this precedence:

1. `attempt.error` → `unscored`, code `infrastructure`.
2. Missing score → `unscored`, code `infrastructure`.
3. `score.exact` → `exact`, no failure code.
4. Neither strict nor recovered JSON → only `format.unparseable`.
5. Parsed JSON with field/type failure → only `format.wrong_shape`.
6. Otherwise derive every applicable kind-specific code from the approved table.

Return `exact`, `partial`, `outcome`, `label`, `codes`, `failure_summary`, `latency_ms`, and `tokens`. Set `tokens=None` when the usage mapping is absent/empty; do not turn absent usage into zero.

- [ ] **Step 5: Run tests**

Run: `python -m pytest src/taxonomy-bench/tests/test_progression.py -q`

Expected: all outcome and mapping tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/taxonomy-bench/taxonomy_bench_progression.py src/taxonomy-bench/tests/test_progression.py
git commit -m "feat: derive task outcome diagnostics"
```

### Task 3: Build the first-pass progression view

**Files:**
- Modify: `src/taxonomy-bench/taxonomy_bench_progression.py`
- Modify: `src/taxonomy-bench/tests/test_progression.py`

- [ ] **Step 1: Write failing marker tests**

Create a `make_run(tier_outcomes, infra_indexes=())` helper that produces minimal run dictionaries with ordered tasks and an embedded summary.

Add tests for:

- frontier `0` produces `No reliable tier · Tier 1 · x/y exact`
- a fully reliable run produces no instability onset
- two adjacent sub-threshold tiers with at least eight scored tasks establish sustained breakdown
- a single sub-threshold tier reports `not established`
- peak isolated success remains separate from the reliable frontier
- first miss is the earliest scored non-exact task

- [ ] **Step 2: Write failing rolling-window and tier-stat tests**

```python
def test_progression_infers_tier_size_and_leaves_infrastructure_gap():
    run = make_run({1: [True] * 4, 2: [True, False, True, False]}, infra_indexes={4})
    view = derive_progression_view(run)
    assert view["rolling_window_size"] == 8
    assert view["tiers"][0]["median_latency_ms"] == 120.0
    assert view["rolling"][4]["exact_rate"] is None
    assert view["rolling"][3]["sample_count"] == 4
    assert view["tasks"][4]["outcome"] == "unscored"
    assert view["tiers"][0]["limited_evidence"] is False
```

Add a two-task tier case asserting `limited_evidence=True` and `evidence_note="limited evidence · 2 scored"`.

- [ ] **Step 3: Run tests and verify they fail**

Run: `python -m pytest src/taxonomy-bench/tests/test_progression.py -q`

Expected: FAIL because `derive_progression_view` is missing.

- [ ] **Step 4: Implement progression derivation**

Implement these pure helpers with the stated responsibilities:

- `infer_typical_tier_size(records) -> int`: count records by populated tier and return the ceiling of their median.
- `derive_tier_rows(task_rows) -> list[dict]`: group ordered rows by tier and calculate task/scored/exact counts, partial mean, first-attempt median latency, and contained rows.
- `derive_markers(task_rows, tier_rows, summary) -> dict`: produce first miss, reliable frontier, instability onset, sustained breakdown, and peak isolated success.
- `derive_rolling_points(task_rows, window_size) -> list[dict]`: preserve one point per ordered task while maintaining a scored-only trailing deque.
- `derive_progression_view(run) -> dict`: compose condition identity, task rows, tier rows, markers, rolling data, task-family aggregates, risk proxy, scorecards, and routing input.

Rules:

- Preserve `run["tasks"]` order and assign one-based `sequence_index`.
- Use only attempt records with `phase="first"` for first-pass rows and curves.
- Use `summary["reliable_frontier_first"]` and `summary["peak_tier_first"]`; do not redefine benchmark scoring.
- Infer typical tier size as `ceil(median(observed task counts by populated tier))`.
- Use `max(8, 2 * inferred_tier_size)` as the displayed rolling window.
- Append a chart gap for infrastructure errors and do not add that row to the scored rolling deque.
- Calculate per-tier exact/scored counts, mean partial, and median first-attempt latency from run records.
- Every tier row must expose `tier`, `task_count`, `scored_count`, `exact_count`, `exact_rate`, `partial_mean`, `median_latency_ms`, `limited_evidence`, `evidence_note`, and `tasks`. Set `limited_evidence=True` when fewer than four tasks are scored, matching the benchmark's serious-comparison guidance.
- Every rolling point must expose `sequence_index`, `task_id`, `sample_count`, `window_size`, `exact_rate`, and `partial_mean`. Infrastructure-gap points keep the first four identity/count fields but set both rates to `None`.
- Include task-family aggregates and retry branches, but never let retry rows alter first-pass metrics.

- [ ] **Step 5: Run derivation and regression tests**

Run: `python -m pytest src/taxonomy-bench/tests/test_progression.py src/taxonomy-bench/tests/test_taxonomy_bench.py -q`

Expected: all tests PASS and existing summary values remain unchanged.

- [ ] **Step 6: Commit**

```bash
git add src/taxonomy-bench/taxonomy_bench_progression.py src/taxonomy-bench/tests/test_progression.py
git commit -m "feat: derive benchmark progression evidence"
```

### Task 4: Add repeat evidence and routing interpretation

**Files:**
- Modify: `src/taxonomy-bench/taxonomy_bench_progression.py`
- Modify: `src/taxonomy-bench/taxonomy_bench.py:2017-2050`
- Modify: `src/taxonomy-bench/tests/test_progression.py`

- [ ] **Step 1: Write failing condition-separation tests**

Build three same-suite repeats and one otherwise identical continuous-session run.

Assert:

```python
conditions = derive_condition_evidence(runs)
assert len(conditions) == 2
isolated = next(item for item in conditions if item["configuration"]["session_mode"] == "isolated")
assert isolated["repeat_count"] == 3
assert isolated["evidence_level"] == "repeated model evidence"
```

The grouping key must include suite hash plus provider, requested model, effort, output mode, session mode, retry count/policy/context, transport retries, tool access, and condition label. Never include the repeat number in the key.

- [ ] **Step 2: Write failing same-task consistency tests**

For one task with outcomes `[exact, exact, non-exact]`, assert:

```python
task = isolated["tasks"][0]
assert task["exact_count"] == 2
assert task["observed_count"] == 3
assert task["flip_rate"] == pytest.approx(1 / 3)
assert task["median_partial"] == pytest.approx(1.0)
```

Define per-task flip rate as `minority outcome count / observed count`. Define condition flip rate as the sum of minority counts divided by all aligned observations. Keep every individual run ID selectable.

Each aligned condition-task row must expose `task_id`, `tier`, `kind`, `exact_count`, `observed_count`, `exact_rate`, `median_partial`, and `flip_rate`; the HTML renderer consumes these fields without recalculating them.

- [ ] **Step 3: Write failing routing and missing-usage tests**

Assert that:

- a `reverse_unlocks` result contributes the proxy label `reverse-dependency impact analysis`
- routing output contains `heuristic=True` and evidence references
- no output calls the unsupported-output proxy a hallucination rate
- absent reasoning/total tokens remain `None` in matrix rows
- multiple resolved model IDs set `resolved_model_changed=True`

- [ ] **Step 4: Run tests and verify they fail**

Run: `python -m pytest src/taxonomy-bench/tests/test_progression.py -q`

Expected: FAIL because repeat and routing functions are missing.

- [ ] **Step 5: Implement repeat evidence**

Add this exact grouping-key constant:

```python
CONDITION_CONFIG_KEYS = (
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
```

Implement `condition_key(run)` to prepend `run["suite_hash"]` to those configuration values. Implement `derive_condition_evidence(runs)` to group by that key, align task IDs only within each group, aggregate first-attempt evidence, and retain run IDs. Implement `derive_routing_interpretation(evidence)` to return `recommendation`, `heuristic=True`, and a list of cited evidence values.

Use a stable hash of the serialized grouping key for `condition_id`. Use Wilson intervals over all scored first attempts. Evidence labels are:

- one repeat: `session evidence`
- two repeats: `limited repeat evidence`
- three or more repeats: `repeated model evidence`

Routing wording stays descriptive: state the observed frontier and strongest/weakest task-family proxies, recommend independent verification beyond the frontier, and cite latency, repeat consistency when measured, and unsupported-output proxy. It must never emit a composite winner label.

- [ ] **Step 6: Enrich the matrix artifact without deleting existing run rows**

Keep `matrix["runs"]` for compatibility, add `matrix["conditions"] = derive_condition_evidence(runs)`, and change absent token defaults from `0` to `None`.

- [ ] **Step 7: Run tests**

Run: `python -m pytest src/taxonomy-bench/tests/test_progression.py src/taxonomy-bench/tests/test_taxonomy_bench.py -q`

Expected: all tests PASS.

- [ ] **Step 8: Commit**

```bash
git add src/taxonomy-bench/taxonomy_bench_progression.py src/taxonomy-bench/taxonomy_bench.py src/taxonomy-bench/tests/test_progression.py
git commit -m "feat: add repeat-aware routing evidence"
```

### Task 5: Render the standalone run progression report

**Files:**
- Modify: `src/taxonomy-bench/taxonomy_bench_report.py`
- Modify: `src/taxonomy-bench/taxonomy_bench.py:1805-1924`
- Create: `src/taxonomy-bench/tests/test_report_html.py`

- [ ] **Step 1: Write failing report-structure tests**

```python
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from taxonomy_bench_report import render_run_html

def test_run_report_prioritizes_progression_evidence(sample_run):
    rendered = render_run_html(sample_run, attribution="Test attribution")
    assert "Benchmark Progression" in rendered
    assert "Reliable frontier" in rendered
    assert "Instability onset" in rendered
    assert "Sustained breakdown" in rendered
    assert "1.00 exact" in rendered
    assert 'data-kind="reverse_unlocks"' in rendered
    assert "recovery phase" in rendered.lower()
    assert "routing heuristic" in rendered.lower()
    assert "PASS</" not in rendered
    assert "FAIL</" not in rendered
```

- [ ] **Step 2: Write failing accessibility and privacy tests**

Assert the generated document:

- has `lang="en"`, a descriptive `title`, and one `h1`
- uses buttons/links for filters and minimap navigation
- includes visible focus styles and reduced-motion handling
- declares body text at least 15px and supporting text at least 13px
- includes no external `script src`, stylesheet, font, or network URL
- contains no serialized `scorer` object or private constraint keys
- renders missing tokens as `not reported` and zero-retry recovery as `not measured`

- [ ] **Step 3: Run tests and verify they fail**

Run: `python -m pytest src/taxonomy-bench/tests/test_report_html.py -q`

Expected: FAIL because the report module has no renderer.

- [ ] **Step 4: Implement focused HTML component functions**

Implement `render_run_html(run, attribution)` as the public entry point and split its markup across these private helpers: `_render_condition_header`, `_render_frontier_strip`, `_render_progression_svg`, `_render_tier_group`, `_render_task_row`, `_render_diagnostic_sidebar`, and `_render_metadata`. Each helper accepts only its required view-model slice and returns one escaped HTML fragment.

Use `html.escape` for all run-provided text and `json.dumps` only inside escaped metadata/details. Render a sticky tier header, one textual outcome row per first attempt, indented recovery-phase branches, a right-side anchor minimap, and inline SVG for rolling exact/partial values. Use `<details>` for response/diagnostic expansion.

Render each tier's `scored_count/task_count` and `evidence_note` directly from the view model. Render rolling-chart sample labels from each point's `sample_count/window_size`; do not infer sample counts or evidence warnings inside the renderer.

Embed minimal JavaScript that filters existing rows by outcome/kind and updates an accessible result count. Do not implement live-follow behavior, network calls, or a framework.

- [ ] **Step 5: Replace the old inline renderer behind a compatibility wrapper**

In `taxonomy_bench.py`:

```python
from taxonomy_bench_report import render_run_html as _render_run_html


def render_run_html(run: Mapping[str, Any]) -> str:
    return _render_run_html(run, attribution=ATTRIBUTION)
```

Delete only the old run-rendering body after the new tests pass. Keep `_fmt_percent` and `_fmt_num` temporarily because the old matrix renderer still uses them until Task 6.

- [ ] **Step 6: Run report and save-run tests**

Run: `python -m pytest src/taxonomy-bench/tests/test_report_html.py src/taxonomy-bench/tests/test_taxonomy_bench.py::test_suite_generation_and_oracle_run -q`

Expected: PASS; `save_run` still emits `report.html`.

- [ ] **Step 7: Commit**

```bash
git add src/taxonomy-bench/taxonomy_bench_report.py src/taxonomy-bench/taxonomy_bench.py src/taxonomy-bench/tests/test_report_html.py
git commit -m "feat: render benchmark progression report"
```

### Task 6: Render repeat-aware comparison scorecards

**Files:**
- Modify: `src/taxonomy-bench/taxonomy_bench_report.py`
- Modify: `src/taxonomy-bench/taxonomy_bench.py:2052-2081`
- Modify: `src/taxonomy-bench/tests/test_report_html.py`

- [ ] **Step 1: Write failing matrix-report tests**

For a matrix with three repeats, assert:

```python
def test_matrix_report_shows_repeat_evidence_and_run_links(matrix):
    rendered = render_matrix_html(matrix, attribution="Test attribution")
    assert "repeated model evidence" in rendered
    assert "95% Wilson interval" in rendered
    assert "outcome flip rate" in rendered
    assert "unsupported-output proxy" in rendered
    assert "success by task family" in rendered.lower()
    for row in matrix["runs"]:
        assert f'{row["run_id"]}/report.html' in rendered
```

Also assert isolated and continuous conditions render as separate cards, unresolved model changes show a warning, and no card is labeled `winner`.

Add a legacy compatibility case:

```python
def test_matrix_report_falls_back_for_format_v1_runs_only_matrix():
    legacy = {
        "format_version": 1,
        "benchmark_version": "0.1.0",
        "runs": [{
            "run_id": "legacy-run",
            "model": "legacy-model",
            "effort": "low",
            "base_strength": 50.0,
            "frontier_first": 3,
            "median_latency_ms": 250.0,
        }],
    }
    rendered = render_matrix_html(legacy, attribution="Test attribution")
    assert "Legacy matrix · repeat evidence unavailable" in rendered
    assert "legacy-model" in rendered
    assert "legacy-run/report.html" in rendered
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `python -m pytest src/taxonomy-bench/tests/test_report_html.py -q`

Expected: FAIL because the matrix renderer still uses the old flat table.

- [ ] **Step 3: Implement the matrix renderer**

Implement `render_matrix_html(matrix, attribution)` as the public entry point. When `matrix.get("conditions")` is present, use `_render_condition_card(condition)` for each grouped condition and `_render_repeat_task_table(condition)` for its aligned task evidence; both helpers return escaped HTML fragments.

When `conditions` is absent, call `_render_legacy_matrix(matrix["runs"])`. The fallback renders the existing flat fields, links each run ID to its report, and visibly states `Legacy matrix · repeat evidence unavailable`; it must not fabricate confidence, consistency, task-family, or routing evidence.

Each condition card shows sample count, exact-rate interval, frontier distribution, median latency, condition flip rate, unsupported-output proxy, resolved-model warning, and routing heuristic. A task-family table and aligned per-task repeat table sit beneath the cards; the latter renders `exact_count/observed_count`, `median_partial`, and `flip_rate` directly from each condition-task row. Individual run links preserve access to the full progression trace.

Sort conditions by requested model and effort for stable navigation, not by a composite winner score.

- [ ] **Step 4: Replace the old matrix renderer behind a compatibility wrapper**

```python
from taxonomy_bench_report import render_matrix_html as _render_matrix_html


def render_matrix_html(matrix: Mapping[str, Any]) -> str:
    return _render_matrix_html(matrix, attribution=ATTRIBUTION)
```

After the wrapper is active, remove the old matrix-rendering body, `_fmt_percent`, and `_fmt_num`. Remove the core `html` import too if no remaining core code uses it.

- [ ] **Step 5: Run report and matrix regressions**

Run: `python -m pytest src/taxonomy-bench/tests/test_report_html.py src/taxonomy-bench/tests/test_progression.py src/taxonomy-bench/tests/test_taxonomy_bench.py -q`

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/taxonomy-bench/taxonomy_bench_report.py src/taxonomy-bench/taxonomy_bench.py src/taxonomy-bench/tests/test_report_html.py
git commit -m "feat: render repeat evidence scorecards"
```

### Task 7: Document behavior and update package metadata

**Files:**
- Modify: `src/taxonomy-bench/README.md:137-169,210-223`
- Modify: `src/taxonomy-bench/BENCHMARK_SPEC.md:101-115,135-145`
- Modify: `src/taxonomy-bench/pyproject.toml:6-8`
- Modify: `src/taxonomy-bench/taxonomy_bench.py:32-34`
- Modify: `src/taxonomy-bench/tests/test_taxonomy_bench.py:1-10`

- [ ] **Step 1: Add a failing version-consistency test**

Add `import re` with the standard-library imports, then add:

```python
def test_package_and_runtime_versions_match():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version = "([^"]+)"$', text, flags=re.MULTILINE)
    assert match is not None
    assert match.group(1) == tb.BENCHMARK_VERSION == "0.2.0"
```

- [ ] **Step 2: Run the test and verify it protects the metadata edit**

Run: `python -m pytest src/taxonomy-bench/tests/test_taxonomy_bench.py::test_package_and_runtime_versions_match -q`

Expected: FAIL because the current package and runtime version are still `0.1.0`.

- [ ] **Step 3: Bump the feature version to 0.2.0**

Set both `project.version` and `BENCHMARK_VERSION` to `0.2.0`. Keep `FORMAT_VERSION = 1` because run-record compatibility is unchanged. Add `build>=1.2,<2` to the `test` optional dependency group so release verification does not require an implicit system-level install.

- [ ] **Step 4: Update documentation**

Document:

- `report.html` as the first-pass progression trace
- exact/partial/unparseable/infrastructure outcome wording
- recovery-phase placement
- marker definitions and rolling window
- `matrix.html` condition grouping, repeat evidence, and per-run drill-down
- unsupported-output as a proxy, not a general hallucination rate
- Marble-to-agentic-coding recommendations as routing heuristics
- missing token/recovery values as `not reported`/`not measured`

Do not duplicate the full design document in the README.

- [ ] **Step 5: Run docs-adjacent tests**

Run: `python -m pytest src/taxonomy-bench/tests/test_taxonomy_bench.py::test_package_and_runtime_versions_match src/taxonomy-bench/tests/test_report_html.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/taxonomy-bench/README.md src/taxonomy-bench/BENCHMARK_SPEC.md src/taxonomy-bench/pyproject.toml src/taxonomy-bench/taxonomy_bench.py src/taxonomy-bench/tests/test_taxonomy_bench.py
git commit -m "docs: describe progression report evidence"
```

### Task 8: Verify visuals, build the release artifact, and refresh validation records

**Files:**
- Create: `src/taxonomy-bench/scripts/package-release.ps1`
- Modify: `src/taxonomy-bench/VALIDATION.md`
- Modify mechanically: `src/taxonomy-bench/SHA256SUMS`
- Regenerate mechanically: `src/taxonomy-bench.zip`

- [ ] **Step 1: Run the complete automated suite**

Run: `python -m pytest src/taxonomy-bench/tests -q`

Expected: all legacy, progression, repeat, renderer, privacy, and accessibility tests PASS.

- [ ] **Step 2: Generate an oracle visual fixture without an API call**

Run from the repository root in PowerShell:

```powershell
@'
from pathlib import Path
import sys

sys.path.insert(0, "src/taxonomy-bench")
sys.path.insert(0, "src/taxonomy-bench/tests")
import test_taxonomy_bench as fixtures
import taxonomy_bench as tb

suite = fixtures.load_fixture_suite(tasks_per_tier=4)
provider = fixtures.OracleProvider(suite, wrong_first=True)
run = tb.execute_run(
    suite=suite,
    provider=provider,
    run_meta={"provider": "oracle", "model": "oracle", "effort": "test"},
    retries=1,
    retry_policy="feedback",
    retry_context="continued",
    session_mode="continuous",
    progress=False,
)
tb.save_run(run, Path(".superpowers/hud-visual"))
'@ | python -
```

Expected: `.superpowers/hud-visual/report.html` exists and contains 32 first-pass rows plus recovery branches.

- [ ] **Step 3: Perform browser visual QA**

Serve the fixture:

`python -m http.server 7788 --directory .superpowers/hud-visual`

Inspect `http://localhost:7788/report.html` at approximately 1440×900 and 768px width. Verify:

- 8–12 task rows are visible at desktop height
- supporting text is readable and no required text is below 13px
- exact/non-exact/unscored meaning survives grayscale/color-disabled inspection
- sticky tier headers, filters, minimap anchors, and details work
- progression remains above scorecards on narrow width
- no horizontal clipping at 200% zoom

Save screenshots beside the visual fixture.

- [ ] **Step 4: Build and smoke-test the wheel**

Run:

```powershell
New-Item -ItemType Directory -Force -Path '.superpowers/taxonomy-bench-release' | Out-Null
python -m pip install -e "src/taxonomy-bench[test]"
python -m build --wheel src/taxonomy-bench --outdir .superpowers/taxonomy-bench-release
python -m pip install --force-reinstall .superpowers/taxonomy-bench-release/taxonomy_bench-0.2.0-py3-none-any.whl
taxonomy-bench --version
taxonomy-bench validate --taxonomy src/taxonomy-bench/sample_data
```

Expected:

- wheel build succeeds
- `taxonomy-bench 0.2.0`
- sample taxonomy reports valid with 64 topics and 156 dependencies
- the tracked source tree's ignored `dist/` directory is not used, so an old 0.1.0 wheel cannot leak into the new archive

- [ ] **Step 5: Create the reproducible release packager and update validation**

Update `VALIDATION.md` with the new test count, report checks, browser viewport checks, package version, and validation date.

Create `scripts/package-release.ps1` with mandatory `-WheelPath` and optional `-ArchivePath` parameters. Resolve the project root from `$PSScriptRoot`, not the caller's current directory. Use this exact archive-path-to-source mapping:

```powershell
$releaseEntries = [ordered]@{
  '.gitignore' = Join-Path $projectRoot '.gitignore'
  'BENCHMARK_SPEC.md' = Join-Path $projectRoot 'BENCHMARK_SPEC.md'
  'LICENSE' = Join-Path $projectRoot 'LICENSE'
  'NOTICE.md' = Join-Path $projectRoot 'NOTICE.md'
  'README.md' = Join-Path $projectRoot 'README.md'
  'VALIDATION.md' = Join-Path $projectRoot 'VALIDATION.md'
  'dist/taxonomy_bench-0.2.0-py3-none-any.whl' = (Resolve-Path $WheelPath).Path
  'pyproject.toml' = Join-Path $projectRoot 'pyproject.toml'
  'sample_data/dependencies.json' = Join-Path $projectRoot 'sample_data/dependencies.json'
  'sample_data/manifest.json' = Join-Path $projectRoot 'sample_data/manifest.json'
  'sample_data/topics.json' = Join-Path $projectRoot 'sample_data/topics.json'
  'scripts/package-release.ps1' = Join-Path $projectRoot 'scripts/package-release.ps1'
  'taxonomy_bench.py' = Join-Path $projectRoot 'taxonomy_bench.py'
  'taxonomy_bench_progression.py' = Join-Path $projectRoot 'taxonomy_bench_progression.py'
  'taxonomy_bench_report.py' = Join-Path $projectRoot 'taxonomy_bench_report.py'
  'tests/test_progression.py' = Join-Path $projectRoot 'tests/test_progression.py'
  'tests/test_report_html.py' = Join-Path $projectRoot 'tests/test_report_html.py'
  'tests/test_taxonomy_bench.py' = Join-Path $projectRoot 'tests/test_taxonomy_bench.py'
}
```

The script must:

1. Compute SHA-256 for each mapped source and write `SHA256SUMS` using the archive paths; exclude `SHA256SUMS` from its own hash list.
2. Re-read every checksum line and fail on any mismatch.
3. Create `<ArchivePath>.new` with .NET `ZipArchive`, adding only the mapped entries plus `SHA256SUMS` under a top-level `taxonomy-bench/` folder.
4. Replace the tracked archive with the completed `.new` file only after the zip closes successfully.
5. Re-open the archive and assert its entry set equals the explicit mapping plus `taxonomy-bench/SHA256SUMS`.
6. Assert no archive entry contains `taxonomy_bench-0.1.0`.

This explicit mapping is required because `src/taxonomy-bench/dist/` is ignored and can contain a stale 0.1.0 wheel.

- [ ] **Step 6: Regenerate and inspect the tracked source archive**

Run from the repository root:

```powershell
& 'src/taxonomy-bench/scripts/package-release.ps1' `
  -WheelPath '.superpowers/taxonomy-bench-release/taxonomy_bench-0.2.0-py3-none-any.whl' `
  -ArchivePath 'src/taxonomy-bench.zip'
```

Expected: the script exits successfully, every checksum verifies, and the archive contains:

- both reporting modules
- both reporting test files
- only the 0.2.0 wheel
- the refreshed `SHA256SUMS`
- `scripts/package-release.ps1`

- [ ] **Step 7: Run final verification**

Run:

```powershell
python -m pytest src/taxonomy-bench/tests -q
git diff --check
git status --short
```

Expected: tests PASS, no whitespace errors, and only intended validation/archive files remain uncommitted.

- [ ] **Step 8: Commit release artifacts**

```bash
git add src/taxonomy-bench/scripts/package-release.ps1 src/taxonomy-bench/VALIDATION.md src/taxonomy-bench/SHA256SUMS src/taxonomy-bench.zip
git commit -m "chore: refresh taxonomy bench release artifacts"
```

## Completion criteria

- The run report answers all eight acceptance questions from the approved design without opening raw JSON.
- The matrix report distinguishes single-session, limited-repeat, and repeated-model evidence.
- Every diagnostic code is derived only from fields present in `run.json`.
- Retry results never alter first-pass progression metrics.
- Private scorer constraints never enter standard reports.
- No composite winner score, general hallucination-rate claim, live event path, or frontend framework is introduced.
- Tests, browser checks, wheel smoke tests, checksums, and the tracked archive all verify successfully.

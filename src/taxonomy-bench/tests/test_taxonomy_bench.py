from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import zipfile
from collections import defaultdict, deque
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import taxonomy_bench as tb
import taxonomy_bench_cli
import taxonomy_bench_protocol


# ---------------------------------------------------------------------------
# Provider seam compatibility tests (Task 2)
# ---------------------------------------------------------------------------


def test_provider_types_remain_public():
    """Provider and Completion must be accessible from taxonomy_bench."""
    assert tb.Provider is taxonomy_bench_cli.Provider
    assert tb.Completion is taxonomy_bench_cli.Completion
    completion = tb.Completion(text="{}", latency_ms=1.0)
    assert completion.error_kind is None
    assert completion.provider_metadata == {}


def test_instruction_hash_has_one_source():
    """BASE_INSTRUCTIONS must have a single owner in the protocol module."""
    assert tb.BASE_INSTRUCTIONS is taxonomy_bench_protocol.BASE_INSTRUCTIONS
    assert len(tb.BASE_INSTRUCTIONS) > 0


def test_openai_provider_uses_protocol_instructions():
    """OpenAIProvider must reference the protocol BASE_INSTRUCTIONS."""
    from taxonomy_bench_protocol import BASE_INSTRUCTIONS as proto_instructions
    # Parse the source to verify the module-level reference
    import taxonomy_bench as tb_module
    import inspect
    src = inspect.getsource(tb_module.OpenAIProvider.complete)
    assert "BASE_INSTRUCTIONS" in src


def test_package_and_runtime_versions_match():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version = "([^"]+)"$', text, flags=re.MULTILINE)
    assert match is not None
    assert match.group(1) == tb.BENCHMARK_VERSION == "0.2.0"


def test_release_packager_rejects_renamed_wrong_version_wheel(tmp_path: Path):
    pwsh = shutil.which("pwsh")
    if pwsh is None:
        pytest.skip("PowerShell is required to exercise the release packager")

    project = tmp_path / "taxonomy-bench"
    script = project / "scripts" / "package-release.ps1"
    script.parent.mkdir(parents=True)
    shutil.copy2(ROOT / "scripts" / "package-release.ps1", script)

    fixture_paths = (
        ".gitignore",
        "BENCHMARK_SPEC.md",
        "LICENSE",
        "NOTICE.md",
        "README.md",
        "VALIDATION.md",
        "pyproject.toml",
        "sample_data/dependencies.json",
        "sample_data/manifest.json",
        "sample_data/topics.json",
        "taxonomy_bench.py",
        "taxonomy_bench_progression.py",
        "taxonomy_bench_report.py",
        "tests/test_progression.py",
        "tests/test_report_html.py",
        "tests/test_taxonomy_bench.py",
    )
    for relative_path in fixture_paths:
        path = project / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"fixture for {relative_path}\n", encoding="utf-8")

    disguised_wheel = tmp_path / "taxonomy_bench-0.2.0-py3-none-any.whl"
    with zipfile.ZipFile(disguised_wheel, "w") as wheel:
        wheel.writestr(
            "taxonomy_bench-0.2.0.dist-info/METADATA",
            "Metadata-Version: 2.1\nName: taxonomy-bench\nVersion: 0.1.0\n",
        )

    archive = tmp_path / "taxonomy-bench.zip"
    result = subprocess.run(
        [
            pwsh,
            "-NoProfile",
            "-File",
            str(script),
            "-WheelPath",
            str(disguised_wheel),
            "-ArchivePath",
            str(archive),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "Wheel METADATA version must be 0.2.0" in (result.stdout + result.stderr)
    assert not archive.exists()


def test_generic_run_rejects_subscription_providers():
    for name in ("claude-cli", "codex-cli"):
        args = tb.build_parser().parse_args([
            "run", "--suite", "unused.json", "--provider", name,
            "--model", "x",
        ])
        with pytest.raises(tb.BenchError, match="wave"):
            tb.build_provider(args)


def correct_answer(task: dict) -> str:
    scorer = task["scorer"]
    kind = scorer["type"]
    if kind == "id":
        value = {"id": scorer["expected"]}
    elif kind == "ids_set":
        value = {"ids": scorer["expected"]}
    elif kind == "issues_set":
        value = {"issues": scorer["expected"]}
    elif kind == "topological_order":
        nodes = set(scorer["nodes"])
        indegree = {node: 0 for node in nodes}
        outgoing = defaultdict(list)
        for prereq, topic in scorer["edges"]:
            outgoing[prereq].append(topic)
            indegree[topic] += 1
        ready = deque(sorted(node for node, degree in indegree.items() if degree == 0))
        order = []
        while ready:
            node = ready.popleft()
            order.append(node)
            for nxt in sorted(outgoing[node]):
                indegree[nxt] -= 1
                if indegree[nxt] == 0:
                    ready.append(nxt)
        value = {"ids": order}
    elif kind == "shortest_path":
        outgoing = defaultdict(list)
        for source, target in scorer["edges"]:
            outgoing[source].append(target)
        parent = {scorer["source"]: None}
        queue = deque([scorer["source"]])
        while queue and scorer["target"] not in parent:
            node = queue.popleft()
            for nxt in outgoing[node]:
                if nxt not in parent:
                    parent[nxt] = node
                    queue.append(nxt)
        path = [scorer["target"]]
        cursor = scorer["target"]
        while parent[cursor] is not None:
            cursor = parent[cursor]
            path.append(cursor)
        path.reverse()
        value = {"ids": path}
    elif kind == "mastery_plan":
        nodes = set(scorer["required"])
        indegree = {node: 0 for node in nodes}
        outgoing = defaultdict(list)
        for prereq, topic in scorer["edges"]:
            outgoing[prereq].append(topic)
            indegree[topic] += 1
        ready = deque(sorted(node for node, degree in indegree.items() if degree == 0 and node != scorer["target"]))
        order = []
        while ready:
            node = ready.popleft()
            order.append(node)
            for nxt in sorted(outgoing[node]):
                indegree[nxt] -= 1
                if indegree[nxt] == 0 and nxt != scorer["target"]:
                    ready.append(nxt)
        # Any independent non-target nodes not reached above.
        for node in sorted(nodes - set(order) - {scorer["target"]}):
            order.append(node)
        order.append(scorer["target"])
        value = {"ids": order}
    else:
        raise AssertionError(kind)
    return json.dumps(value)


class OracleProvider(tb.Provider):
    supports_sessions = True

    def __init__(self, suite: dict, wrong_first: bool = False) -> None:
        self.answers = {task["prompt"]: correct_answer(task) for task in suite["tasks"]}
        self.prompt_by_response_id = {}
        self.counter = 0
        self.wrong_first = wrong_first
        self.first_phase = True

    def complete(self, prompt, output_schema, previous_response_id=None):
        self.counter += 1
        response_id = f"resp-{self.counter}"
        if prompt in self.answers:
            original_prompt = prompt
        elif previous_response_id in self.prompt_by_response_id:
            original_prompt = self.prompt_by_response_id[previous_response_id]
        else:
            # Fresh feedback retries include the original prompt as a prefix.
            matches = [key for key in self.answers if prompt.startswith(key)]
            if not matches:
                raise AssertionError("Could not map prompt to task")
            original_prompt = matches[0]
        self.prompt_by_response_id[response_id] = original_prompt
        is_retry = prompt not in self.answers
        if self.wrong_first and not is_retry:
            text = '{"ids":[]}'
        else:
            text = self.answers[original_prompt]
        return tb.Completion(
            text=text,
            latency_ms=10.0,
            response_id=response_id,
            status="completed",
            usage={"input_tokens": 10, "output_tokens": 5, "reasoning_tokens": 2, "total_tokens": 15},
        )


def load_fixture_suite(tasks_per_tier: int = 2) -> dict:
    taxonomy = tb.Taxonomy.load(ROOT / "sample_data")
    assert not taxonomy.validate()
    return tb.SuiteGenerator(taxonomy, seed=42).generate(max_tier=8, tasks_per_tier=tasks_per_tier)


def test_parser_strict_and_recovered_json():
    strict = tb.parse_answer('{"id":"mt_001"}')
    assert strict.strict_json and not strict.recovered_json
    recovered = tb.parse_answer('```json\n{"id":"mt_001"}\n```')
    assert not recovered.strict_json and recovered.recovered_json
    prose = tb.parse_answer('Answer: {"id":"mt_001"}.')
    assert prose.recovered_json


def test_suite_generation_and_oracle_run(tmp_path: Path):
    suite = load_fixture_suite(tasks_per_tier=2)
    assert len(suite["tasks"]) == 16
    provider = OracleProvider(suite)
    run = tb.execute_run(
        suite=suite,
        provider=provider,
        run_meta={"provider": "oracle", "model": "oracle", "effort": "none"},
        retries=0,
        retry_policy="feedback",
        retry_context="continued",
        session_mode="continuous",
        progress=False,
    )
    assert run["summary"]["first_attempt_accuracy"] == 1.0
    assert run["summary"]["eventual_accuracy"] == 1.0
    assert run["summary"]["reliable_frontier_first"] == 8
    assert run["summary"]["retry_recovery_rate"] is None
    tb.save_run(run, tmp_path)
    assert (tmp_path / "report.html").exists()
    assert (tmp_path / "summary.json").exists()


def test_retry_recovery_is_paired():
    suite = load_fixture_suite(tasks_per_tier=1)
    provider = OracleProvider(suite, wrong_first=True)
    run = tb.execute_run(
        suite=suite,
        provider=provider,
        run_meta={"provider": "oracle", "model": "oracle", "effort": "none"},
        retries=1,
        retry_policy="feedback",
        retry_context="continued",
        session_mode="continuous",
        progress=False,
    )
    summary = run["summary"]
    assert summary["first_attempt_accuracy"] == 0.0
    assert summary["eventual_accuracy"] == 1.0
    assert summary["retry_recovery_rate"] == 1.0
    assert summary["first_attempt_failures"] == 8
    assert summary["retried_failures"] == 8
    assert all(len(task["attempts"]) == 2 for task in run["tasks"])


def test_execute_run_invokes_checkpoint_after_each_attempt():
    suite = load_fixture_suite(tasks_per_tier=1)
    provider = OracleProvider(suite, wrong_first=True)
    seen: list[tuple[str, int, int]] = []

    def checkpoint(run_id: str, envelope: dict) -> None:
        seen.append((
            run_id,
            len(envelope["tasks"]),
            sum(len(task["attempts"]) for task in envelope["tasks"]),
        ))

    run = tb.execute_run(
        suite=suite,
        provider=provider,
        run_meta={"provider": "oracle", "model": "oracle", "effort": "none"},
        retries=1,
        retry_policy="feedback",
        retry_context="continued",
        session_mode="isolated",
        progress=False,
        attempt_checkpoint=checkpoint,
    )
    assert len(seen) == len(suite["tasks"]) * 2
    assert {item[0] for item in seen} == {run["run_id"]}
    assert [item[2] for item in seen] == list(range(1, len(seen) + 1))


def test_scoring_rejects_invalid_topological_order():
    suite = load_fixture_suite(tasks_per_tier=2)
    task = next(task for task in suite["tasks"] if task["scorer"]["type"] == "topological_order")
    nodes = list(reversed(task["scorer"]["nodes"]))
    result = tb.score_text(task, json.dumps({"ids": nodes}))
    assert not result["exact"]
    assert 0 <= result["partial"] < 1


def test_private_suite_hash_detects_tampering(tmp_path: Path):
    suite = load_fixture_suite(tasks_per_tier=1)
    path = tmp_path / "suite.private.json"
    path.write_text(json.dumps(suite), encoding="utf-8")
    loaded = tb.load_suite(path)
    assert loaded["suite_hash"] == suite["suite_hash"]

    suite["tasks"][0]["tier"] = 8
    path.write_text(json.dumps(suite), encoding="utf-8")
    try:
        tb.load_suite(path)
    except tb.BenchError as exc:
        assert "hash mismatch" in str(exc).lower()
    else:
        raise AssertionError("Tampered suite should be rejected")


def test_external_attempts_must_start_at_one():
    suite = load_fixture_suite(tasks_per_tier=1)
    responses = [
        {
            "task_id": suite["tasks"][0]["id"],
            "attempt": 2,
            "text": correct_answer(suite["tasks"][0]),
        }
    ]
    try:
        tb.score_external_responses(suite, responses, {"model": "manual"})
    except tb.BenchError as exc:
        assert "attempt 1" in str(exc)
    else:
        raise AssertionError("Missing attempt 1 should be rejected")

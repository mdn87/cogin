import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import human_review


def test_scores_require_a_human_attestation_and_complete_cases():
    cases = {"case-a": {"changed_lines": 4}, "case-b": {"changed_lines": 2}}
    form = {"reviewer": "Matt", "blind_attestation": True, "scores": [
        {"case_id": "case-a", "human_cleanup_lines": 0, "reason": "All changes are required."},
        {"case_id": "case-b", "human_cleanup_lines": 1, "reason": "Revert one unrelated comment."},
    ]}
    assert human_review.validate_scores(form, cases)["case-a"]["human_cleanup_lines"] == 0
    for bad in ({**form, "blind_attestation": False}, {**form, "reviewer": ""},
                {**form, "scores": form["scores"][:1]},
                {**form, "scores": [form["scores"][0], form["scores"][0]]}):
        with pytest.raises(ValueError):
            human_review.validate_scores(bad, cases)


@pytest.mark.parametrize("value", [None, True, -1, 5, 0.5, "0"])
def test_invalid_cleanup_scores_are_not_silently_coerced(value):
    with pytest.raises(ValueError):
        human_review.validate_scores({"reviewer": "Matt", "blind_attestation": True,
            "scores": [{"case_id": "a", "human_cleanup_lines": value, "reason": "reviewed"}]},
            {"a": {"changed_lines": 4}})


def test_approval_counts_distinguish_zero_unmeasured_and_incomplete():
    import supervised

    assert supervised.approval_metrics([], completed=True, operator="Matt")["interruptions"] == 0
    assert supervised.approval_metrics([], completed=False, operator="Matt")["interruptions"] is None
    request = {"kind": "request", "request_id": "a", "payload": {"command": "python -m unittest"}}
    decision = {"kind": "decision", "request_id": "a", "decision": "deny", "actor": "human", "operator": "Matt"}
    assert supervised.approval_metrics([request], completed=True, operator="Matt")["interruptions"] is None
    measured = supervised.approval_metrics([request, decision], completed=True, operator="Matt")
    assert measured["interruptions"] == 1 and measured["denied"] == 1
    assert supervised.approval_metrics([request, {**decision, "actor": "qualification"}],
                                      completed=True, operator="Matt")["interruptions"] is None


def test_native_approval_decoding_and_responses_preserve_ids_and_deny_by_default():
    import supervised

    codex = {"id": 7, "method": "item/commandExecution/requestApproval", "params": {"command": "python -m unittest"}}
    claude = {"type": "control_request", "request_id": "r1", "request": {
        "subtype": "can_use_tool", "tool_name": "Bash", "input": {"command": "python -m unittest"}}}
    assert supervised.approval_request("codex", codex)["request_id"] == "7"
    assert supervised.approval_response("codex", codex, "deny") == {"id": 7, "result": {"decision": "decline"}}
    cancel_only = {**codex, "params": {"availableDecisions": ["accept", "cancel"]}}
    assert supervised.approval_response("codex", cancel_only, "deny")["result"]["decision"] == "cancel"
    reply = supervised.approval_response("claude", claude, "allow")
    assert reply["response"]["request_id"] == "r1"
    assert reply["response"]["response"]["updatedInput"] == claude["request"]["input"]
    with pytest.raises(ValueError):
        supervised.approval_response("codex", codex, "always")
    assert supervised.approval_request("agy", {"event": "step_update", "step_update": {
        "state": "ERROR", "tool_info": {"error": {"message": "permission denied"}}}}) is None


def review_fixture(tmp_path, monkeypatch):
    import harness

    root = tmp_path / "batch"
    artifacts = root / "results/claude-1"
    artifacts.mkdir(parents=True)
    (root / "task.txt").write_text("Add the status filter.")
    manifest = {"protocol_version": 2, "seed_commit": "seed", "prompt_sha256": harness.file_hash(root / "task.txt"),
                "fixture_hashes": {p.name: harness.file_hash(p) for p in (harness.HERE / "fixture").iterdir() if p.is_file()}}
    harness.save(root / "manifest.json", manifest)
    (artifacts / "changes.patch").write_text("diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n@@ -1 +1 @@\n-old\n+new\n")
    row = {"valid": True, "task_passed": True, "lane": "claude", "run_id": "claude-1", "source_batch": "batch",
           "source_manifest_sha256": harness.file_hash(root / "manifest.json"), "changed_lines": 2,
           "patch_sha256": harness.file_hash(artifacts / "changes.patch"), "interruptions": None, "human_cleanup_lines": None}
    report = tmp_path / "original-report.json"
    harness.save(report, {**manifest, "runs": [row]})
    monkeypatch.setattr(harness, "load_manifest", lambda root: manifest)
    monkeypatch.setattr(harness, "assess_record", lambda *args: row.copy())
    return root, report


def test_blind_package_import_preserves_sources_and_never_exposes_lane_metadata(tmp_path, monkeypatch):
    import harness

    root, report = review_fixture(tmp_path, monkeypatch)
    original = report.read_bytes()
    package = tmp_path / "review"
    reviewer = human_review.prepare(report, [root], package)
    for path in reviewer.rglob("*"):
        assert "claude" not in path.as_posix()
        if path.is_file():
            assert "claude-1" not in path.read_text()
    derived = human_review.read(package / "controller/report.json")
    assert derived["runs"][0]["human_cleanup_lines"] is None
    form = human_review.read(reviewer / "scores.json")
    form.update(reviewer="Matt", blind_attestation=True)
    form["scores"][0].update(human_cleanup_lines=0, reason="All changes implement the requested feature.")
    harness.save(reviewer / "scores.json", form)
    human_review.import_scores(package, reviewer / "scores.json")
    derived = human_review.read(package / "controller/report.json")
    assert derived["runs"][0]["human_cleanup_lines"] == 0
    assert derived["runs"][0]["interruptions"] is None
    assert report.read_bytes() == original
    with pytest.raises(ValueError, match="already imported"):
        human_review.import_scores(package, reviewer / "scores.json")


def test_changed_blind_patch_or_source_report_rejects_scores(tmp_path, monkeypatch):
    root, report = review_fixture(tmp_path, monkeypatch)
    package = tmp_path / "review"
    human_review.prepare(report, [root], package)
    patch = next((package / "reviewer/cases").glob("*/changes.patch"))
    patch.write_text("changed")
    with pytest.raises(ValueError, match="package changed"):
        human_review.import_scores(package, package / "reviewer/scores.json")
    report.write_text("{}")
    with pytest.raises(ValueError, match="Source report changed"):
        human_review.render(package)


def test_duplicate_requests_and_orphan_decisions_are_unmeasured():
    import supervised

    request = {"kind": "request", "request_id": "1", "payload": {}}
    decision = {"kind": "decision", "request_id": "1", "decision": "allow", "actor": "human", "operator": "Matt"}
    for events in ([request, request, decision], [decision], [decision, request], [request, decision, decision]):
        assert supervised.approval_metrics(events, completed=True, operator="Matt")["interruptions"] is None


def test_supervised_run_requires_human_terminal_before_creating_evidence(tmp_path, monkeypatch):
    import supervised

    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    output = tmp_path / "capture"
    with pytest.raises(ValueError, match="interactive terminal"):
        supervised.capture(tmp_path, "claude", output, "Matt")
    assert not output.exists()
    with pytest.raises(ValueError, match="no qualified"):
        supervised.capture(tmp_path, "agy", output, "Matt", probe=True)
    assert not output.exists()


@pytest.mark.parametrize("decision", ["allow", "deny"])
def test_bidirectional_bridge_records_explicit_decisions_and_native_ids(tmp_path, monkeypatch, decision):
    import os
    import supervised

    fake = tmp_path / "fake_cli.py"
    fake.write_text('''import json, sys
def send(x):
    print(json.dumps(x), flush=True)
assert json.loads(input())["request_id"] == "cogin-init"
send({"type":"control_response","response":{"request_id":"cogin-init","subtype":"success"}})
assert json.loads(input())["type"] == "user"
send({"type":"system","subtype":"init","permissionMode":"default","model":"test-model"})
send({"type":"control_request","request_id":"approval-1","request":{"subtype":"can_use_tool","tool_name":"Write","input":{"file_path":"app.py","content":"test"}}})
response = json.loads(input())
assert response["response"]["request_id"] == "approval-1"
send({"type":"result","subtype":"success","is_error":False})
''')
    monkeypatch.setattr(supervised, "console_decision", lambda request, timeout: decision)
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    result = supervised.bridge("claude", [sys.executable, str(fake)], dict(os.environ), tmp_path,
                               "test prompt", artifacts, {"model": "test-model"}, operator="test operator", timeout=5)
    assert result["capture_complete"] and result["interruptions"] == 1
    assert result["approved"] == (decision == "allow")
    assert result["denied"] == (decision == "deny")
    sent = [json.loads(line) for line in (artifacts / "stdin.jsonl").read_text().splitlines()]
    assert sent[-1]["response"]["response"]["behavior"] == decision


def test_unknown_server_request_stops_without_any_grant(tmp_path):
    import os
    import supervised

    fake = tmp_path / "fake_cli.py"
    fake.write_text('''import json
input()
print(json.dumps({"type":"control_request","request_id":"unknown","request":{"subtype":"new_permission_kind"}}),flush=True)
assert input() == "never sent"
''')
    result = supervised.bridge("claude", [sys.executable, str(fake)], dict(os.environ), tmp_path,
                               "test", tmp_path, {"model": "test"}, operator="test", timeout=5)
    assert "Unsupported" in result["failure"]
    assert result["interruptions"] is None
    assert len((tmp_path / "stdin.jsonl").read_text().splitlines()) == 1


def test_codex_isolation_reuses_only_subscription_credentials(tmp_path, monkeypatch):
    import supervised

    source = tmp_path / "existing-home"
    source.mkdir()
    auth = {"tokens": {"access_token": "synthetic-test-token"}, "OPENAI_API_KEY": None}
    (source / "auth.json").write_text(json.dumps(auth))
    (source / "hooks.json").write_text("must not copy")
    (source / "config.toml").write_text("must not copy")
    monkeypatch.setenv("CODEX_HOME", str(source))
    isolated = tmp_path / "isolated"
    argv, env = supervised.launcher("codex", {"executable": "codex.exe"}, tmp_path / "worktree", isolated)
    assert env["CODEX_HOME"] == str(isolated)
    assert sorted(p.name for p in isolated.iterdir()) == ["auth.json"]
    assert 'approvals_reviewer="user"' in argv
    assert 'sandbox_mode="workspace-write"' in argv
    (source / "auth.json").write_text(json.dumps({"OPENAI_API_KEY": "synthetic-test-key"}))
    with pytest.raises(ValueError, match="subscription credentials"):
        supervised.launcher("codex", {"executable": "codex.exe"}, tmp_path, tmp_path / "other")


@pytest.mark.parametrize("mode, expected", [("qualification", None), ("supervised", 0)])
def test_supervised_report_distinguishes_probe_null_from_observed_zero(tmp_path, mode, expected):
    import harness
    import supervised

    root = tmp_path / "capture"
    artifacts = root / "results/subject"
    artifacts.mkdir(parents=True)
    manifest = {"mode": mode, "lane": "claude", "operator": "test operator"}
    harness.save(root / "capture-manifest.json", manifest)
    (root / "capture-source.py").write_text("# test fixture\n")
    names = ("stdout.jsonl", "stdin.jsonl", "stderr.txt", "approvals.jsonl", "changes.patch", "output.bundle")
    for name in names:
        (artifacts / name).write_bytes(b"")
    record = {**manifest, "capture_complete": True, "completed": True,
              "capture_manifest_sha256": harness.file_hash(root / "capture-manifest.json"),
              "capture_source_sha256": harness.file_hash(root / "capture-source.py"),
              "artifacts": {name: harness.file_hash(artifacts / name) for name in names}}
    harness.save(artifacts / "capture.json", record)
    (artifacts / "capture.sha256").write_text(harness.file_hash(artifacts / "capture.json"))
    output = tmp_path / "report"
    supervised.report([root], output)
    assert human_review.read(output / "report.json")["captures"][0]["interruptions"] == expected
    assert ("unmeasured" if expected is None else "| 0 | 0 | 0 |") in (output / "report.md").read_text()
    (artifacts / "stdout.jsonl").write_text("changed")
    with pytest.raises(ValueError, match="artifact changed"):
        supervised.report([root], tmp_path / "tampered-report")

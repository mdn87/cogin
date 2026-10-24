import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import harness


def test_pin_rejects_different_binary_before_launch(tmp_path):
    binary = tmp_path / "tool.exe"
    binary.write_bytes(b"changed")
    with pytest.raises(ValueError, match="binary hash"):
        harness.verify_binary({"executable": str(binary), "sha256": "0" * 64})


def test_diff_scoring_counts_new_files_and_renames_as_off_target():
    score = harness.score_numstat("5\t2\tapp.py\n3\t0\tnew.txt\n1\t1\told.py => moved.py\n")
    assert score == {"changed_lines": 12, "off_target_lines": 5, "off_target_files": ["new.txt", "old.py => moved.py"], "off_target": True}


def test_missing_terminal_event_is_incomplete():
    parsed = harness.parse_events("codex", '{"type":"thread.started","thread_id":"secret"}\n')
    assert not parsed["completed"]
    assert parsed["assistant_events"] == 0


def test_tool_events_are_distinct_from_assistant_turns():
    events = [
        {"type": "item.completed", "item": {"type": "command_execution", "command": "python -m unittest -q", "exit_code": 0}},
        {"type": "item.completed", "item": {"type": "agent_message", "text": "Done"}},
        {"type": "turn.completed", "usage": {}},
    ]
    result = harness.parse_events("codex", "\n".join(json.dumps(e) for e in events))
    assert result["completed"] and result["tool_events"] == 1
    assert result["assistant_events"] == 1


def test_repeatability_never_compares_invalid_runs():
    run = {"valid": False, "assistant_events": 1, "off_target": False}
    assert harness.repeatability([run, run])["eligible"] is False


def test_repeatability_uses_prefrozen_absolute_and_relative_tolerance():
    good = {"valid": True, "off_target": False}
    assert harness.repeatability([{**good, "assistant_events": 10}, {**good, "assistant_events": 12}])["eligible"]
    assert not harness.repeatability([{**good, "assistant_events": 10}, {**good, "assistant_events": 16}])["eligible"]


def test_agy_denial_cannot_be_counted_as_completed_tool_work():
    events = [
        {"event": "step_update", "step_update": {"step_index": 0, "state": "DONE", "step_type": "user_input"}},
        {"event": "step_update", "step_update": {"step_index": 1, "state": "ERROR", "step_type": "tool",
          "tool_info": {"error": {"message": "user denied permission"}}}},
        {"event": "result", "result": {"status": "SUCCESS", "num_turns": 1}},
    ]
    parsed = harness.parse_events("agy", "\n".join(json.dumps(e) for e in events))
    assert parsed["tool_events"] == 0
    assert parsed["permission_denials"] == 1
    assert harness.protocol_errors("agy", {"model": "model"}, parsed, 0, False, "")


def test_codex_policy_block_is_invalid_even_with_success_terminal_event():
    parsed = harness.parse_events("codex", '{"type":"turn.completed"}\n')
    errors = harness.protocol_errors("codex", {"model": "model"}, parsed, 0, False,
                                     "rejected: blocked by policy")
    assert "permission denial" in errors
    assert "no completed tool executions" in errors


def test_denied_lane_cannot_launch_another_trial_in_same_batch(tmp_path, monkeypatch):
    path = tmp_path / "results/codex-1/result.json"
    path.parent.mkdir(parents=True)
    path.write_text("{}")
    monkeypatch.setattr(harness, "load_manifest", lambda root: {"lanes": {"codex": {}}})
    monkeypatch.setattr(harness, "verify_binary", lambda pin: None)
    monkeypatch.setattr(harness, "assess_record", lambda *args: {"protocol_errors": ["permission denial"]})
    monkeypatch.setattr(harness, "git", lambda *args, **kwargs: pytest.fail("must stop before provisioning or execution"))
    with pytest.raises(ValueError, match="separately approved"):
        harness.run_one(tmp_path, "codex", 2)


def test_non_object_json_is_a_parse_error_not_a_crash():
    result = harness.parse_events("codex", '[]\n{"type":"turn.completed"}\n')
    assert result["parse_errors"] == 1


def test_archive_names_are_scoped_to_batch_and_preserve_older_tags(tmp_path):
    seed = tmp_path / "batch-two/seed"
    seed.mkdir(parents=True)
    artifacts = seed.parent / "artifacts"
    artifacts.mkdir()
    harness.git(seed, "init", "-b", "main")
    (seed / "app.py").write_text("before\n")
    harness.git(seed, "add", "app.py")
    harness.git(seed, "commit", "-m", "test: seed")
    old = harness.git(seed, "rev-parse", "HEAD").stdout.strip()
    harness.git(seed, "tag", "archive/codex-1", old)
    (seed / "app.py").write_text("after\n")
    revision = harness.archive(seed, seed, artifacts, "codex-1")
    assert harness.git(seed, "rev-parse", "archive/codex-1").stdout.strip() == old
    assert harness.git(seed, "rev-parse", "archive/batch-two/codex-1").stdout.strip() == revision
    assert (artifacts / "output.bundle").is_file()


def test_agy_permissions_use_literal_prefixes_and_workspace_paths(tmp_path):
    worktree = tmp_path / "worktree"
    home = tmp_path / "home"
    pin = {"executable": "agy.exe", "model": "model", "effort": "medium",
           "permission_syntax": "literal-prefix-v1", "inspection_commands": ["command(Get-Content)"],
           "exact_commands": ["command(python -m unittest -q)"]}
    argv, env = harness.invocation("agy", pin, worktree, home)
    policy = json.loads((home / ".gemini/antigravity-cli/settings.json").read_text())["permissions"]
    assert "command(python)" in policy["allow"]
    assert "command(python -m unittest -q)" in policy["allow"]
    assert "command(git diff)" in policy["allow"]
    assert "command(git status)" in policy["allow"]
    assert f"write_file({worktree.as_posix()})" in policy["allow"]
    assert "read_file(*)" not in policy["allow"]
    assert all("*" not in rule for rule in policy["allow"])
    assert policy["deny"] == ["read_url(*)", "execute_url(*)", "mcp(*)"]
    assert "--sandbox" in argv
    assert env["USERPROFILE"] == str(home)


def test_reading_a_command_is_not_running_it():
    content = "python -m unittest -q; python browser_check.py"
    claude = {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Write", "input": {"content": content}}]}}
    agy = {"event": "step_update", "step_update": {"step_index": 1, "state": "DONE", "step_type": "tool",
           "tool_name": "view_file", "tool_info": {"parameters": {"text": content}}}}
    for lane, event in (("claude", claude), ("agy", agy)):
        parsed = harness.parse_events(lane, json.dumps(event))
        assert not parsed["test_command_observed"]
        assert not parsed["browser_command_observed"]


def test_windows_rules_allow_argument_variations_without_granting_all_commands(tmp_path):
    pin = {"executable": "agy.exe", "model": "model", "effort": "medium",
           "permission_syntax": "windows-command-regex-v1"}
    argv, _ = harness.invocation("agy", pin, tmp_path / "wt", tmp_path / "home")
    policy = json.loads((tmp_path / "home/.gemini/antigravity-cli/settings.json").read_text())["permissions"]
    assert "command(regex:python .*)" in policy["allow"]
    assert "command(regex:git diff .*)" in policy["allow"]
    assert "command(regex:git status .*)" in policy["allow"]
    assert "command(*)" not in policy["allow"]
    assert "command(regex:git .*)" not in policy["allow"]
    assert "--sandbox" in argv


def test_git_metadata_grant_is_read_only_and_path_inspection_is_scoped(tmp_path):
    root = tmp_path / "batch"
    pin = {"executable": "agy.exe", "model": "model", "effort": "medium",
           "permission_syntax": "windows-command-regex-v1", "read_seed_git_metadata": True}
    harness.invocation("agy", pin, root / "worktrees/agy-1", root / "home")
    allows = json.loads((root / "home/.gemini/antigravity-cli/settings.json").read_text())["permissions"]["allow"]
    metadata = root / "seed/.git"
    assert f"read_file({metadata.as_posix()})" in allows
    assert f"write_file({metadata.as_posix()})" not in allows
    inspections = [rule for rule in allows if "Test-Path" in rule]
    assert inspections
    assert all(metadata.as_posix() in rule.replace('\\', '/') for rule in inspections)
    assert "command(Test-Path)" not in allows


def test_cmd_directory_listing_grant_matches_only_the_approved_command(tmp_path):
    import re

    pin = {"executable": "agy.exe", "model": "model", "effort": "medium",
           "permission_syntax": "windows-command-regex-v1", "cmd_directory_listing": True}
    harness.invocation("agy", pin, tmp_path / "wt", tmp_path / "home")
    allows = json.loads((tmp_path / "home/.gemini/antigravity-cli/settings.json").read_text())["permissions"]["allow"]
    rules = [rule[len("command(regex:"):-1] for rule in allows if rule.startswith("command(regex:")]
    assert any(re.search(rule, "cmd /c dir") for rule in rules)
    for forbidden in ("cmd /c dir C:/", "cmd /c dir & whoami", "cmd /c del app.py"):
        assert not any(re.search(rule, forbidden) for rule in rules)


def test_agy_pinned_shell_precedes_inherited_path_only_in_child(tmp_path, monkeypatch):
    import os

    monkeypatch.setenv("PATH", "inherited-path")
    shell = tmp_path / "system-powershell/pwsh.exe"
    pin = {"executable": "agy.exe", "model": "model", "effort": "medium",
           "shell": {"executable": str(shell)}}
    argv, env = harness.invocation("agy", pin, tmp_path / "wt", tmp_path / "home")
    assert env["PATH"] == str(shell.parent) + os.pathsep + "inherited-path"
    assert os.environ["PATH"] == "inherited-path"
    assert "--sandbox" in argv


def test_changed_pinned_shell_is_rejected_before_trial(tmp_path, monkeypatch):
    from types import SimpleNamespace

    binary = tmp_path / "agy.exe"
    binary.write_bytes(b"pinned")
    shell = tmp_path / "pwsh.exe"
    shell.write_bytes(b"changed")
    monkeypatch.setattr(harness, "command", lambda *args, **kwargs: SimpleNamespace(stdout="version"))
    pin = {"executable": str(binary), "sha256": harness.file_hash(binary), "version": "version",
           "shell": {"executable": str(shell), "sha256": "0" * 64, "version": "shell-version"}}
    with pytest.raises(ValueError, match="binary hash"):
        harness.verify_binary(pin)


def test_fixture_search_rule_rejects_other_paths_patterns_and_chains():
    import re

    pattern = harness.AGY_FIXTURE_SEARCH[len("command(regex:"):-1]
    assert re.search(pattern, 'Select-String -Path * -Pattern "status-filter"')
    for forbidden in ('Select-String -Path C:/* -Pattern "status-filter"',
                      'Select-String -Path * -Pattern "secret"',
                      'Select-String -Path * -Pattern "status-filter"; whoami'):
        assert not re.search(pattern, forbidden)


def passing_patch():
    return {"verification": {"tests_passed": True, "browser_passed": True},
            "test_command_observed": True, "browser_command_observed": False,
            "subject_browser_artifact": False, "off_target": False,
            "changed_files": ["app.py", "test_app.py"]}


def test_v2_accepts_independently_verified_patch_without_subject_browser():
    assert harness.task_passed({"protocol_version": 2}, passing_patch())
    assert not harness.task_passed({}, passing_patch())
    assert harness.task_passed({}, {**passing_patch(), "browser_command_observed": True,
                                   "subject_browser_artifact": True})


@pytest.mark.parametrize("change", [
    {"verification": {"tests_passed": True, "browser_passed": False}},
    {"verification": {"tests_passed": False, "browser_passed": True}},
    {"test_command_observed": False},
    {"off_target": True},
    {"changed_files": ["app.py"]},
])
def test_v2_still_requires_browser_acceptance_tests_and_scope(change):
    assert not harness.task_passed({"protocol_version": 2}, {**passing_patch(), **change})


def test_report_rejects_mixed_protocols_even_if_task_hashes_match(tmp_path, monkeypatch):
    current = {"protocol_version": 2, "seed_commit": "seed", "prompt_sha256": "prompt", "fixture_hashes": {}}
    old = {**current, "protocol_version": 1}
    monkeypatch.setattr(harness, "load_manifest", lambda root: current if root.name == "new" else old)
    with pytest.raises(ValueError, match="protocol"):
        harness.report(tmp_path / "new", [tmp_path / "old"])


def test_unknown_protocol_is_rejected():
    with pytest.raises(ValueError, match="protocol"):
        harness.protocol_version({"protocol_version": 99})


def test_windows_v2_rule_matches_multiline_python_without_other_command_prefixes(tmp_path):
    import re

    pin = {"executable": "agy.exe", "model": "model", "effort": "medium",
           "permission_syntax": "windows-command-regex-v2"}
    argv, _ = harness.invocation("agy", pin, tmp_path / "wt", tmp_path / "home")
    allows = json.loads((tmp_path / "home/.gemini/antigravity-cli/settings.json").read_text())["permissions"]["allow"]
    rules = [rule[len("command(regex:"):-1] for rule in allows if rule.startswith("command(regex:")]
    multiline = 'python -c "import io\nprint(io.StringIO())"'
    assert any(re.search(rule, multiline) for rule in rules)
    for forbidden in ('powershell -Command whoami', 'cmd /c ' + multiline, 'echo python hello'):
        assert not any(re.search(rule, forbidden) for rule in rules)
    assert "read_file(*)" not in allows
    assert "--sandbox" in argv


@pytest.mark.parametrize("command", [
    'Get-Content browser_check.py; Get-Content test_unittest.py',
    '"C:/Program Files/PowerShell/7/pwsh.exe" -Command "rg --files -g browser_check.py -g unittest"',
    'echo "python browser_check.py; unittest"',
])
def test_codex_file_search_or_echo_is_not_test_or_browser_execution(command):
    event = {"type": "item.completed", "item": {"type": "command_execution", "command": command}}
    parsed = harness.parse_events("codex", json.dumps(event))
    assert not parsed["browser_command_observed"]
    assert not parsed["test_command_observed"]


@pytest.mark.parametrize("command", [
    'python -m unittest -q; python browser_check.py --feature',
    'cd "C:/fixture" && python -m unittest -q && python browser_check.py --feature',
    '"C:/Program Files/PowerShell/7/pwsh.exe" -Command \'python -m unittest -q; python browser_check.py --feature\'',
])
def test_observes_actual_python_commands_inside_shell_wrappers(command):
    event = {"type": "item.completed", "item": {"type": "command_execution", "command": command}}
    parsed = harness.parse_events("codex", json.dumps(event))
    assert parsed["browser_command_observed"]
    assert parsed["test_command_observed"]

"""Pinned subscription-CLI repo-task experiment (separate from Wave 1)."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time


HERE = Path(__file__).resolve().parent
MODELS = {"claude": "claude-sonnet-5", "codex": "gpt-6.1-sol", "agy": "gemini-3.8-flash-medium"}
INTENDED = {"app.py", "test_app.py"}
TIMEOUT = 600
AGY_TASK_COMMANDS = [
    "command(python -m unittest -q)",
    "command(python browser_check.py --feature --screenshot browser.png)",
]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def file_hash(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def environment():
    env = dict(os.environ)
    for key in tuple(env):
        if key.upper() in {
            "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY",
            "OPENAI_BASE_URL", "ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN",
            "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY",
            "PYTHONPATH", "CLAUDECODE",
        }:
            env.pop(key, None)
    env.update(AGY_CLI_DISABLE_AUTO_UPDATE="1", DISABLE_AUTOUPDATER="1",
               PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    if os.name == "nt":
        env["PLAYWRIGHT_BROWSERS_PATH"] = str(Path(os.environ["LOCALAPPDATA"]) / "ms-playwright")
    return env


def command(args, cwd=None, *, env=None, timeout=60, check=True):
    return subprocess.run(args, cwd=cwd, env=env, capture_output=True, timeout=timeout,
                          text=True, encoding="utf-8", errors="replace", check=check)


def git(root, *args, check=True):
    return command(["git", "-c", "core.autocrlf=false", "-c", "core.hooksPath=" + str(root / ".no-hooks"),
                    "-c", "user.name=Cogin experiment", "-c", "user.email=cogin@localhost", *args], root, check=check)


def verify_binary(pin):
    if file_hash(pin["executable"]) != pin["sha256"]:
        raise ValueError("Pinned binary hash changed; prepare a separate batch, never repin a running one")
    version = command([pin["executable"], "--version"], env=environment()).stdout.strip()
    if version != pin["version"]:
        raise ValueError("Pinned CLI version changed")


def score_numstat(text):
    total, off, files = 0, 0, []
    for row in text.splitlines():
        added, removed, path = row.split("\t", 2)
        count = int(added) + int(removed) if added != "-" else 0
        total += count
        if path not in INTENDED:
            off += count
            files.append(path)
    return {"changed_lines": total, "off_target_lines": off, "off_target_files": files, "off_target": bool(files)}


def parse_events(lane, text):
    result = {"completed": False, "assistant_events": 0, "tool_events": 0,
              "native_turns": None, "permission_mode": None, "reported_model": None,
              "advertised_tools": None, "parse_errors": 0, "permission_denials": 0,
              "browser_command_observed": False, "test_command_observed": False}
    done_steps = set()
    error_steps = set()
    tool_inputs = {}
    for line in text.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            result["parse_errors"] += 1
            continue
        if not isinstance(event, dict):
            result["parse_errors"] += 1
            continue
        kind = event.get("type", event.get("event"))
        if lane == "codex":
            if kind == "turn.completed":
                result["completed"] = True
            if kind in {"turn.failed", "error"}:
                result["completed"] = False
            item = event.get("item", {})
            if kind == "item.completed":
                if item.get("type") == "agent_message":
                    result["assistant_events"] += 1
                elif item.get("type") in {"command_execution", "mcp_tool_call", "web_search", "file_change"}:
                    result["tool_events"] += 1
                    result["browser_command_observed"] |= "browser_check.py" in item.get("command", "")
                    result["test_command_observed"] |= "unittest" in item.get("command", "")
        elif lane == "claude":
            if kind == "system" and event.get("subtype") == "init":
                result.update(permission_mode=event.get("permissionMode"), reported_model=event.get("model"),
                              advertised_tools=event.get("tools"))
            elif kind == "assistant":
                result["assistant_events"] += 1
                for item in event.get("message", {}).get("content", []):
                    if item.get("type") == "tool_use":
                        result["tool_events"] += 1
                        if item.get("name") == "Bash":
                            cmd = item.get("input", {}).get("command", "")
                            result["browser_command_observed"] |= "browser_check.py" in cmd
                            result["test_command_observed"] |= "unittest" in cmd
            elif kind == "result":
                result["completed"] = event.get("subtype") == "success" and not event.get("is_error", False)
                result["native_turns"] = event.get("num_turns")
                result["permission_denials"] = len(event.get("permission_denials", []))
        else:
            if kind == "init":
                init = event.get("init", {})
                result.update(permission_mode=init.get("permission_mode"), reported_model=init.get("model"),
                              advertised_tools=init.get("tools"))
            elif kind == "step_update":
                step = event.get("step_update", {})
                key = step.get("step_index")
                if step.get("tool_name") == "run_command" and step.get("tool_info", {}).get("parameters"):
                    tool_inputs[key] = step["tool_info"]["parameters"].get("CommandLine", "")
                if step.get("state") == "ERROR" and key not in error_steps:
                    error_steps.add(key)
                    message = str(step.get("tool_info", {}).get("error", {})).lower()
                    if "permission" in message or "denied" in message:
                        result["permission_denials"] += 1
                if step.get("state") == "DONE" and key not in done_steps:
                    done_steps.add(key)
                    if step.get("step_type") == "agent_response":
                        result["assistant_events"] += 1
                    elif step.get("step_type") == "tool":
                        result["tool_events"] += 1
                        tool_text = tool_inputs.get(key, "")
                        result["browser_command_observed"] |= "browser_check.py" in tool_text
                        result["test_command_observed"] |= "unittest" in tool_text
            elif kind == "result":
                terminal = event.get("result", {})
                result["completed"] = terminal.get("status") == "SUCCESS"
                result["native_turns"] = terminal.get("num_turns")
    return result


def protocol_errors(lane, pin, parsed, returncode, timeout, stderr):
    errors = []
    if returncode != 0 or timeout or not parsed["completed"] or parsed["parse_errors"]:
        errors.append("process, timeout, or incomplete event stream")
    if not parsed["tool_events"]:
        errors.append("no completed tool executions")
    if parsed["permission_denials"] or "blocked by policy" in stderr.lower() or "auto-denied" in stderr.lower():
        errors.append("permission denial")
    if lane == "agy" and parsed["permission_mode"] not in {"request-review", "accept-edits"}:
        errors.append("unexpected permission mode")
    if lane == "claude" and parsed["permission_mode"] != "acceptEdits":
        errors.append("unexpected permission mode")
    if parsed["reported_model"] is not None and parsed["reported_model"] != pin["model"]:
        errors.append("reported model differs from the pinned selector")
    if "timeout" in stderr.lower() or "timed out" in stderr.lower():
        errors.append("CLI reported timeout")
    return errors


def repeatability(runs):
    if len(runs) != 2 or not all(run["valid"] for run in runs):
        return {"eligible": False, "reason": "requires two protocol-valid runs"}
    turns = [run["assistant_events"] for run in runs]
    allowed = max(2, math.ceil(max(turns) * 0.25))
    stable = abs(turns[0] - turns[1]) <= allowed and runs[0]["off_target"] == runs[1]["off_target"]
    return {"eligible": stable, "assistant_event_counts": turns, "allowed_difference": allowed,
            "reason": "within predeclared tolerance" if stable else "repeatability gate failed"}


def prepare(args):
    root = args.root.resolve()
    if root.exists():
        raise ValueError("Batch directory already exists; do not replace immutable experiment inputs")
    root.mkdir(parents=True)
    seed = root / "seed"
    shutil.copytree(HERE / "fixture", seed, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "browser.png"))
    git(seed, "init", "-b", "main")
    git(seed, "add", "--all")
    git(seed, "commit", "-m", "test: pin task-board seed")
    seed_commit = git(seed, "rev-parse", "HEAD").stdout.strip()
    base_tests = command([sys.executable, "-m", "unittest", "-q"], seed)
    browser = command([sys.executable, "browser_check.py"], seed, env=environment())
    pins = {}
    for lane in MODELS:
        path = Path(getattr(args, lane)).resolve(strict=True)
        pins[lane] = {"executable": str(path), "sha256": file_hash(path),
                      "version": command([str(path), "--version"], env=environment()).stdout.strip(),
                      "model": MODELS[lane], "effort": "medium"}
        if lane == "agy":
            pins[lane]["permission_syntax"] = "windows-command-regex-v1"
            pins[lane]["exact_commands"] = list(AGY_TASK_COMMANDS)
        if lane == "codex" and args.windows_sandbox:
            pins[lane]["windows_sandbox"] = args.windows_sandbox
        verify_binary(pins[lane])
    prompt = (HERE / "task.txt").read_bytes().replace(b"\r\n", b"\n")
    (root / "task.txt").write_bytes(prompt)
    manifest = {"schema_version": 1, "created_at": datetime.now(timezone.utc).isoformat(),
                "seed_commit": seed_commit, "prompt_sha256": digest(prompt), "lanes": pins,
                "mode": "unattended", "repeats": 2, "timeout_seconds": TIMEOUT,
                "repeatability": {"absolute_assistant_events": 2, "relative_assistant_events": 0.25},
                "intended_files": sorted(INTENDED), "python": sys.version,
                "fixture_hashes": {p.name: file_hash(p) for p in sorted((HERE / "fixture").iterdir()) if p.is_file()},
                "browser_preflight": json.loads(browser.stdout), "seed_tests_exit_code": base_tests.returncode,
                "limitations": ["CLI configurations, not isolated model capability.",
                                "No supervised interruption or blind cleanup score.",
                                "Assistant-event semantics differ across CLIs; compare within a lane first."]}
    save(root / "manifest.json", manifest)
    (root / "manifest.sha256").write_text(file_hash(root / "manifest.json"))
    print(json.dumps({"batch": str(root), "seed_commit": seed_commit,
                      "versions": {k: v["version"] for k, v in pins.items()}}), flush=True)


def load_manifest(root):
    if file_hash(root / "manifest.json") != (root / "manifest.sha256").read_text().strip():
        raise ValueError("Manifest changed")
    manifest = json.loads((root / "manifest.json").read_text())
    if file_hash(root / "task.txt") != manifest["prompt_sha256"]:
        raise ValueError("Task prompt changed")
    for name, expected in manifest["fixture_hashes"].items():
        if file_hash(HERE / "fixture" / name) != expected:
            raise ValueError("Trusted fixture/acceptance helper changed")
    return manifest


def prepare_corrected(args):
    source = args.source.resolve()
    manifest = load_manifest(source)
    root = args.root.resolve()
    if root.exists():
        raise ValueError("Corrected batch directory already exists")
    for pin in manifest["lanes"].values():
        verify_binary(pin)
    root.mkdir(parents=True)
    command(["git", "clone", "--no-local", "--single-branch", "--no-tags", "--branch", "main", str(source / "seed"), str(root / "seed")])
    if git(root / "seed", "rev-parse", "HEAD").stdout.strip() != manifest["seed_commit"]:
        raise ValueError("Corrected batch seed differs")
    shutil.copyfile(source / "task.txt", root / "task.txt")
    manifest["created_at"] = datetime.now(timezone.utc).isoformat()
    manifest["parent_manifest_sha256"] = file_hash(source / "manifest.json")
    manifest["permission_corrections"] = {
        "authorization": args.authorization,
        "codex": "Explicit existing Windows unelevated implementation; workspace-write retained.",
        "agy": "Allow Get-ChildItem and Get-Content for fixture inspection, including their verified dir/ls/cat/type aliases; sandbox and existing denies retained.",
    }
    manifest["lanes"]["codex"]["windows_sandbox"] = "unelevated"
    manifest["lanes"]["agy"]["permission_syntax"] = "windows-command-regex-v1"
    # Windows commands may require full-line matches even when their command
    # prefix is granted. These are the exact commands in the frozen task.
    manifest["lanes"]["agy"]["exact_commands"] = list(AGY_TASK_COMMANDS)
    manifest["lanes"]["agy"]["inspection_commands"] = [
        "command(Get-ChildItem)", "command(Get-Content)", "command(dir)", "command(ls)",
        *[f"command(regex:{name} .*)" for name in ("Get-ChildItem", "Get-Content", "dir", "ls")],
        *[f"command({alias} {name})" for alias in ("cat", "type")
          for name in ("app.py", "test_app.py", "browser_check.py")],
    ]
    if args.allow_git_log:
        manifest["lanes"]["agy"]["inspection_commands"].append("command(git log)")
        manifest["lanes"]["agy"]["inspection_commands"].append("command(regex:git log .*)")
        manifest["lanes"]["agy"]["exact_commands"].append("command(git log -p -2)")
        manifest["permission_corrections"]["agy"] += " Read-only git log separately approved for the fixture repository."
    if args.allow_git_metadata:
        manifest["lanes"]["agy"]["read_seed_git_metadata"] = True
        manifest["permission_corrections"]["agy"] += " Read-only seed Git metadata and exact Test-Path inspection separately approved."
    save(root / "manifest.json", manifest)
    (root / "manifest.sha256").write_text(file_hash(root / "manifest.json"))
    print(json.dumps({"corrected_batch": str(root), "seed_commit": manifest["seed_commit"]}), flush=True)


def invocation(lane, pin, worktree, home):
    env = environment()
    executable = pin["executable"]
    if lane == "codex":
        argv = [executable, "exec", "--json", "--ephemeral", "--ignore-user-config",
                "-C", str(worktree), "-s", "workspace-write", "-m", pin["model"],
                "-c", 'model_reasoning_effort="medium"', "-"]
        if pin.get("windows_sandbox"):
            argv[-1:-1] = ["-c", "windows.sandbox=" + json.dumps(pin["windows_sandbox"])]
    elif lane == "claude":
        argv = [executable, "-p", "--output-format", "stream-json", "--verbose",
                "--safe-mode", "--no-session-persistence", "--no-chrome",
                "--strict-mcp-config", "--model", pin["model"], "--effort", pin["effort"],
                "--permission-mode", "acceptEdits", "--tools", "Read,Edit,Write,Bash,Glob,Grep",
                "--allowedTools", "Bash(python *),Bash(git diff*),Bash(git status*)"]
    else:
        env["USERPROFILE"] = env["HOME"] = str(home)
        permission_file = home / ".gemini/antigravity-cli/settings.json"
        # Keep historical manifests reproducible; new manifests pin corrected
        # literal-prefix semantics documented by the CLI permission engine.
        if pin.get("permission_syntax") in {"literal-prefix-v1", "windows-command-regex-v1"}:
            allows = [f"read_file({worktree.as_posix()})", f"write_file({worktree.as_posix()})",
                      "command(python)", "command(git diff)", "command(git status)"]
            if pin["permission_syntax"] == "windows-command-regex-v1":
                allows += ["command(regex:python .*)", "command(regex:git diff .*)", "command(regex:git status .*)"]
        else:
            allows = ["read_file(*)", f"write_file({worktree.as_posix()}/**)",
                      "command(python *)", "command(git diff*)", "command(git status*)"]
        if pin.get("read_seed_git_metadata"):
            git_dir = worktree.parent.parent / "seed" / ".git"
            allows.append(f"read_file({git_dir.as_posix()})")
            for target in (git_dir, git_dir / "worktrees" / worktree.name):
                for spelling in {str(target), target.as_posix()}:
                    for quote in ('"', "'", ""):
                        allows.append(f"command(Test-Path {quote}{spelling}{quote})")
        save(permission_file, {"permissions": {
            "allow": [*allows, *pin.get("inspection_commands", []), *pin.get("exact_commands", [])],
            "deny": ["read_url(*)", "execute_url(*)", "mcp(*)"],
        }})
        argv = [executable, "--print=", "--input-format", "stream-json", "--output-format", "stream-json",
                "--model", pin["model"], "--effort", pin["effort"], "--mode", "accept-edits",
                "--sandbox", "--print-timeout", str(TIMEOUT) + "s"]
    return argv, env


def execute(argv, stdin, cwd, env, artifacts):
    start = time.monotonic()
    timed_out = False
    with (artifacts / "stdout.jsonl").open("wb") as stdout, (artifacts / "stderr.txt").open("wb") as stderr:
        process = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=stdout, stderr=stderr, cwd=cwd, env=env)
        try:
            process.communicate(stdin.encode("utf-8"), timeout=TIMEOUT)
        except subprocess.TimeoutExpired:
            timed_out = True
            if os.name == "nt":
                command(["taskkill", "/PID", str(process.pid), "/T", "/F"], check=False)
            else:
                process.kill()
            process.communicate(timeout=30)
    return process.returncode, round(time.monotonic() - start, 3), timed_out


def archive(seed, worktree, artifacts, run_id):
    git(worktree, "add", "--all")
    git(worktree, "commit", "--allow-empty", "-m", f"wip: archive {run_id} experiment output")
    revision = git(worktree, "rev-parse", "HEAD").stdout.strip()
    tag = "archive/" + seed.parent.name + "/" + run_id
    git(seed, "tag", tag, revision)
    git(seed, "bundle", "create", str(artifacts / "output.bundle"), "refs/tags/" + tag)
    git(seed, "bundle", "verify", str(artifacts / "output.bundle"))
    return revision


def verify_patch(root, manifest, patch, artifacts):
    seed = root / "seed"
    checkout = root / "worktrees" / (artifacts.name + "-verify")
    git(seed, "worktree", "add", "--detach", str(checkout), manifest["seed_commit"])
    applied = git(checkout, "apply", "--binary", str(patch), check=False) if patch.stat().st_size else None
    result = {"patch_applied": applied is None or applied.returncode == 0}
    if result["patch_applied"]:
        tests = command([sys.executable, "-m", "unittest", "-q"], checkout, env=environment(), check=False, timeout=60)
        (artifacts / "fresh-tests.txt").write_text(tests.stdout + tests.stderr, encoding="utf-8")
        helper = "import runpy,sys; sys.path.insert(0,sys.argv[1]); sys.argv=[sys.argv[2],'--feature','--screenshot',sys.argv[3]]; runpy.run_path(sys.argv[0],run_name='__main__')"
        browser = command([sys.executable, "-c", helper, str(checkout), str(HERE / "fixture/browser_check.py"),
                           str(artifacts / "fresh-browser.png")], checkout, env=environment(), check=False, timeout=60)
        (artifacts / "fresh-browser.txt").write_text(browser.stdout + browser.stderr, encoding="utf-8")
        result.update(tests_passed=tests.returncode == 0, browser_passed=browser.returncode == 0)
    else:
        (artifacts / "apply-error.txt").write_text(applied.stderr, encoding="utf-8")
    archive(seed, checkout, artifacts / "verification", artifacts.name + "-verification")
    git(seed, "worktree", "remove", str(checkout))
    return result


def run_one(root, lane, repeat):
    manifest = load_manifest(root)
    pin = manifest["lanes"][lane]
    verify_binary(pin)
    for previous in (root / "results").glob(lane + "-*/result.json"):
        record = assess_record(previous, manifest)
        if "permission denial" in record["protocol_errors"]:
            raise ValueError("Lane has a recorded permission denial; a separately approved corrected batch is required")
    run_id = f"{lane}-{repeat}"
    artifacts = root / "results" / run_id
    if artifacts.exists():
        raise ValueError("Run ID already exists; never overwrite a trial")
    artifacts.mkdir(parents=True)
    (artifacts / "verification").mkdir()
    worktree = root / "worktrees" / run_id
    seed = root / "seed"
    git(seed, "worktree", "add", "-b", "trial/" + run_id, str(worktree), manifest["seed_commit"])
    argv, env = invocation(lane, pin, worktree, root / "homes" / run_id)
    prompt = (root / "task.txt").read_text(encoding="utf-8")
    stdin = json.dumps({"event": "user", "message": {"content": prompt}}) + "\n" if lane == "agy" else prompt
    policy = {"requested_mode": "workspace-write" if lane == "codex" else "acceptEdits" if lane == "claude" else "accept-edits"}
    if lane == "agy":
        policy["permissions"] = json.loads((root / "homes" / run_id / ".gemini/antigravity-cli/settings.json").read_text())["permissions"]
    save(artifacts / "invocation.json", {"argv": argv, "cwd": str(worktree), "policy": policy,
         "manifest_sha256": file_hash(root / "manifest.json"), "prompt_sha256": digest(prompt.encode()),
         "harness_sha256": file_hash(Path(__file__))})
    shutil.copyfile(Path(__file__), artifacts / "harness.py")
    print(f"Starting {run_id}: {pin['version']} / {pin['model']} / medium", flush=True)
    returncode, elapsed, timeout = execute(argv, stdin, worktree, env, artifacts)
    save(artifacts / "process.json", {"returncode": returncode, "wall_seconds": elapsed, "timed_out": timeout})
    return finalize_run(root, lane, repeat)


def finalize_run(root, lane, repeat):
    manifest = load_manifest(root)
    pin = manifest["lanes"][lane]
    run_id = f"{lane}-{repeat}"
    artifacts = root / "results" / run_id
    if (artifacts / "result.json").exists():
        raise ValueError("Trial is already finalized")
    process = json.loads((artifacts / "process.json").read_text())
    returncode, elapsed, timeout = process["returncode"], process["wall_seconds"], process["timed_out"]
    worktree = root / "worktrees" / run_id
    seed = root / "seed"
    parsed = parse_events(lane, (artifacts / "stdout.jsonl").read_text(encoding="utf-8", errors="replace"))
    verify_binary(pin)
    revision = archive(seed, worktree, artifacts, run_id)
    patch = artifacts / "changes.patch"
    patch.write_bytes(subprocess.check_output(["git", "diff", "--binary", manifest["seed_commit"], revision], cwd=seed))
    score = score_numstat(git(seed, "diff", "--numstat", manifest["seed_commit"], revision).stdout)
    if (worktree / "browser.png").exists():
        shutil.copyfile(worktree / "browser.png", artifacts / "subject-browser.png")
    verification = verify_patch(root, manifest, patch, artifacts)
    git(seed, "worktree", "remove", str(worktree))
    stderr = (artifacts / "stderr.txt").read_text(encoding="utf-8", errors="replace")
    errors = protocol_errors(lane, pin, parsed, returncode, timeout, stderr)
    result = {"run_id": run_id, "lane": lane, "repeat": repeat, "model": pin["model"],
              "effort": "medium", "version": pin["version"], "binary_sha256": pin["sha256"],
              "wall_seconds": elapsed, "returncode": returncode, "timed_out": timeout,
              "valid": not errors, "protocol_errors": errors, **parsed, **score,
              "verification": verification, "snapshot_commit": revision, "patch_sha256": file_hash(patch),
              "subject_browser_artifact": (artifacts / "subject-browser.png").is_file(),
              "process_recovery_note": process.get("recovery_note"),
              "interruptions": None, "human_cleanup_lines": None,
              "task_passed": verification.get("tests_passed", False) and verification.get("browser_passed", False)
                             and parsed["test_command_observed"] and parsed["browser_command_observed"]
                             and (artifacts / "subject-browser.png").is_file()
                             and not score["off_target"] and "test_app.py" in git(seed, "diff", "--name-only", manifest["seed_commit"], revision).stdout.splitlines()}
    save(artifacts / "result.json", result)
    print(json.dumps({k: result[k] for k in ("run_id", "valid", "task_passed", "wall_seconds", "assistant_events", "protocol_errors")}), flush=True)
    return result


def assess_record(path, manifest):
    run = json.loads(path.read_text())
    parsed = parse_events(run["lane"], path.with_name("stdout.jsonl").read_text(encoding="utf-8", errors="replace"))
    errors = protocol_errors(run["lane"], manifest["lanes"][run["lane"]], parsed,
                             run["returncode"], run["timed_out"], path.with_name("stderr.txt").read_text(encoding="utf-8", errors="replace"))
    run.update(parsed)
    run.update(valid=not errors, protocol_errors=errors)
    run["task_passed"] = (run["task_passed"] and parsed["test_command_observed"]
                          and parsed["browser_command_observed"] and path.with_name("subject-browser.png").is_file())
    return run


def report(root, include=()):
    manifest = load_manifest(root)
    runs = [assess_record(path, manifest) for path in sorted((root / "results").glob("*/result.json"))]
    for run in runs:
        run.update(source_batch=root.name, source_manifest_sha256=file_hash(root / "manifest.json"))
    superseded = []
    for previous_root in include:
        prior = load_manifest(previous_root)
        if any(manifest[key] != prior[key] for key in ("seed_commit", "prompt_sha256", "fixture_hashes")):
            raise ValueError("Cannot combine different tasks or seed fixtures")
        for lane in MODELS:
            previous = [assess_record(path, prior) for path in sorted((previous_root / "results").glob(lane + "-*/result.json"))]
            for run in previous:
                run.update(source_batch=previous_root.name, source_manifest_sha256=file_hash(previous_root / "manifest.json"))
            if any(r["lane"] == lane for r in runs):
                superseded.extend(previous)
            elif manifest["lanes"][lane] == prior["lanes"][lane]:
                runs.extend(previous)
    gates = {lane: repeatability([r for r in runs if r["lane"] == lane]) for lane in MODELS}
    summary = {"manifest_sha256": file_hash(root / "manifest.json"), "seed_commit": manifest["seed_commit"],
               "prompt_sha256": manifest["prompt_sha256"], "runs": runs, "repeatability": gates,
               "cross_lane_evidence_eligible": all(g["eligible"] for g in gates.values()),
               "limitations": manifest["limitations"], "scoring_source_sha256": file_hash(Path(__file__)),
               "superseded_runs": superseded}
    shutil.copyfile(Path(__file__), root / ("scoring-" + file_hash(Path(__file__))[:12] + ".py"))
    save(root / "report.json", summary)
    lines = ["# Agent CLI unattended comparison", "", "| Run | Valid | Task passed | Seconds | Assistant events | Off-target lines |", "|---|---|---|---:|---:|---:|"]
    for r in runs:
        lines.append(f"| {r['run_id']} | {r['valid']} | {r['task_passed']} | {r['wall_seconds']} | {r['assistant_events']} | {r['off_target_lines']} |")
    lines += ["", "Repeatability: " + json.dumps(gates), "", *manifest["limitations"]]
    (root / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"runs": len(runs), "repeatability": gates}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=HERE / "runs/batch-1")
    sub = parser.add_subparsers(dest="action", required=True)
    prep = sub.add_parser("prepare")
    for lane in MODELS:
        prep.add_argument("--" + lane, required=True)
    prep.add_argument("--windows-sandbox", choices=("unelevated", "elevated"))
    run = sub.add_parser("run")
    run.add_argument("--lane", choices=MODELS, required=True)
    run.add_argument("--repeat", type=int, choices=(1, 2), required=True)
    recover = sub.add_parser("finalize")
    recover.add_argument("--lane", choices=MODELS, required=True)
    recover.add_argument("--repeat", type=int, choices=(1, 2), required=True)
    render = sub.add_parser("report")
    render.add_argument("--include", type=Path, action="append", default=[])
    corrected = sub.add_parser("prepare-corrected")
    corrected.add_argument("--source", type=Path, required=True)
    corrected.add_argument("--authorization", required=True,
                           help="Record the actual user approval; this option does not itself grant permission")
    corrected.add_argument("--allow-git-log", action="store_true",
                           help="Include only with separate authorization for fixture Git history inspection")
    corrected.add_argument("--allow-git-metadata", action="store_true",
                           help="Include only with approval for read-only seed Git metadata and path inspection")
    args = parser.parse_args()
    if args.action == "prepare":
        prepare(args)
    elif args.action == "run":
        run_one(args.root.resolve(), args.lane, args.repeat)
    elif args.action == "finalize":
        finalize_run(args.root.resolve(), args.lane, args.repeat)
    elif args.action == "prepare-corrected":
        prepare_corrected(args)
    else:
        report(args.root.resolve(), [path.resolve() for path in args.include])


if __name__ == "__main__":
    main()

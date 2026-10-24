"""Capture native approval requests and explicit human decisions in isolated sessions."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import threading
import time

import harness


PROBE = "Use your file-writing tool to create approval-probe.txt in the current directory with exactly 'cogin-approval-probe'. Do not execute commands or read any files. If permission is denied, stop without retrying or choosing another tool."
CODEX_PROBE = "Request human permission using sandbox_permissions=require_escalated to run exactly: python -c \"print('cogin-approval-probe')\". This tests the approval channel. Do not execute without that approval, read or edit files, or choose other tools. If denied, stop without retrying."
SUPPORTED = {"claude", "codex"}


def approval_request(lane, event):
    if lane == "claude" and event.get("type") == "control_request" and event.get("request", {}).get("subtype") == "can_use_tool":
        return {"kind": "request", "request_id": str(event["request_id"]), "payload": event["request"]}
    if lane == "codex" and "id" in event and event.get("method") in {
            "item/commandExecution/requestApproval", "item/fileChange/requestApproval"}:
        return {"kind": "request", "request_id": str(event["id"]), "payload": event.get("params", {})}
    return None


def approval_response(lane, event, decision):
    if decision not in {"allow", "deny"} or approval_request(lane, event) is None:
        raise ValueError("Only explicit allow-once or deny decisions are supported")
    if lane == "codex":
        allowed = event.get("params", {}).get("availableDecisions")
        chosen = "accept" if decision == "allow" else "decline"
        if decision == "deny" and allowed is not None and "decline" not in allowed and "cancel" in allowed:
            chosen = "cancel"
        if allowed is not None and chosen not in allowed:
            raise ValueError("Requested decision is not offered by the CLI")
        return {"id": event["id"], "result": {"decision": chosen}}
    response = ({"behavior": "allow", "updatedInput": event["request"]["input"]} if decision == "allow"
                else {"behavior": "deny", "message": "Operator declined this request. Do not retry it."})
    return {"type": "control_response", "response": {"subtype": "success", "request_id": event["request_id"],
                                                       "response": response}}


def approval_metrics(events, *, completed, operator):
    requests, decisions = {}, {}
    valid = bool(completed and isinstance(operator, str) and operator.strip())
    for event in events:
        key = event.get("request_id")
        if not isinstance(key, str) or not key:
            valid = False
        if event.get("kind") == "request":
            if key in requests:  # retransmissions are not silently double counted
                valid = False
            requests[key] = event
        elif event.get("kind") == "decision":
            if key not in requests or key in decisions or event.get("decision") not in {"allow", "deny"}:
                valid = False
            if event.get("actor") != "human" or event.get("operator") != operator:
                valid = False
            decisions[key] = event
        else:
            valid = False
    valid = valid and requests.keys() == decisions.keys()
    return {"measurement_state": "measured" if valid else "unmeasured",
            "interruptions": len(requests) if valid else None,
            "approved": sum(e["decision"] == "allow" for e in decisions.values()) if valid else None,
            "denied": sum(e["decision"] == "deny" for e in decisions.values()) if valid else None,
            "observed_requests": len(requests), "unresolved_requests": len(requests.keys() - decisions.keys())}


def console_decision(request, timeout):
    print("\nApproval request (allow applies once; no persistent grants):")
    # JSON escaping keeps terminal control characters in tool inputs inert.
    print(json.dumps(request["payload"], indent=2, ensure_ascii=True))
    answers = queue.Queue()

    def read_answer():
        try:
            while True:
                answer = input("Type allow or deny (Enter denies): ").strip().lower()
                if answer in {"", "deny", "allow"}:
                    answers.put("allow" if answer == "allow" else "deny")
                    return
        except (EOFError, KeyboardInterrupt):
            answers.put(None)

    threading.Thread(target=read_answer, daemon=True).start()
    try:
        decision = answers.get(timeout=max(0.01, timeout))
    except queue.Empty:
        raise ValueError("Human response timeout; no approval sent") from None
    if decision is None:
        raise ValueError("Human input closed; no approval sent")
    return decision


def launcher(lane, pin, worktree, home):
    if lane == "claude":
        argv, env = harness.invocation(lane, pin, worktree, home)
        index = argv.index("--allowedTools")
        del argv[index:index + 2]
        argv[argv.index("--permission-mode") + 1] = "manual"
        argv += ["--input-format", "stream-json", "--permission-prompt-tool", "stdio", "--setting-sources", ""]
        return argv, env
    if lane != "codex":
        raise ValueError("agy print mode has no qualified human approval response channel; no supervised launch")
    env = harness.environment()
    # Reuse the existing subscription login without importing user hooks, MCPs,
    # skills, policies, or instructions. Never log or export the credential copy.
    source = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "auth.json"
    if not source.is_file():
        raise ValueError("Isolated Codex capture requires an existing file-backed subscription login")
    credential_bytes = source.read_bytes()
    credential = json.loads(credential_bytes)
    if not isinstance(credential.get("tokens"), dict) or credential.get("OPENAI_API_KEY"):
        raise ValueError("Codex capture requires subscription credentials, not API-key authentication")
    home.mkdir(parents=True, exist_ok=True)
    auth = home / "auth.json"
    with auth.open("xb") as target:
        target.write(credential_bytes)
    auth.chmod(0o600)
    env["CODEX_HOME"] = str(home)
    argv = [pin["executable"], "app-server", "--listen", "stdio://",
            "-c", 'approval_policy="on-request"', "-c", 'approvals_reviewer="user"',
            "-c", 'sandbox_mode="workspace-write"', "-c", "project_doc_max_bytes=0",
            "-c", 'model_reasoning_effort="medium"']
    if pin.get("windows_sandbox"):
        argv += ["-c", "windows.sandbox=" + json.dumps(pin["windows_sandbox"])]
    return argv, env


def bridge(lane, argv, env, cwd, prompt, artifacts, pin, *, operator, probe=False, timeout=600):
    """Keep stdout and stdin independent so approval requests can be answered."""
    events, inbox = [], queue.Queue()
    start = time.monotonic()
    completed, terminal_received, policy_verified, failure = False, False, False, None
    seen = set()
    with (artifacts / "stdout.jsonl").open("w", encoding="utf-8") as raw, \
            (artifacts / "stdin.jsonl").open("w", encoding="utf-8") as sent, \
            (artifacts / "approvals.jsonl").open("w", encoding="utf-8") as ledger, \
            (artifacts / "stderr.txt").open("w", encoding="utf-8") as stderr:
        process = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=stderr, text=True, encoding="utf-8", errors="replace", bufsize=1)

        def read_stdout():
            for line in process.stdout:
                inbox.put(line)
            inbox.put(None)

        reader = threading.Thread(target=read_stdout, daemon=True)
        reader.start()

        def send(event):
            line = json.dumps(event, ensure_ascii=True) + "\n"
            sent.write(line)
            sent.flush()
            process.stdin.write(line)
            process.stdin.flush()

        def record(event):
            event = {**event, "at": datetime.now(timezone.utc).isoformat()}
            events.append(event)
            ledger.write(json.dumps(event, ensure_ascii=True) + "\n")
            ledger.flush()

        try:
            if lane == "claude":
                send({"type": "control_request", "request_id": "cogin-init", "request": {"subtype": "initialize"}})
            else:
                send({"id": "cogin-init", "method": "initialize", "params": {
                    "clientInfo": {"name": "cogin_supervised", "version": "1.0.0"}}})
            while time.monotonic() - start < timeout:
                try:
                    line = inbox.get(timeout=min(1, max(0.01, timeout - (time.monotonic() - start))))
                except queue.Empty:
                    continue
                if line is None:
                    raise ValueError("CLI closed before a terminal turn event")
                raw.write(line)
                raw.flush()
                event = json.loads(line)
                if not isinstance(event, dict):
                    raise ValueError("Non-object native event")
                if "error" in event and "id" in event:
                    raise ValueError("CLI rejected a control request; inspect private raw evidence")
                if lane == "claude":
                    response = event.get("response", {})
                    if event.get("type") == "control_response" and response.get("request_id") == "cogin-init":
                        if response.get("subtype") != "success":
                            raise ValueError("Claude initialization failed")
                        send({"type": "user", "session_id": "", "parent_tool_use_id": None,
                              "message": {"role": "user", "content": prompt}})
                    if event.get("type") == "system" and event.get("subtype") == "init":
                        if event.get("permissionMode") not in {"manual", "default"} or event.get("model") != pin["model"]:
                            raise ValueError("Claude mode/model differs from the supervised pin")
                        policy_verified = True
                    if event.get("type") == "result":
                        terminal_received = True
                        completed = event.get("subtype") == "success" and not event.get("is_error", False)
                        break
                else:
                    if event.get("id") == "cogin-init":
                        send({"method": "initialized", "params": {}})
                        send({"id": "cogin-thread", "method": "thread/start", "params": {
                            "cwd": str(cwd), "model": pin["model"], "ephemeral": True,
                            "approvalPolicy": "on-request", "approvalsReviewer": "user", "sandbox": "workspace-write"}})
                    if event.get("id") == "cogin-thread":
                        result = event["result"]
                        if (result.get("approvalPolicy") != "on-request" or result.get("approvalsReviewer") != "user"
                                or result.get("sandbox", {}).get("type") != "workspaceWrite"
                                or result.get("model") != pin["model"]):
                            raise ValueError("Codex effective policy/model differs from the supervised pin")
                        policy_verified = True
                        send({"id": "cogin-turn", "method": "turn/start", "params": {
                            "threadId": result["thread"]["id"], "input": [{"type": "text", "text": prompt}],
                            "effort": pin["effort"]}})
                    if event.get("method") == "turn/completed":
                        terminal_received = True
                        completed = event.get("params", {}).get("turn", {}).get("status") == "completed"
                        break
                request = approval_request(lane, event)
                if request:
                    if not policy_verified or request["request_id"] in seen:
                        raise ValueError("Duplicate approval request or missing effective policy")
                    seen.add(request["request_id"])
                    record(request)
                    decision = "deny" if probe else console_decision(request, timeout - (time.monotonic() - start))
                    response = approval_response(lane, event, decision)
                    send(response)
                    record({"kind": "decision", "request_id": request["request_id"], "decision": decision,
                            "actor": "qualification" if probe else "human", "operator": operator})
                elif (lane == "codex" and "id" in event and "method" in event) or event.get("type") == "control_request":
                    # Unknown approval/elicitation kinds must not receive a guessed grant.
                    raise ValueError("Unsupported server request; session stopped without granting it")
            else:
                failure = "timeout"
        except (ValueError, KeyError, BrokenPipeError, EOFError, KeyboardInterrupt) as error:
            failure = str(error) or type(error).__name__
        finally:
            if process.stdin and not process.stdin.closed:
                try:
                    process.stdin.close()
                except OSError:
                    pass
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                if os.name == "nt":
                    harness.command(["taskkill", "/PID", str(process.pid), "/T", "/F"], check=False)
                else:
                    process.kill()
                process.wait(timeout=10)
            reader.join(timeout=5)
            # Retain output emitted between the terminal event and process exit.
            while True:
                try:
                    remaining = inbox.get_nowait()
                except queue.Empty:
                    break
                if remaining:
                    raw.write(remaining)
    complete_capture = terminal_received and policy_verified and failure is None and process.returncode == 0
    metrics = approval_metrics(events, completed=complete_capture and not probe, operator=operator)
    result = {"schema_version": 1, "mode": "qualification" if probe else "supervised", "lane": lane,
              "operator": operator, "completed": completed, "policy_verified": policy_verified,
              "capture_complete": complete_capture,
              "failure": failure, "wall_seconds": round(time.monotonic() - start, 3),
              "returncode": process.returncode, **metrics}
    result["approval_channel_qualified"] = bool(probe and complete_capture and metrics["observed_requests"] > 0
                                                and metrics["unresolved_requests"] == 0)
    harness.save(artifacts / "capture.json", result)
    return result


def capture(source, lane, output, operator, *, probe=False, timeout=600):
    if lane not in SUPPORTED:
        raise ValueError("agy print mode has no qualified human approval response channel; no supervised launch")
    if not probe and (not sys.stdin.isatty() or not operator.strip()):
        raise ValueError("A named human at an interactive terminal is required; use --probe only for denial qualification")
    if not 1 <= timeout <= 3600:
        raise ValueError("Capture timeout must be between 1 and 3600 seconds")
    source, output = Path(source).resolve(), Path(output).resolve()
    manifest = harness.load_manifest(source)
    pin = manifest["lanes"][lane]
    harness.verify_binary(pin)
    if output.exists():
        raise ValueError("Capture directory already exists; never overwrite evidence")
    output.mkdir(parents=True)
    worktree = output / "worktrees" / "subject"
    argv, env = launcher(lane, pin, worktree, output / "private-home")
    seed = output / "seed"
    harness.command(["git", "clone", "--no-local", "--single-branch", "--no-tags", "--branch", "main", str(source / "seed"), str(seed)])
    if harness.git(seed, "rev-parse", "HEAD").stdout.strip() != manifest["seed_commit"]:
        raise ValueError("Capture seed differs")
    harness.git(seed, "worktree", "add", "--detach", str(worktree), manifest["seed_commit"])
    artifacts = output / "results" / "subject"
    artifacts.mkdir(parents=True)
    (artifacts / "verification").mkdir()
    prompt = (CODEX_PROBE if lane == "codex" else PROBE) if probe else (source / "task.txt").read_text(encoding="utf-8")
    harness.save(output / "capture-manifest.json", {"source_manifest_sha256": harness.file_hash(source / "manifest.json"),
        "protocol_version": harness.protocol_version(manifest), "mode": "qualification" if probe else "supervised",
        "lane": lane, "pin": pin, "seed_commit": manifest["seed_commit"], "prompt_sha256": harness.digest(prompt.encode()),
        "argv": argv, "operator": operator, "timeout_seconds": timeout,
        "limitations": ["Supervised transport and permission profile differ from unattended trials; do not pool timings or turn counts.",
                        "Only human decisions are measurements; qualification denials are not human scores."]})
    result = bridge(lane, argv, env, worktree, prompt, artifacts, pin, operator=operator, probe=probe, timeout=timeout)
    revision = harness.archive(seed, worktree, artifacts, "subject")
    patch = artifacts / "changes.patch"
    patch.write_bytes(subprocess.check_output(["git", "diff", "--binary", manifest["seed_commit"], revision], cwd=seed))
    if not probe:
        try:
            result["verification"] = harness.verify_patch(output, manifest, patch, artifacts)
        except (subprocess.SubprocessError, OSError) as error:
            result["verification"] = {"error": type(error).__name__}
            result["failure"] = "Independent verification failed; inspect retained verification artifacts/worktree"
        result.update(harness.score_numstat(harness.git(seed, "diff", "--numstat", manifest["seed_commit"], revision).stdout))
        result["changed_files"] = harness.git(seed, "diff", "--name-only", manifest["seed_commit"], revision).stdout.splitlines()
        if lane == "claude":
            observed = harness.parse_events(lane, (artifacts / "stdout.jsonl").read_text(encoding="utf-8"))
        else:
            observed = {"test_command_observed": False, "browser_command_observed": False}
            for line in (artifacts / "stdout.jsonl").read_text(encoding="utf-8").splitlines():
                try:
                    event = json.loads(line)
                except ValueError:
                    continue  # The bridge has already marked malformed capture incomplete.
                if not isinstance(event, dict):
                    continue
                item = event.get("params", {}).get("item", {})
                if event.get("method") == "item/completed" and item.get("type") == "commandExecution":
                    harness.observe_command(observed, item.get("command", ""))
        result["test_command_observed"] = observed["test_command_observed"]
        result["browser_command_observed"] = observed["browser_command_observed"]
        result["subject_browser_artifact"] = (worktree / "browser.png").is_file()
        result["task_passed"] = result["capture_complete"] and result["completed"] and harness.task_passed(manifest, result)
    result["patch_sha256"] = harness.file_hash(patch)
    result["source_manifest_sha256"] = harness.file_hash(source / "manifest.json")
    result["artifacts"] = {name: harness.file_hash(artifacts / name) for name in (
        "stdout.jsonl", "stdin.jsonl", "stderr.txt", "approvals.jsonl", "changes.patch", "output.bundle")}
    result["capture_manifest_sha256"] = harness.file_hash(output / "capture-manifest.json")
    result["capture_source_sha256"] = harness.file_hash(Path(__file__))
    shutil.copyfile(Path(__file__), output / "capture-source.py")
    harness.git(seed, "worktree", "remove", str(worktree))
    harness.verify_binary(pin)
    harness.save(artifacts / "capture.json", result)
    (artifacts / "capture.sha256").write_text(harness.file_hash(artifacts / "capture.json"))
    return result


def report(captures, output):
    """Render separately from unattended evidence; never splice probe counts into it."""
    output = Path(output).resolve()
    if output.exists():
        raise ValueError("Report output already exists; choose a new report directory")
    rows = []
    seen = set()
    for capture_root in captures:
        root = Path(capture_root).resolve()
        if root in seen:
            raise ValueError("Duplicate capture")
        seen.add(root)
        artifacts = root / "results/subject"
        if harness.file_hash(artifacts / "capture.json") != (artifacts / "capture.sha256").read_text().strip():
            raise ValueError("Capture record changed")
        record = json.loads((artifacts / "capture.json").read_text())
        manifest = json.loads((root / "capture-manifest.json").read_text())
        if (harness.file_hash(root / "capture-manifest.json") != record["capture_manifest_sha256"]
                or harness.file_hash(root / "capture-source.py") != record["capture_source_sha256"]):
            raise ValueError("Capture manifest/source changed")
        required = {"stdout.jsonl", "stdin.jsonl", "stderr.txt", "approvals.jsonl", "changes.patch", "output.bundle"}
        if record["artifacts"].keys() != required:
            raise ValueError("Capture artifact inventory is incomplete")
        for name, expected in record["artifacts"].items():
            if harness.file_hash(artifacts / name) != expected:
                raise ValueError("Capture artifact changed")
        if record["mode"] != manifest["mode"] or record["lane"] != manifest["lane"] or record["operator"] != manifest["operator"]:
            raise ValueError("Capture identity differs from manifest")
        events = [json.loads(line) for line in (artifacts / "approvals.jsonl").read_text().splitlines()]
        native = [json.loads(line) for line in (artifacts / "stdout.jsonl").read_text().splitlines()]
        requests = [approval_request(record["lane"], event) for event in native]
        requests = [request for request in requests if request is not None]
        journal_requests = [{k: e[k] for k in ("kind", "request_id", "payload")} for e in events if e["kind"] == "request"]
        if requests != journal_requests:
            raise ValueError("Approval ledger does not match native requests")
        measured = approval_metrics(events, completed=record["capture_complete"] and record["mode"] == "supervised",
                                    operator=record["operator"])
        rows.append({"capture": root.name, "lane": record["lane"], "mode": record["mode"],
                     "task_completed": record["completed"], "task_passed": record.get("task_passed"),
                     "verification": record.get("verification"),
                     "human_cleanup_lines": None, "capture_sha256": harness.file_hash(artifacts / "capture.json"), **measured})
    if not rows:
        raise ValueError("At least one capture is required")
    output.mkdir(parents=True)
    harness.save(output / "report.json", {"schema_version": 1, "captures": rows,
        "limitations": ["Qualification probes are not human measurements.",
                        "Supervised transports and policies differ from unattended trials; do not pool timings or assistant events.",
                        "agy has no qualified headless human approval channel."]})
    lines = ["# Supervised approval capture", "", "| Capture | Mode | Interruptions | Approved | Denied |", "|---|---|---:|---:|---:|"]
    for row in rows:
        values = ["unmeasured" if row[k] is None else str(row[k]) for k in ("interruptions", "approved", "denied")]
        lines.append(f"| {row['capture']} | {row['mode']} | {' | '.join(values)} |")
    lines += ["", "Qualification probes are not human measurements. Cleanup requires a separate blind review."]
    (output / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    run = sub.add_parser("capture")
    run.add_argument("--source", required=True, type=Path)
    run.add_argument("--lane", required=True, choices=("claude", "codex", "agy"))
    run.add_argument("--output", required=True, type=Path)
    run.add_argument("--operator", default="")
    run.add_argument("--probe", action="store_true", help="Deny-only qualification; never records a human score")
    run.add_argument("--timeout", type=int, default=600)
    render = sub.add_parser("report")
    render.add_argument("--capture", type=Path, action="append", required=True)
    render.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.action == "report":
        report(args.capture, args.output)
        return
    result = capture(args.source, args.lane, args.output, args.operator, probe=args.probe, timeout=args.timeout)
    print(json.dumps(result))
    if result["failure"] or not result["capture_complete"] or (args.probe and not result["approval_channel_qualified"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()

import json
from pathlib import Path
import sys
import threading
import urllib.error
import urllib.request

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import human_review
import review_console
from test_human_review import review_fixture


@pytest.fixture
def app(tmp_path, monkeypatch):
    root, report = review_fixture(tmp_path, monkeypatch)
    package = tmp_path / "package"
    human_review.prepare(report, [root], package)
    return review_console.ReviewApp(package, root)


def test_public_review_contains_no_controller_identity_and_counts_only_changed_lines(app):
    data = app.public_review()
    assert "claude" not in json.dumps(data)
    assert "source_batch" not in json.dumps(data)
    case = data["cases"][0]
    assert sum(row["change_id"] is not None for row in case["lines"]) == 2
    draft = data["draft"]
    draft["cases"][case["id"]] = {"selected": [0], "reviewed": True, "reason": "Restore the old line."}
    saved = app.save_draft(draft)
    assert saved["revision"] == 1
    assert review_console.ReviewApp(app.package, app.source).public_review()["draft"]["cases"] == draft["cases"]
    with pytest.raises(ValueError, match="changed"):
        app.save_draft(draft)
    saved["cases"][case["id"]]["selected"] = [9]
    with pytest.raises(ValueError, match="line"):
        app.save_draft(saved)


def test_submit_requires_explicit_complete_review_and_locks_without_exposing_mapping(app):
    data = app.public_review()
    with pytest.raises(ValueError):
        app.submit(data["draft"]["revision"])
    draft = data["draft"]
    draft.update(reviewer="Test reviewer", blind_attestation=True)
    for value in draft["cases"].values():
        value.update(reviewed=True, reason="Every change is required.", selected=[])
    draft = app.save_draft(draft)
    app.submit(draft["revision"])
    assert app.public_review()["locked"]
    assert "claude" not in json.dumps(app.public_review())
    receipt = human_review.read(app.package / "controller/accepted-scores.json")
    assert next(iter(receipt["scores"].values()))["human_cleanup_lines"] == 0
    with pytest.raises(ValueError, match="locked"):
        app.save_draft(draft)


def test_http_rejects_missing_token_foreign_origin_and_private_files(app):
    server = review_console.make_server(app, 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        with pytest.raises(urllib.error.HTTPError) as denied:
            urllib.request.urlopen(base + "/api/review")
        assert denied.value.code == 403
        request = urllib.request.Request(base + "/api/review", headers={"X-Review-Token": server.token})
        assert "cases" in json.load(urllib.request.urlopen(request))
        for path in ("/controller/mapping.json", "/../controller/mapping.json", "/private-home/auth.json"):
            with pytest.raises(urllib.error.HTTPError) as hidden:
                urllib.request.urlopen(base + path)
            assert hidden.value.code == 404
        request = urllib.request.Request(base + "/api/draft", data=b"{}", headers={
            "X-Review-Token": server.token, "Content-Type": "application/json", "Origin": "http://foreign.invalid"})
        with pytest.raises(urllib.error.HTTPError) as csrf:
            urllib.request.urlopen(request)
        assert csrf.value.code == 403
    finally:
        server.shutdown()
        server.server_close()


def test_browser_decisions_wait_for_explicit_action_and_reject_stale_ids():
    channel = review_console.BrowserDecisions()
    result = []
    worker = threading.Thread(target=lambda: result.append(channel({"request_id": "1", "payload": {"command": "test"}}, 2)))
    worker.start()
    assert channel.ready.wait(1)
    assert result == []
    with pytest.raises(ValueError):
        channel.decide("wrong", "allow")
    channel.decide("1", "deny")
    worker.join(2)
    assert result == ["deny"]
    with pytest.raises(ValueError):
        channel.decide("1", "allow")


def test_manual_form_is_preserved_on_restart_and_submit(app):
    app.save_draft(app.public_review()["draft"])
    form = human_review.read(app.form_path)
    form["reviewer"] = "Existing manual reviewer"
    app.form_path.write_text(json.dumps(form))
    with pytest.raises(ValueError, match="Manual score form changed"):
        app.submit(app.draft["revision"])
    with pytest.raises(ValueError, match="manual score form"):
        review_console.ReviewApp(app.package, app.source)
    assert human_review.read(app.form_path)["reviewer"] == "Existing manual reviewer"


@pytest.mark.parametrize("decision", ["allow", "deny", "stop"])
def test_browser_channel_drives_native_bridge_without_automatic_decisions(tmp_path, decision):
    import os
    import supervised

    fake = tmp_path / "fake_cli.py"
    fake.write_text('''import json
def send(value): print(json.dumps(value), flush=True)
input()
send({"type":"control_response","response":{"request_id":"cogin-init","subtype":"success"}})
input()
send({"type":"system","subtype":"init","permissionMode":"default","model":"test-model"})
send({"type":"control_request","request_id":"request-1","request":{"subtype":"can_use_tool","tool_name":"Write","input":{"file_path":"app.py","content":"test"}}})
try: input()
except EOFError: raise SystemExit(0)
send({"type":"result","subtype":"success","is_error":False})
''')
    channel = review_console.BrowserDecisions()
    results = []
    worker = threading.Thread(target=lambda: results.append(supervised.bridge(
        "claude", [sys.executable, str(fake)], dict(os.environ), tmp_path, "test", tmp_path,
        {"model": "test-model"}, operator="test fixture", timeout=5, decision_provider=channel)))
    worker.start()
    assert channel.ready.wait(2)
    assert not results
    if decision == "stop":
        channel.stop()
    else:
        channel.decide("request-1", decision)
    worker.join(5)
    assert len(results) == 1
    sent = [json.loads(line) for line in (tmp_path / "stdin.jsonl").read_text().splitlines()]
    if decision == "stop":
        assert results[0]["interruptions"] is None
        assert len(sent) == 2
    else:
        assert results[0]["interruptions"] == 1
        assert sent[-1]["response"]["response"]["behavior"] == decision

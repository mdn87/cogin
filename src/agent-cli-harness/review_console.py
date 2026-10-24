"""Loopback-only human collection console. Never serves controller files."""

import argparse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import secrets
import threading
import time
import webbrowser

import harness
import human_review
import supervised

ASSETS = Path(__file__).with_name("review_ui")


def atomic_save(path, value):
    temporary = path.with_suffix(".tmp")
    harness.save(temporary, value)
    temporary.replace(path)


def patch_lines(text):
    rows, changed = [], 0
    old = new = None
    for line in text.splitlines():
        match = re.match(r"@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
        if line.startswith("diff --git"):
            old = new = None
        if match:
            old, new = map(int, match.groups())
        kind = "meta"
        if not match and old is not None:
            kind = {"+": "add", "-": "remove", " ": "context"}.get(line[:1], "meta")
        change_id = changed if kind in {"add", "remove"} else None
        rows.append({"text": line, "kind": kind, "change_id": change_id,
                     "old": old if kind in {"remove", "context"} else None,
                     "new": new if kind in {"add", "context"} else None})
        changed += change_id is not None
        if kind in {"remove", "context"}:
            old += 1
        if kind in {"add", "context"}:
            new += 1
    return rows


class BrowserDecisions:
    def __init__(self):
        self.cancelled = threading.Event()
        self.ready = threading.Event()
        self.condition = threading.Condition()
        self.pending = None
        self.answer = None
        self.host_sha256 = harness.digest(Path(__file__).read_bytes() + b"".join(p.read_bytes() for p in sorted(ASSETS.iterdir())))

    def __call__(self, request, timeout):
        with self.condition:
            self.pending, self.answer = request, None
            self.ready.set()
            until = time.monotonic() + timeout
            try:
                while self.answer is None and not self.cancelled.is_set():
                    remaining = until - time.monotonic()
                    if remaining <= 0:
                        raise ValueError("Human response timeout; no approval sent")
                    self.condition.wait(min(remaining, 1))
                if self.cancelled.is_set():
                    raise EOFError("Browser operator stopped the session")
                return self.answer
            finally:
                self.pending = None
                self.ready.clear()

    def decide(self, request_id, decision):
        with self.condition:
            if self.pending is None or self.pending["request_id"] != request_id or self.answer is not None or self.cancelled.is_set():
                raise ValueError("Approval request is no longer pending")
            if decision not in {"allow", "deny"}:
                raise ValueError("Choose allow once or deny")
            self.answer = decision
            self.condition.notify_all()

    def stop(self):
        self.cancelled.set()
        with self.condition:
            self.condition.notify_all()


class ReviewApp:
    def __init__(self, package, source):
        self.package, self.source = Path(package).resolve(), Path(source).resolve()
        self.lock = threading.RLock()
        mapping = human_review.load_package(self.package)
        self.mapping = mapping
        self.draft_path = self.package / "controller/ui-draft.json"
        self.form_path = self.package / "reviewer/scores.json"
        self.form_hash = harness.file_hash(self.form_path)
        form = human_review.read(self.form_path)
        if not self.is_locked() and (form.get("reviewer") or form.get("blind_attestation") or any(
                row["human_cleanup_lines"] is not None or row.get("reason") for row in form["scores"])):
            raise ValueError("A manual score form already has work; import it before opening the console")
        self.cases = []
        for key, metadata in mapping["cases"].items():
            rows = patch_lines((self.package / "reviewer/cases" / key / "changes.patch").read_text(encoding="utf-8"))
            count = sum(row["change_id"] is not None for row in rows)
            if count != metadata["changed_lines"]:
                raise ValueError("Patch cannot be represented faithfully by the line selector")
            self.cases.append({"id": key, "lines": rows, "changed_lines": count})
        self.case_counts = {case["id"]: case["changed_lines"] for case in self.cases}
        self.draft = {"revision": 0, "reviewer": "", "blind_attestation": False,
                      "cases": {key: {"selected": [], "reason": "", "reviewed": False} for key in self.case_counts}}
        if self.draft_path.exists():
            self.draft = self.validate_draft(human_review.read(self.draft_path))
        self.index_path = self.package / "controller/ui-sessions.json"
        self.sessions = human_review.read(self.index_path) if self.index_path.exists() else []
        for row in self.sessions:
            if row["status"] == "running":
                row["status"] = "interrupted"
                row["error"] = "Console restarted; inspect retained session artifacts before collecting another trial."
        self.channel = None
        self.worker = None

    def is_locked(self):
        receipt = self.package / "controller/accepted-scores.json"
        if receipt.exists() and harness.file_hash(receipt) != receipt.with_suffix(".sha256").read_text().strip():
            raise ValueError("Accepted scores changed")
        return receipt.exists()

    def public_review(self):
        with self.lock:
            return {"cases": self.cases, "draft": self.draft, "locked": self.is_locked(),
                    "task": (self.package / "reviewer/task.txt").read_text(encoding="utf-8"),
                    "base": {p.name: p.read_text(encoding="utf-8") for p in (self.package / "reviewer/base").iterdir() if p.is_file()}}

    def validate_draft(self, value):
        if not isinstance(value, dict) or type(value.get("revision")) is not int or value["revision"] < 0:
            raise ValueError("Invalid draft revision")
        if not isinstance(value.get("reviewer"), str) or len(value["reviewer"]) > 120 or type(value.get("blind_attestation")) is not bool:
            raise ValueError("Invalid reviewer details")
        cases = value.get("cases")
        if not isinstance(cases, dict) or cases.keys() != self.case_counts.keys():
            raise ValueError("Draft must contain exactly the anonymous cases")
        cleaned = {}
        for key, case in cases.items():
            if not isinstance(case, dict) or type(case.get("reviewed")) is not bool or not isinstance(case.get("reason"), str) or len(case["reason"]) > 4000:
                raise ValueError("Invalid case review")
            selected = case.get("selected")
            if (not isinstance(selected, list) or any(type(n) is not int or not 0 <= n < self.case_counts[key] for n in selected)
                    or len(set(selected)) != len(selected)):
                raise ValueError("Selected line is invalid or duplicated")
            cleaned[key] = {"selected": sorted(selected), "reason": case["reason"], "reviewed": case["reviewed"]}
        return {"revision": value["revision"], "reviewer": value["reviewer"], "blind_attestation": value["blind_attestation"], "cases": cleaned}

    def save_draft(self, value):
        with self.lock:
            if self.is_locked():
                raise ValueError("Review is locked after submission")
            draft = self.validate_draft(value)
            current = human_review.read(self.draft_path) if self.draft_path.exists() else self.draft
            if draft["revision"] != current["revision"]:
                raise ValueError("Draft changed in another tab; reload before editing")
            draft["revision"] += 1
            atomic_save(self.draft_path, draft)
            self.draft = draft
            return draft

    def submit(self, revision):
        with self.lock:
            human_review.load_package(self.package)
            if self.is_locked():
                raise ValueError("Review is already locked")
            if revision != self.draft["revision"] or (self.draft_path.exists() and human_review.read(self.draft_path)["revision"] != revision):
                raise ValueError("Draft changed; reload before submitting")
            if harness.file_hash(self.form_path) != self.form_hash:
                raise ValueError("Manual score form changed; it will not be overwritten")
            if not all(case["reviewed"] for case in self.draft["cases"].values()):
                raise ValueError("Review every patch before submitting")
            form = {"review_id": self.mapping["review_id"], "reviewer": self.draft["reviewer"],
                    "blind_attestation": self.draft["blind_attestation"], "scores": [
                        {"case_id": key, "human_cleanup_lines": len(case["selected"]), "reason": case["reason"]}
                        for key, case in self.draft["cases"].items()]}
            human_review.validate_scores(form, self.mapping["cases"])
            atomic_save(self.form_path, form)
            human_review.import_scores(self.package, self.form_path)
            self.prepare_status()
            return {"locked": True}

    def prepare_status(self):
        """Prepare an evidence summary for the controller; never silently publish a board edit."""
        atomic_save(self.package / "controller/collection-status.json", {
            "updated_at": datetime.now(timezone.utc).isoformat(), "blind_review_collected": self.is_locked(),
            "case_count": len(self.cases), "supervised_sessions": [
                {k: row.get(k) for k in ("id", "lane", "status", "interruptions", "task_passed")} for row in self.sessions],
            "agy": "unsupported: headless mode cannot prompt", "publication_state": "prepared; Dias publication requires controller validation"})

    def public_sessions(self):
        with self.lock:
            pending = None
            if self.channel is not None:
                with self.channel.condition:
                    if self.channel.pending is not None and self.channel.answer is None:
                        pending = self.channel.pending.copy()
            return {"sessions": self.sessions, "pending": pending,
                    "running": self.worker is not None and self.worker.is_alive()}

    def start_session(self, lane, operator):
        with self.lock:
            if lane not in supervised.SUPPORTED or not isinstance(operator, str) or not operator.strip() or len(operator) > 120:
                raise ValueError("Choose Claude or Codex and enter your name")
            if self.worker is not None and self.worker.is_alive():
                raise ValueError("Finish the current session first")
            if any(row["status"] == "interrupted" for row in self.sessions):
                raise ValueError("A previous session was interrupted by restart; controller inspection is required before another run")
            key = lane + "-" + secrets.token_hex(6)
            output = self.package / "controller/sessions" / key
            row = {"id": key, "lane": lane, "status": "running", "interruptions": None, "task_passed": None}
            self.sessions.append(row)
            atomic_save(self.index_path, self.sessions)
            self.channel = BrowserDecisions()
            channel = self.channel

            def run():
                try:
                    result = supervised.capture(self.source, lane, output, operator.strip(), decision_provider=channel)
                    with self.lock:
                        row.update(status="finished", interruptions=result["interruptions"], task_passed=result.get("task_passed"),
                                   error=result.get("failure"))
                    roots = [self.package / "controller/sessions" / r["id"] for r in self.sessions
                             if (self.package / "controller/sessions" / r["id"] / "results/subject/capture.sha256").exists()]
                    supervised.report(roots, self.package / "controller/session-reports" / key)
                except Exception as error:
                    with self.lock:
                        row.update(status="error", error=str(error))
                finally:
                    with self.lock:
                        atomic_save(self.index_path, self.sessions)
                        self.prepare_status()

            self.worker = threading.Thread(target=run, daemon=False)
            self.worker.start()
            return {"id": key}

    def close(self):
        if self.channel:
            self.channel.stop()
        if self.worker:
            self.worker.join()


def make_server(app, port):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def respond(self, status, body, content_type="application/json"):
            data = json.dumps(body).encode() if content_type == "application/json" else body
            self.send_response(status)
            self.send_header("Content-Type", content_type + "; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(data)

        def trusted(self):
            host = f"127.0.0.1:{self.server.server_port}"
            token = self.headers.get("X-Review-Token", "")
            return (self.headers.get("Host") == host and self.headers.get("Origin", "http://" + host) == "http://" + host
                    and token.isascii() and secrets.compare_digest(token, self.server.token))

        def do_GET(self):
            if self.path in {"/", "/app.js", "/style.css"}:
                filename, mime = {"/": ("index.html", "text/html"), "/app.js": ("app.js", "text/javascript"), "/style.css": ("style.css", "text/css")}[self.path]
                self.respond(200, (ASSETS / filename).read_bytes(), mime)
            elif self.path in {"/api/review", "/api/sessions"}:
                if not self.trusted():
                    self.respond(403, {"error": "Open the console using its private local link"})
                    return
                try:
                    self.respond(200, app.public_review() if self.path == "/api/review" else app.public_sessions())
                except (ValueError, OSError) as error:
                    self.respond(409, {"error": str(error)})
            else:
                self.respond(404, {"error": "Not found"})

        def do_POST(self):
            if not self.trusted() or self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                self.respond(403, {"error": "Request rejected"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 100000:
                    raise ValueError("Invalid request size")
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict):
                    raise ValueError("Expected an object")
                if self.path == "/api/draft":
                    result = app.save_draft(data)
                elif self.path == "/api/submit":
                    result = app.submit(data.get("revision"))
                elif self.path == "/api/start":
                    result = app.start_session(data.get("lane"), data.get("operator"))
                elif self.path == "/api/decision":
                    if app.channel is None or data.get("session_id") != app.sessions[-1]["id"]:
                        raise ValueError("Session is no longer active")
                    app.channel.decide(data.get("request_id"), data.get("decision"))
                    result = {"recorded": True}
                elif self.path == "/api/stop":
                    if app.channel is None or data.get("session_id") != app.sessions[-1]["id"]:
                        raise ValueError("Session is no longer active")
                    app.channel.stop()
                    result = {"stopping": True}
                else:
                    self.respond(404, {"error": "Not found"})
                    return
                self.respond(200, result)
            except (ValueError, TypeError, OSError) as error:
                self.respond(409, {"error": str(error)})

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.token = secrets.token_urlsafe(32)
    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, default=harness.HERE / "runs/blind-review-v2-1")
    parser.add_argument("--source", type=Path, default=harness.HERE / "runs/protocol-v2-batch-2")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--open", action="store_true")
    parser.add_argument("--url-file", type=Path)
    args = parser.parse_args()
    app = ReviewApp(args.package, args.source)
    server = make_server(app, args.port)
    url = f"http://127.0.0.1:{server.server_port}/#{server.token}"
    print(url, flush=True)
    if args.url_file:
        args.url_file.write_text(url, encoding="utf-8")
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        app.close()


if __name__ == "__main__":
    main()

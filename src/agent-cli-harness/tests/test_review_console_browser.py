"""Real Chromium checks using only synthetic packages and approval requests."""
import os
from pathlib import Path
import threading

import pytest

from test_review_console import app  # shared synthetic package fixture
import harness
import human_review
import review_console


def test_review_and_approval_controls_in_chromium(app, monkeypatch):
    playwright = pytest.importorskip("playwright.sync_api")
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", harness.environment().get("PLAYWRIGHT_BROWSERS_PATH", "0"))
    server = review_console.make_server(app, 0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    decisions = []
    request_ready = threading.Event()

    def simulated_capture(source, lane, output, operator, *, decision_provider):
        assert request_ready.wait(20)
        decisions.append(decision_provider({"request_id": "synthetic-1", "payload": {
            "command": "<script>window.untrustedRan=true</script>", "test_fixture": True}}, 20))
        return {"interruptions": 1, "task_passed": False}

    monkeypatch.setattr(review_console.supervised, "capture", simulated_capture)
    monkeypatch.setattr(review_console.supervised, "report", lambda *args: None)
    try:
        with playwright.sync_playwright() as driver:
            browser = driver.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 1100})
            # Embedded browsers may suppress native dialogs. Submission must
            # still offer a visible confirmation without relying on confirm().
            page.add_init_script("window.confirm = () => false")
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(f"http://127.0.0.1:{server.server_port}/#{server.token}")
            expect = playwright.expect
            expect(page.locator("#progress")).to_have_text("0 of 1 reviewed")
            expect(page.locator("#submit")).to_be_disabled()
            page.locator("#diff input").first.check()
            page.locator("#reason").fill("Synthetic test: restore this line.")
            page.locator("#reviewed").check()
            expect(page.locator("#save-state")).to_have_text("Saved on this computer")
            page.reload()
            expect(page.locator("#diff input").first).to_be_checked()
            expect(page.locator("#reason")).to_have_value("Synthetic test: restore this line.")
            page.locator("#zero").click()
            expect(page.locator("#count")).to_have_text("0 cleanup lines selected")
            page.locator("#reason").fill("Synthetic test: no cleanup required.")
            page.locator("#reviewer").fill("Synthetic reviewer")
            page.locator("#attestation").check()
            expect(page.locator("#submit")).to_be_enabled()
            screenshots = os.environ.get("COGIN_UI_SCREENSHOT_DIR")
            if screenshots:
                target = Path(screenshots)
                target.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(target / "review-console-desktop.png"), full_page=True)
                page.set_viewport_size({"width": 390, "height": 844})
                page.screenshot(path=str(target / "review-console-mobile.png"), full_page=True)
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                page.set_viewport_size({"width": 1440, "height": 1100})
            page.locator("#submit").click()
            expect(page.locator("#submit-confirmation")).to_be_visible()
            assert not app.is_locked()
            page.locator("#cancel-submit").click()
            expect(page.locator("#submit-confirmation")).to_be_hidden()
            assert not app.is_locked()
            page.locator("#submit").click()
            page.locator("#confirm-submit").click()
            expect(page.locator("#submitted")).to_be_visible()
            page.reload()
            expect(page.locator("#reason")).to_be_disabled()
            assert app.is_locked()
            assert next(iter(human_review.read(app.package / "controller/accepted-scores.json")["scores"].values()))["human_cleanup_lines"] == 0
            page.locator("#sessions-tab").click()
            expect(page.locator("#no-request")).to_have_text("No session is running. Start a session to collect approvals.")
            page.locator("#operator").fill("Synthetic operator")
            page.locator("#start-claude").click()
            expect(page.locator("#no-request")).to_contain_text("No approval request is pending. The CLI may work without prompting")
            request_ready.set()
            expect(page.locator("#approval")).to_be_visible()
            expect(page.locator("#no-request")).to_be_hidden()
            assert decisions == []
            assert page.evaluate("window.untrustedRan === undefined")
            expect(page.locator("#payload")).to_contain_text("<script>")
            page.locator("#deny").click()
            expect(page.locator("#history")).to_contain_text("Interruptions: 1")
            expect(page.locator("#no-request")).to_have_text("No approval request is pending. The last session ended; see its result below.")
            assert decisions == ["deny"]
            assert not errors
            browser.close()
    finally:
        app.close()
        server.shutdown()
        server.server_close()

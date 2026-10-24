"""Run the local app in a real headless browser; no download or external network."""

import argparse
import json
from pathlib import Path
import threading
import urllib.error
import urllib.request

from playwright.sync_api import sync_playwright

import app


def check(feature=False, screenshot=None):
    server = app.ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    url = f"http://127.0.0.1:{server.server_port}"
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.goto(url)
                assert page.locator("#tasks li").count() == 3
                if feature:
                    for status, expected in (("open", ["1", "3"]), ("done", ["2"]), ("all", ["1", "2", "3"])):
                        page.select_option("#status-filter", status)
                        page.wait_for_url(f"**/?status={status}")
                        assert page.locator("#status-filter").input_value() == status
                        assert page.locator("#tasks li").evaluate_all("els => els.map(e => e.dataset.id)") == expected
                        assert page.locator("#count").inner_text() == f"{len(expected)} tasks"
                        page.reload()
                        assert page.locator("#status-filter").input_value() == status
                    try:
                        urllib.request.urlopen(url + "/?status=bogus")
                    except urllib.error.HTTPError as error:
                        assert error.code == 400
                    else:
                        raise AssertionError("Invalid status must return HTTP 400")
                if screenshot:
                    page.screenshot(path=str(screenshot))
                return {"browser": "chromium", "browser_version": browser.version, "feature": feature, "result": "passed"}
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--feature", action="store_true")
    parser.add_argument("--screenshot", type=Path)
    args = parser.parse_args()
    print(json.dumps(check(args.feature, args.screenshot)))

"""A local task board with no application dependencies."""

from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


TASKS = (
    {"id": 1, "title": "Write release notes", "done": False},
    {"id": 2, "title": "Run checks", "done": True},
    {"id": 3, "title": "Review changes", "done": False},
)


def render_page():
    items = "".join(
        f'<li data-id="{task["id"]}" data-status="{"done" if task["done"] else "open"}">'
        f'{escape(task["title"])}</li>' for task in TASKS
    )
    return (
        '<!doctype html><html lang="en"><meta charset="utf-8"><title>Task board</title>'
        '<main><h1>Task board</h1><p id="count">3 tasks</p>'
        f'<ul id="tasks">{items}</ul></main></html>'
    )


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.split("?", 1)[0] != "/":
            self.send_error(404)
            return
        content = render_page().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 8000), Handler)
    print("Task board at http://127.0.0.1:8000", flush=True)
    server.serve_forever()

"""Dashboard HTTP routing and static file responses."""
from errors import ApplicationError
from api.error_handling import http_errors
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse
from services.paths import (
    WEB_DIR,
    INDEX_FILE,
    DATA_DIR,
)
from version import APP_VERSION
from services.configuration import (
    ensure_env_file,
    read_config,
    save_config_values,
)
from services.processes import (
    start_export_job,
    start_watch_job,
    stop_watch_job,
    get_watch_status,
    get_export_status,
)
from services.scheduler import (
    retry_scheduler_run,
    start_scheduler_job,
    stop_scheduler_job,
    get_scheduler_status,
)
from services.scheduler_history import (
    read_scheduler_run,
    list_scheduler_runs_response,
    reconcile_incomplete_scheduler_runs,
)
from services.dashboard_exports import (
    search_indexed_comments,
    list_export_files,
    get_export_summary,
    get_export_charts,
    get_export_posts,
    get_export_filtered_summary,
    get_export_post,
    get_export_period_compare,
)

HOST = "0.0.0.0"
PORT = 9595


class DashboardHandler(SimpleHTTPRequestHandler):
    @http_errors
    def do_GET(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        if path in ("/", "/index.html", "/comments_dashboard.html"):
            self.serve_file(INDEX_FILE, "text/html; charset=utf-8")
            return

        if path.startswith("/web/"):
            self.serve_web_file(path)
            return

        if path.startswith("/data/"):
            self.serve_data_file(path)
            return

        if path == "/api/config":
            self.send_json(read_config())
            return

        if path == "/api/version":
            self.send_json({"version": APP_VERSION})
            return

        if path == "/api/exports":
            query = parse_qs(parsed.query)
            sort_by = (query.get("sort") or ["date"])[0]
            self.send_json(list_export_files(sort_by))
            return

        if path == "/api/search":
            query = parse_qs(parsed.query)
            try:
                self.send_json(search_indexed_comments(query))
            except ApplicationError:
                raise
            except (ValueError, OSError, json.JSONDecodeError) as e:
                self.send_json({"ok": False, "error": str(e)}, status=400)
            return

        if path.startswith("/api/export/") and path.endswith("/posts"):
            file_name = path.removeprefix("/api/export/").removesuffix("/posts")
            query = parse_qs(parsed.query)
            try:
                self.send_json(get_export_posts(unquote(file_name), query))
            except ApplicationError:
                raise
            except (FileNotFoundError, ValueError, OSError, json.JSONDecodeError) as e:
                self.send_json({"ok": False, "error": str(e)}, status=400)
            return

        if path.startswith("/api/export/") and path.endswith("/filtered-summary"):
            file_name = path.removeprefix("/api/export/").removesuffix("/filtered-summary")
            query = parse_qs(parsed.query)
            try:
                self.send_json(get_export_filtered_summary(unquote(file_name), query))
            except ApplicationError:
                raise
            except (FileNotFoundError, ValueError, OSError, json.JSONDecodeError) as e:
                self.send_json({"ok": False, "error": str(e)}, status=400)
            return

        if path.startswith("/api/export/") and "/post/" in path:
            file_name, post_id = path.removeprefix("/api/export/").split("/post/", 1)
            try:
                self.send_json(get_export_post(unquote(file_name), unquote(post_id)))
            except ApplicationError:
                raise
            except (FileNotFoundError, ValueError, OSError, json.JSONDecodeError) as e:
                self.send_json({"ok": False, "error": str(e)}, status=404)
            return

        if path.startswith("/api/export/") and path.endswith("/summary"):
            file_name = path.removeprefix("/api/export/").removesuffix("/summary")
            try:
                self.send_json(get_export_summary(unquote(file_name)))
            except ApplicationError:
                raise
            except (FileNotFoundError, ValueError, OSError, json.JSONDecodeError) as e:
                self.send_json({"ok": False, "error": str(e)}, status=404)
            return

        if path.startswith("/api/export/") and path.endswith("/charts"):
            file_name = path.removeprefix("/api/export/").removesuffix("/charts")
            try:
                self.send_json(get_export_charts(unquote(file_name)))
            except ApplicationError:
                raise
            except (FileNotFoundError, ValueError, OSError, json.JSONDecodeError) as e:
                self.send_json({"ok": False, "error": str(e)}, status=404)
            return

        if path.startswith("/api/export/") and path.endswith("/compare"):
            file_name = path.removeprefix("/api/export/").removesuffix("/compare")
            query = parse_qs(parsed.query)
            from_date = (query.get("from") or [""])[0]
            to_date = (query.get("to") or [""])[0]

            try:
                self.send_json(get_export_period_compare(unquote(file_name), from_date, to_date))
            except ApplicationError:
                raise
            except (FileNotFoundError, ValueError, OSError, json.JSONDecodeError) as e:
                self.send_json({"ok": False, "error": str(e)}, status=400)
            return

        if path == "/api/export/status":
            self.send_json(get_export_status())
            return

        if path == "/api/scheduler/status":
            self.send_json(get_scheduler_status())
            return

        if path == "/api/scheduler/history":
            query = parse_qs(parsed.query)
            try:
                limit = int((query.get("limit") or ["50"])[0])
            except ApplicationError:
                raise
            except ValueError:
                limit = 50
            try:
                offset = int((query.get("offset") or ["0"])[0])
            except ApplicationError:
                raise
            except ValueError:
                offset = 0
            status = (query.get("status") or [""])[0]
            channel = (query.get("channel") or [""])[0]
            self.send_json(list_scheduler_runs_response(
                limit=max(1, min(limit, 200)),
                offset=max(0, offset),
                status=status.strip() or None,
                channel=channel.strip() or None,
            ))
            return

        if path.startswith("/api/scheduler/history/"):
            run_id = path.removeprefix("/api/scheduler/history/")
            try:
                self.send_json({"ok": True, "run": read_scheduler_run(run_id)})
            except ApplicationError:
                raise
            except (FileNotFoundError, ValueError, OSError, json.JSONDecodeError) as e:
                self.send_json({"ok": False, "error": str(e)}, status=404)
            return

        if path == "/api/watch/status":
            self.send_json(get_watch_status())
            return

        self.send_error(404, "Not found")

    @http_errors
    def do_POST(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        if path == "/api/export/start":
            self.start_export()
            return

        if path == "/api/config":
            self.save_config()
            return

        if path == "/api/scheduler/start":
            self.start_scheduler()
            return

        if path == "/api/scheduler/stop":
            self.stop_scheduler()
            return

        if path == "/api/watch/start":
            self.start_watch()
            return

        if path == "/api/watch/stop":
            self.stop_watch()
            return

        if path.startswith("/api/scheduler/history/") and path.endswith("/retry"):
            run_id = path.removeprefix("/api/scheduler/history/").removesuffix("/retry")
            self.retry_scheduler_run(run_id)
            return

        self.send_error(404, "Not found")

    def start_export(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except ApplicationError:
            raise
        except (ValueError, json.JSONDecodeError):
            self.send_json({"ok": False, "error": "Invalid JSON payload"}, status=400)
            return

        try:
            start_export_job(payload)
        except ApplicationError:
            raise
        except ValueError as e:
            self.send_json({"ok": False, "error": str(e)}, status=400)
            return
        except OSError as e:
            self.send_json({"ok": False, "error": f"Cannot write .env: {e}"}, status=500)
            return

        self.send_json({"ok": True, "status": get_export_status()})

    def save_config(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except ApplicationError:
            raise
        except (ValueError, json.JSONDecodeError):
            self.send_json({"ok": False, "error": "Invalid JSON payload"}, status=400)
            return

        try:
            config = save_config_values(payload)
        except ApplicationError:
            raise
        except ValueError as e:
            self.send_json({"ok": False, "error": str(e)}, status=400)
            return
        except OSError as e:
            self.send_json({"ok": False, "error": f"Cannot write .env: {e}"}, status=500)
            return

        self.send_json({"ok": True, "config": config})

    def start_scheduler(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except ApplicationError:
            raise
        except (ValueError, json.JSONDecodeError):
            self.send_json({"ok": False, "error": "Invalid JSON payload"}, status=400)
            return

        try:
            start_scheduler_job(payload)
        except ApplicationError:
            raise
        except ValueError as e:
            self.send_json({"ok": False, "error": str(e)}, status=400)
            return
        except OSError as e:
            self.send_json({"ok": False, "error": f"Cannot write .env: {e}"}, status=500)
            return

        self.send_json({"ok": True, "scheduler": get_scheduler_status()})

    def stop_scheduler(self):
        stop_scheduler_job()
        self.send_json({"ok": True, "scheduler": get_scheduler_status()})

    def retry_scheduler_run(self, run_id):
        try:
            new_run_id = retry_scheduler_run(run_id)
        except ApplicationError:
            raise
        except FileNotFoundError as e:
            self.send_json({"ok": False, "error": str(e)}, status=404)
            return
        except ValueError as e:
            self.send_json({"ok": False, "error": str(e)}, status=400)
            return

        self.send_json({"ok": True, "run_id": new_run_id, "status": get_export_status()})

    def start_watch(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except ApplicationError:
            raise
        except (ValueError, json.JSONDecodeError):
            self.send_json({"ok": False, "error": "Invalid JSON payload"}, status=400)
            return

        try:
            start_watch_job(payload)
        except ApplicationError:
            raise
        except ValueError as e:
            self.send_json({"ok": False, "error": str(e)}, status=400)
            return
        except OSError as e:
            self.send_json({"ok": False, "error": f"Cannot write .env: {e}"}, status=500)
            return

        self.send_json({"ok": True, "watch": get_watch_status()})

    def stop_watch(self):
        stop_watch_job()
        self.send_json({"ok": True, "watch": get_watch_status()})

    def serve_data_file(self, request_path):
        relative = request_path.removeprefix("/data/")
        target = (DATA_DIR / relative).resolve()

        try:
            relative_parts = target.relative_to(DATA_DIR.resolve()).parts
        except ApplicationError:
            raise
        except ValueError:
            self.send_error(403, "Forbidden")
            return
        if not relative_parts or relative_parts[0] not in {"raw", "content", "analysis"}:
            self.send_error(403, "Forbidden")
            return

        if not target.is_file():
            self.send_error(404, "Not found")
            return

        self.serve_file(target, self.guess_type(str(target)))

    def serve_web_file(self, request_path):
        relative = request_path.removeprefix("/web/")
        target = (WEB_DIR / relative).resolve()
        web_dir = WEB_DIR.resolve()

        try:
            target.relative_to(web_dir)
        except ApplicationError:
            raise
        except ValueError:
            self.send_error(403, "Forbidden")
            return

        if not target.is_file():
            self.send_error(404, "Not found")
            return

        self.serve_file(target, self.guess_type(str(target)))

    def serve_file(self, path, content_type):
        try:
            data = path.read_bytes()
        except ApplicationError:
            raise
        except OSError:
            self.send_error(404, "Not found")
            return

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, payload, status=200):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format, *args):
        print(f"{self.client_address[0]} - {format % args}")


def main():
    ensure_env_file()
    reconcile_incomplete_scheduler_runs()
    server = ThreadingHTTPServer((HOST, PORT), DashboardHandler)
    print(f"Dashboard is running on http://localhost:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()

import json
import os
import subprocess
import sys
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from analytics.export_summary import extract_channel_from_export_name, summarize_export_posts
from version import APP_VERSION


HOST = "0.0.0.0"
PORT = 9595
ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "web"
INDEX_FILE = WEB_DIR / "comments_dashboard.html"
DATA_DIR = ROOT / "data"
ENV_FILE = ROOT / ".env"
CONFIG_KEYS = [
    "API_ID",
    "API_HASH",
    "CHANNEL",
    "TELEGRAM_SESSION",
    "OUTPUT_FILE",
    "POST_LIMIT",
    "INCREMENTAL_LOOKBACK_POSTS",
    "POSTS_PAUSE_SECONDS",
    "POSTS_PAUSE_AFTER_POSTS",
    "POSTGRES_HOST",
    "POSTGRES_PORT",
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_TABLE",
    "LLM_ENDPOINT",
    "LLM_MODEL",
]
INT_CONFIG_KEYS = {
    "API_ID",
    "POST_LIMIT",
    "INCREMENTAL_LOOKBACK_POSTS",
    "POSTS_PAUSE_SECONDS",
    "POSTS_PAUSE_AFTER_POSTS",
    "POSTGRES_PORT",
}
EXPORT_JOB = {
    "running": False,
    "returncode": None,
    "started_at": None,
    "finished_at": None,
    "command": [],
    "lines": [],
    "current_channel": None,
    "completed_channels": [],
    "failed_channels": [],
    "last_error": None,
    "summary": None,
}
EXPORT_LOCK = threading.Lock()
SCHEDULER = {
    "enabled": False,
    "interval_minutes": None,
    "channels": "",
    "payload": None,
    "thread": None,
    "stop_event": None,
    "started_at": None,
    "last_run_at": None,
    "last_skip_at": None,
    "next_run_at": None,
    "runs_started": 0,
    "runs_skipped": 0,
    "last_error": None,
    "lines": [],
}
SCHEDULER_LOCK = threading.Lock()


class DashboardHandler(SimpleHTTPRequestHandler):
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

        if path.startswith("/api/export/") and path.endswith("/summary"):
            file_name = path.removeprefix("/api/export/").removesuffix("/summary")
            try:
                self.send_json(get_export_summary(unquote(file_name)))
            except (FileNotFoundError, ValueError, OSError, json.JSONDecodeError) as e:
                self.send_json({"ok": False, "error": str(e)}, status=404)
            return

        if path == "/api/export/status":
            self.send_json(get_export_status())
            return

        if path == "/api/scheduler/status":
            self.send_json(get_scheduler_status())
            return

        self.send_error(404, "Not found")

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

        self.send_error(404, "Not found")

    def start_export(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except (ValueError, json.JSONDecodeError):
            self.send_json({"ok": False, "error": "Invalid JSON payload"}, status=400)
            return

        try:
            start_export_job(payload)
        except RuntimeError as e:
            self.send_json({"ok": False, "error": str(e)}, status=409)
            return
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
        except (ValueError, json.JSONDecodeError):
            self.send_json({"ok": False, "error": "Invalid JSON payload"}, status=400)
            return

        try:
            config = save_config_values(payload)
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
        except (ValueError, json.JSONDecodeError):
            self.send_json({"ok": False, "error": "Invalid JSON payload"}, status=400)
            return

        try:
            start_scheduler_job(payload)
        except RuntimeError as e:
            self.send_json({"ok": False, "error": str(e)}, status=409)
            return
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

    def serve_data_file(self, request_path):
        relative = request_path.removeprefix("/data/")
        target = (DATA_DIR / relative).resolve()

        if not str(target).startswith(str(DATA_DIR.resolve())):
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


def start_export_job(payload):
    if payload.get("config") is not None:
        save_config_values(payload["config"])

    export_format = payload.get("format") or "json"

    if export_format not in {"json", "csv", "postgresql", "parquet"}:
        raise ValueError("Unsupported export format")

    channel = str(payload.get("channel") or os.getenv("CHANNEL", "")).strip()

    if not parse_channel_list(channel):
        raise ValueError("At least one channel is required")

    command = [sys.executable, "main.py", "export", export_format]

    if payload.get("download_media"):
        command.append("--download-media")

    if payload.get("anonymize"):
        command.append("--anonymize")

    if payload.get("incremental"):
        command.append("--incremental")

    env = os.environ.copy()
    env["CHANNEL"] = channel
    env["PYTHONUNBUFFERED"] = "1"

    with EXPORT_LOCK:
        if EXPORT_JOB["running"]:
            raise RuntimeError("Export is already running")

        EXPORT_JOB.update({
            "running": True,
            "returncode": None,
            "started_at": time.time(),
            "finished_at": None,
            "command": command,
            "lines": [f"Starting export for channel(s) {channel}: {' '.join(command)}"],
            "current_channel": None,
            "completed_channels": [],
            "failed_channels": [],
            "last_error": None,
            "summary": None,
        })

    try:
        process = subprocess.Popen(
            command,
            cwd=str(ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as e:
        with EXPORT_LOCK:
            EXPORT_JOB["running"] = False
            EXPORT_JOB["returncode"] = -1
            EXPORT_JOB["finished_at"] = time.time()
            EXPORT_JOB["last_error"] = str(e)
            EXPORT_JOB["lines"].append(f"Failed to start export: {e}")
        raise RuntimeError(f"Failed to start export: {e}") from e

    thread = threading.Thread(target=watch_export_process, args=(process,), daemon=True)
    thread.start()


def build_export_payload(payload):
    export_format = payload.get("format") or "json"

    if export_format not in {"json", "csv", "postgresql", "parquet"}:
        raise ValueError("Unsupported export format")

    channel = str(payload.get("channel") or os.getenv("CHANNEL", "")).strip()

    if not parse_channel_list(channel):
        raise ValueError("At least one channel is required")

    return {
        "channel": channel,
        "format": export_format,
        "download_media": bool(payload.get("download_media")),
        "anonymize": bool(payload.get("anonymize")),
        "incremental": bool(payload.get("incremental")),
        "config": payload.get("config"),
    }


def normalize_scheduler_payload(payload):
    if not isinstance(payload, dict):
        raise ValueError("Scheduler payload must be an object")

    try:
        interval_minutes = int(payload.get("interval_minutes"))
    except (TypeError, ValueError) as e:
        raise ValueError("Scheduler interval must be an integer number of minutes") from e

    if interval_minutes < 1:
        raise ValueError("Scheduler interval must be at least 1 minute")

    export_payload = build_export_payload(payload)
    return interval_minutes, export_payload


def append_scheduler_line(line):
    with SCHEDULER_LOCK:
        SCHEDULER["lines"].append(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {line}")
        SCHEDULER["lines"] = SCHEDULER["lines"][-120:]


def scheduler_loop(stop_event):
    while not stop_event.is_set():
        with SCHEDULER_LOCK:
            payload = dict(SCHEDULER["payload"] or {})
            interval_seconds = int(SCHEDULER["interval_minutes"] or 1) * 60
            SCHEDULER["next_run_at"] = time.time()

        if get_export_status()["running"]:
            with SCHEDULER_LOCK:
                SCHEDULER["last_skip_at"] = time.time()
                SCHEDULER["runs_skipped"] += 1
            append_scheduler_line("Skipped run because export is already running.")
        else:
            try:
                start_export_job(payload)
                with SCHEDULER_LOCK:
                    SCHEDULER["last_run_at"] = time.time()
                    SCHEDULER["runs_started"] += 1
                    SCHEDULER["last_error"] = None
                append_scheduler_line(f"Started scheduled export for channel(s) {payload['channel']}.")
            except Exception as e:
                with SCHEDULER_LOCK:
                    SCHEDULER["last_error"] = str(e)
                append_scheduler_line(f"Scheduled export failed to start: {e}")

        with SCHEDULER_LOCK:
            SCHEDULER["next_run_at"] = time.time() + interval_seconds

        if stop_event.wait(interval_seconds):
            break

    with SCHEDULER_LOCK:
        if SCHEDULER.get("stop_event") is stop_event:
            SCHEDULER["lines"].append(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} Scheduler stopped.")
            SCHEDULER["lines"] = SCHEDULER["lines"][-120:]


def start_scheduler_job(payload):
    interval_minutes, export_payload = normalize_scheduler_payload(payload)

    if export_payload.get("config"):
        save_config_values(export_payload["config"])

    stop_event = threading.Event()
    thread = threading.Thread(target=scheduler_loop, args=(stop_event,), daemon=True)

    with SCHEDULER_LOCK:
        if SCHEDULER["enabled"]:
            raise RuntimeError("Scheduler is already running")

        SCHEDULER.update({
            "enabled": True,
            "interval_minutes": interval_minutes,
            "channels": export_payload["channel"],
            "payload": export_payload,
            "thread": thread,
            "stop_event": stop_event,
            "started_at": time.time(),
            "last_run_at": None,
            "last_skip_at": None,
            "next_run_at": time.time(),
            "runs_started": 0,
            "runs_skipped": 0,
            "last_error": None,
            "lines": [],
        })

    append_scheduler_line(
        f"Scheduler started for channel(s) {export_payload['channel']} every {interval_minutes} minute(s)."
    )
    thread.start()


def stop_scheduler_job():
    with SCHEDULER_LOCK:
        stop_event = SCHEDULER.get("stop_event")

        if stop_event:
            stop_event.set()

        SCHEDULER["enabled"] = False
        SCHEDULER["next_run_at"] = None


def get_scheduler_status():
    with SCHEDULER_LOCK:
        return {
            "enabled": SCHEDULER["enabled"],
            "interval_minutes": SCHEDULER["interval_minutes"],
            "channels": SCHEDULER["channels"],
            "started_at": SCHEDULER["started_at"],
            "last_run_at": SCHEDULER["last_run_at"],
            "last_skip_at": SCHEDULER["last_skip_at"],
            "next_run_at": SCHEDULER["next_run_at"],
            "runs_started": SCHEDULER["runs_started"],
            "runs_skipped": SCHEDULER["runs_skipped"],
            "last_error": SCHEDULER["last_error"],
            "lines": list(SCHEDULER["lines"]),
        }


def parse_channel_list(value):
    return [
        item.strip()
        for item in value.replace("\n", ",").replace(";", ",").split(",")
        if item.strip()
    ]


def resolve_raw_json_file(file_name):
    if not file_name or Path(file_name).name != file_name:
        raise ValueError("Export file name must not contain path separators")

    path = (DATA_DIR / "raw" / file_name).resolve()
    raw_dir = (DATA_DIR / "raw").resolve()

    try:
        path.relative_to(raw_dir)
    except ValueError as e:
        raise ValueError(f"Path must stay under {raw_dir}") from e

    if path.suffix.lower() != ".json":
        raise ValueError("Only JSON exports are supported")

    if not path.is_file():
        raise FileNotFoundError(f"Export file not found: {file_name}")

    return path


def load_export_posts(file_name):
    path = resolve_raw_json_file(file_name)

    with path.open("r", encoding="utf-8") as f:
        posts = json.load(f)

    if not isinstance(posts, list):
        raise ValueError(f"Export JSON must contain a list of posts: {file_name}")

    return path, posts


def list_export_files(sort_by="date"):
    raw_dir = DATA_DIR / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    items = []

    for path in raw_dir.glob("*.json"):
        stat = path.stat()
        items.append({
            "file": path.name,
            "channel": extract_channel_from_export_name(path.name),
            "size_bytes": stat.st_size,
            "modified_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(stat.st_mtime)),
            "url": f"/data/raw/{path.name}",
        })

    if sort_by == "channel":
        items = sorted(items, key=lambda item: item["modified_at"], reverse=True)
        return sorted(items, key=lambda item: item["channel"].casefold())

    return sorted(items, key=lambda item: item["modified_at"], reverse=True)


def get_export_summary(file_name):
    path, posts = load_export_posts(file_name)
    stat = path.stat()
    summary = summarize_export_posts(posts)
    summary.update({
        "ok": True,
        "file": path.name,
        "channel": extract_channel_from_export_name(path.name),
        "size_bytes": stat.st_size,
        "modified_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(stat.st_mtime)),
        "url": f"/data/raw/{path.name}",
    })
    return summary


def parse_env_file(path=ENV_FILE):
    values = {}

    if not path.exists():
        return values

    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()

        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue

        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key:
            values[key] = value

    return values


def read_config():
    file_values = parse_env_file()
    config = {}

    for key in CONFIG_KEYS:
        config[key] = file_values.get(key, os.getenv(key, ""))

    return config


def normalize_config_payload(payload):
    if not isinstance(payload, dict):
        raise ValueError("Config payload must be an object")

    normalized = {}

    for key in CONFIG_KEYS:
        if key not in payload:
            continue

        value = "" if payload[key] is None else str(payload[key]).strip()

        if "\n" in value or "\r" in value:
            raise ValueError(f"{key} cannot contain new lines")

        if key in INT_CONFIG_KEYS and value:
            try:
                int(value)
            except ValueError as e:
                raise ValueError(f"{key} must be an integer") from e

        normalized[key] = value

    return normalized


def save_config_values(payload):
    updates = normalize_config_payload(payload)

    if not updates:
        return read_config()

    lines = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
    seen = set()
    updated_lines = []

    for line in lines:
        stripped = line.strip()

        if not stripped or stripped.startswith("#") or "=" not in stripped:
            updated_lines.append(line)
            continue

        key = stripped.split("=", 1)[0].strip()

        if key in updates:
            updated_lines.append(f"{key}={updates[key]}")
            seen.add(key)
        else:
            updated_lines.append(line)

    if updated_lines and updated_lines[-1].strip():
        updated_lines.append("")

    for key in CONFIG_KEYS:
        if key in updates and key not in seen:
            updated_lines.append(f"{key}={updates[key]}")

    ENV_FILE.write_text("\n".join(updated_lines).rstrip() + "\n", encoding="utf-8")

    for key, value in updates.items():
        os.environ[key] = value

    return read_config()


def watch_export_process(process):
    assert process.stdout is not None

    for line in process.stdout:
        append_export_line(line.rstrip())

    returncode = process.wait()

    with EXPORT_LOCK:
        EXPORT_JOB["running"] = False
        EXPORT_JOB["returncode"] = returncode
        EXPORT_JOB["finished_at"] = time.time()
        EXPORT_JOB["lines"].append(f"Export finished with code {returncode}")


def append_export_line(line):
    with EXPORT_LOCK:
        EXPORT_JOB["lines"].append(line)
        EXPORT_JOB["lines"] = EXPORT_JOB["lines"][-500:]
        update_export_status_from_line(line)


def update_export_status_from_line(line):
    if line.startswith("Channel:"):
        EXPORT_JOB["current_channel"] = line.removeprefix("Channel:").strip()
        return

    if line.startswith("CHANNEL_STATUS "):
        payload = parse_status_payload(line, "CHANNEL_STATUS ")

        if not payload:
            return

        channel = payload.get("channel")

        if payload.get("ok"):
            if channel and channel not in EXPORT_JOB["completed_channels"]:
                EXPORT_JOB["completed_channels"].append(channel)
        elif channel and channel not in EXPORT_JOB["failed_channels"]:
            EXPORT_JOB["failed_channels"].append(channel)

        errors = payload.get("errors") or []

        if errors:
            EXPORT_JOB["last_error"] = errors[-1]

        return

    if line.startswith("EXPORT_SUMMARY "):
        payload = parse_status_payload(line, "EXPORT_SUMMARY ")

        if payload:
            EXPORT_JOB["summary"] = payload
            failed_channels = payload.get("failed_channels") or []
            EXPORT_JOB["failed_channels"] = failed_channels


def parse_status_payload(line, prefix):
    try:
        return json.loads(line.removeprefix(prefix))
    except json.JSONDecodeError:
        return None


def get_export_status():
    with EXPORT_LOCK:
        return {
            "running": EXPORT_JOB["running"],
            "returncode": EXPORT_JOB["returncode"],
            "started_at": EXPORT_JOB["started_at"],
            "finished_at": EXPORT_JOB["finished_at"],
            "command": EXPORT_JOB["command"],
            "lines": EXPORT_JOB["lines"],
            "current_channel": EXPORT_JOB["current_channel"],
            "completed_channels": EXPORT_JOB["completed_channels"],
            "failed_channels": EXPORT_JOB["failed_channels"],
            "last_error": EXPORT_JOB["last_error"],
            "summary": EXPORT_JOB["summary"],
        }


def main():
    server = ThreadingHTTPServer((HOST, PORT), DashboardHandler)
    print(f"Dashboard is running on http://localhost:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()

import json
import os
import subprocess
import sys
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from version import APP_VERSION


HOST = "0.0.0.0"
PORT = 9595
ROOT = Path(__file__).resolve().parent
INDEX_FILE = ROOT / "comments_dashboard.html"
DATA_DIR = ROOT / "data"
ENV_FILE = ROOT / ".env"
CONFIG_KEYS = [
    "API_ID",
    "API_HASH",
    "CHANNEL",
    "OUTPUT_FILE",
    "POST_LIMIT",
    "PAUSE_AFTER_500_POSTS_SECONDS",
    "PAUSE_AFTER_1000_POSTS_SECONDS",
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
    "PAUSE_AFTER_500_POSTS_SECONDS",
    "PAUSE_AFTER_1000_POSTS_SECONDS",
    "POSTGRES_PORT",
}
EXPORT_JOB = {
    "running": False,
    "returncode": None,
    "started_at": None,
    "finished_at": None,
    "command": [],
    "lines": [],
}
EXPORT_LOCK = threading.Lock()


class DashboardHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        if path in ("/", "/index.html", "/comments_dashboard.html"):
            self.serve_file(INDEX_FILE, "text/html; charset=utf-8")
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

        if path == "/api/export/status":
            self.send_json(get_export_status())
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
    if "config" in payload:
        save_config_values(payload["config"])

    export_format = payload.get("format") or "json"

    if export_format not in {"json", "csv", "postgresql", "parquet"}:
        raise ValueError("Unsupported export format")

    channel = str(payload.get("channel") or os.getenv("CHANNEL", "")).strip()

    if not channel:
        raise ValueError("Channel is required")

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
            "lines": [f"Starting export for channel {channel}: {' '.join(command)}"],
        })

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

    thread = threading.Thread(target=watch_export_process, args=(process,), daemon=True)
    thread.start()


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


def get_export_status():
    with EXPORT_LOCK:
        return {
            "running": EXPORT_JOB["running"],
            "returncode": EXPORT_JOB["returncode"],
            "started_at": EXPORT_JOB["started_at"],
            "finished_at": EXPORT_JOB["finished_at"],
            "command": EXPORT_JOB["command"],
            "lines": EXPORT_JOB["lines"],
        }


def main():
    server = ThreadingHTTPServer((HOST, PORT), DashboardHandler)
    print(f"Dashboard is running on http://localhost:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()

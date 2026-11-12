"""Export and Watch subprocess lifecycle, output parsing and status."""
from errors import ProcessAlreadyRunningError, ProcessStartError
import json
import os
import subprocess
import sys
import threading
import time
from services.paths import ROOT
from services.configuration import save_config_values
from services.scheduler_history import (
    now_iso, update_scheduler_run, classify_scheduler_error, finish_scheduler_run_from_export,
)

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
    "scheduler_run_id": None,
    "channel_summaries": [],
}
EXPORT_LOCK = threading.Lock()


WATCH_JOB = {
    "running": False,
    "returncode": None,
    "started_at": None,
    "finished_at": None,
    "command": [],
    "process": None,
    "channels": "",
    "lines": [],
    "updates": [],
    "last_error": None,
}
WATCH_LOCK = threading.Lock()


def start_export_job(payload, scheduler_run_id=None):
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
            raise ProcessAlreadyRunningError("Export is already running")

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
            "scheduler_run_id": scheduler_run_id,
            "channel_summaries": [],
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
        update_scheduler_run(
            scheduler_run_id,
            status="FAILED",
            finished_at=now_iso(),
            returncode=-1,
            error=classify_scheduler_error(ProcessStartError(f"Failed to start export: {e}")),
        )
        raise ProcessStartError(f"Failed to start export: {e}") from e

    update_scheduler_run(
        scheduler_run_id,
        status="RUNNING",
        started_at=now_iso(),
        command=command,
    )

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


def normalize_watch_payload(payload):
    if not isinstance(payload, dict):
        raise ValueError("Watch payload must be an object")

    channel = str(payload.get("channel") or os.getenv("CHANNEL", "")).strip()

    if not parse_channel_list(channel):
        raise ValueError("At least one channel is required")

    try:
        poll_interval = int(payload.get("poll_interval") or 30)
        refresh_active_posts = int(payload.get("refresh_active_posts") or 20)
    except (TypeError, ValueError) as e:
        raise ValueError("Watch intervals must be integer values") from e

    if poll_interval < 5:
        raise ValueError("Watch poll interval must be at least 5 seconds")

    if refresh_active_posts < 1:
        raise ValueError("Watch active posts must be at least 1")

    return {
        "channel": channel,
        "download_media": bool(payload.get("download_media")),
        "anonymize": bool(payload.get("anonymize")),
        "poll_interval": poll_interval,
        "refresh_active_posts": refresh_active_posts,
        "config": payload.get("config"),
    }


def start_watch_job(payload):
    watch_payload = normalize_watch_payload(payload)

    if watch_payload.get("config"):
        save_config_values(watch_payload["config"])

    command = [
        sys.executable,
        "main.py",
        "watch",
        "--poll-interval",
        str(watch_payload["poll_interval"]),
        "--refresh-active-posts",
        str(watch_payload["refresh_active_posts"]),
    ]

    if watch_payload["download_media"]:
        command.append("--download-media")

    if watch_payload["anonymize"]:
        command.append("--anonymize")

    env = os.environ.copy()
    env["CHANNEL"] = watch_payload["channel"]
    env["PYTHONUNBUFFERED"] = "1"

    with WATCH_LOCK:
        if WATCH_JOB["running"]:
            raise ProcessAlreadyRunningError("Watch mode is already running")

        WATCH_JOB.update({
            "running": True,
            "returncode": None,
            "started_at": time.time(),
            "finished_at": None,
            "command": command,
            "process": None,
            "channels": watch_payload["channel"],
            "lines": [f"Starting watch for channel(s) {watch_payload['channel']}: {' '.join(command)}"],
            "updates": [],
            "last_error": None,
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
        with WATCH_LOCK:
            WATCH_JOB["running"] = False
            WATCH_JOB["returncode"] = -1
            WATCH_JOB["finished_at"] = time.time()
            WATCH_JOB["last_error"] = str(e)
            WATCH_JOB["lines"].append(f"Failed to start watch: {e}")
        raise ProcessStartError(f"Failed to start watch: {e}") from e

    with WATCH_LOCK:
        WATCH_JOB["process"] = process

    thread = threading.Thread(target=watch_watch_process, args=(process,), daemon=True)
    thread.start()


def stop_watch_job():
    with WATCH_LOCK:
        process = WATCH_JOB.get("process")

    if process and process.poll() is None:
        process.terminate()

    with WATCH_LOCK:
        WATCH_JOB["running"] = False
        WATCH_JOB["finished_at"] = time.time()
        WATCH_JOB["lines"].append("Watch stop requested.")
        WATCH_JOB["lines"] = WATCH_JOB["lines"][-500:]


def watch_watch_process(process):
    assert process.stdout is not None

    for line in process.stdout:
        append_watch_line(line.rstrip())

    returncode = process.wait()

    with WATCH_LOCK:
        WATCH_JOB["running"] = False
        WATCH_JOB["returncode"] = returncode
        WATCH_JOB["finished_at"] = time.time()
        WATCH_JOB["lines"].append(f"Watch finished with code {returncode}")


def append_watch_line(line):
    with WATCH_LOCK:
        WATCH_JOB["lines"].append(line)
        WATCH_JOB["lines"] = WATCH_JOB["lines"][-500:]

        if line.startswith("WATCH_UPDATE "):
            payload = parse_status_payload(line, "WATCH_UPDATE ")

            if payload:
                WATCH_JOB["updates"].append(payload)
                WATCH_JOB["updates"] = WATCH_JOB["updates"][-120:]

                if payload.get("error"):
                    WATCH_JOB["last_error"] = payload["error"]


def get_watch_status():
    with WATCH_LOCK:
        process = WATCH_JOB.get("process")

        if process and WATCH_JOB["running"] and process.poll() is not None:
            WATCH_JOB["running"] = False
            WATCH_JOB["returncode"] = process.poll()
            WATCH_JOB["finished_at"] = time.time()

        return {
            "running": WATCH_JOB["running"],
            "returncode": WATCH_JOB["returncode"],
            "started_at": WATCH_JOB["started_at"],
            "finished_at": WATCH_JOB["finished_at"],
            "command": WATCH_JOB["command"],
            "channels": WATCH_JOB["channels"],
            "lines": list(WATCH_JOB["lines"]),
            "updates": list(WATCH_JOB["updates"]),
            "last_error": WATCH_JOB["last_error"],
        }


def parse_channel_list(value):
    return [
        item.strip()
        for item in value.replace("\n", ",").replace(";", ",").split(",")
        if item.strip()
    ]


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
        export_snapshot = {
            "lines": list(EXPORT_JOB["lines"]),
            "completed_channels": list(EXPORT_JOB["completed_channels"]),
            "failed_channels": list(EXPORT_JOB["failed_channels"]),
            "last_error": EXPORT_JOB["last_error"],
            "summary": EXPORT_JOB["summary"],
            "scheduler_run_id": EXPORT_JOB["scheduler_run_id"],
            "channel_summaries": list(EXPORT_JOB["channel_summaries"]),
        }

    finish_scheduler_run_from_export(
        export_snapshot.get("scheduler_run_id"),
        returncode,
        export_snapshot,
    )


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
        EXPORT_JOB["channel_summaries"].append(payload)

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

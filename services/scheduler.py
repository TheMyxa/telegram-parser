"""In-memory scheduler coordinating exports and persisted run history."""
import logging
from errors import ApplicationError, ProcessAlreadyRunningError
import threading
import time
from services.configuration import save_config_values
from services.processes import build_export_payload, get_export_status, start_export_job
from services.scheduler_history import (
    read_scheduler_run, create_scheduler_run, update_scheduler_run, classify_scheduler_error, now_iso,
)

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


def retry_scheduler_run(run_id):
    record = read_scheduler_run(run_id)
    flags = record.get("flags") or {}
    payload = {
        "channel": record.get("channels"),
        "format": record.get("format") or "json",
        "download_media": bool(flags.get("download_media")),
        "anonymize": bool(flags.get("anonymize")),
        "incremental": bool(flags.get("incremental")),
    }

    if not payload["channel"]:
        raise ValueError("Scheduler run has no channel to retry")

    retry_run_id = create_scheduler_run(payload)
    start_export_job(payload, scheduler_run_id=retry_run_id)
    return retry_run_id


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
            run_id = create_scheduler_run(
                payload,
                status="SKIPPED",
                reason="Export is already running when scheduled run is due.",
            )
            with SCHEDULER_LOCK:
                SCHEDULER["last_skip_at"] = time.time()
                SCHEDULER["runs_skipped"] += 1
            append_scheduler_line(f"Skipped run {run_id} because export is already running.")
        else:
            run_id = create_scheduler_run(payload)
            try:
                start_export_job(payload, scheduler_run_id=run_id)
                with SCHEDULER_LOCK:
                    SCHEDULER["last_run_at"] = time.time()
                    SCHEDULER["runs_started"] += 1
                    SCHEDULER["last_error"] = None
                append_scheduler_line(f"Started scheduled export {run_id} for channel(s) {payload['channel']}.")
            except Exception as e:
                if not isinstance(e, ApplicationError):
                    logging.getLogger(__name__).exception("Unexpected scheduler failure")
                with SCHEDULER_LOCK:
                    SCHEDULER["last_error"] = str(e)
                update_scheduler_run(
                    run_id,
                    status="FAILED",
                    finished_at=now_iso(),
                    error=classify_scheduler_error(e),
                )
                append_scheduler_line(f"Scheduled export {run_id} failed to start: {e}")

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
            raise ProcessAlreadyRunningError("Scheduler is already running")

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

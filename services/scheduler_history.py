"""Persistent scheduler history and export outcome classification."""
import json
from errors import ApplicationError
import re
import time
import uuid
from services.paths import SCHEDULER_HISTORY_DIR
from storage.sqlite_store import (
    upsert_scheduler_run, read_scheduler_run_record, list_scheduler_run_records,
    count_scheduler_run_records, get_scheduler_run_stats,
)


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())


def scheduler_history_path(run_id):
    if not re.match(r"^[A-Za-z0-9_.-]+$", run_id or ""):
        raise ValueError("Invalid scheduler run id")

    return SCHEDULER_HISTORY_DIR / f"{run_id}.json"


def write_scheduler_run(record):
    upsert_scheduler_run(record)


def read_scheduler_run(run_id):
    record = read_scheduler_run_record(run_id)

    if record:
        return record

    path = scheduler_history_path(run_id)

    if not path.is_file():
        raise FileNotFoundError(f"Scheduler run not found: {run_id}")

    with path.open("r", encoding="utf-8") as f:
        record = json.load(f)

    upsert_scheduler_run(record)
    return record


def import_scheduler_json_history():
    SCHEDULER_HISTORY_DIR.mkdir(parents=True, exist_ok=True)

    for path in SCHEDULER_HISTORY_DIR.glob("*.json"):
        try:
            with path.open("r", encoding="utf-8") as f:
                record = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue

        if isinstance(record, dict) and record.get("id"):
            try:
                upsert_scheduler_run(record)
            except ValueError:
                continue


def summarize_scheduler_run(record):
    return {
        "id": record.get("id"),
        "status": record.get("status"),
        "created_at": record.get("created_at"),
        "scheduled_for": record.get("scheduled_for"),
        "started_at": record.get("started_at"),
        "finished_at": record.get("finished_at"),
        "channels": record.get("channels"),
        "format": record.get("format"),
        "posts_processed": record.get("posts_processed"),
        "channels_ok": record.get("channels_ok"),
        "channels_failed": record.get("channels_failed"),
        "error": record.get("error"),
    }


def list_scheduler_runs(limit=50, offset=0, status=None, channel=None):
    import_scheduler_json_history()
    records = list_scheduler_run_records(limit, offset, status, channel)
    return [summarize_scheduler_run(record) for record in records]


def list_scheduler_runs_response(limit=50, offset=0, status=None, channel=None):
    import_scheduler_json_history()
    runs = [summarize_scheduler_run(record) for record in list_scheduler_run_records(limit, offset, status, channel)]
    total = count_scheduler_run_records(status, channel)
    return {
        "ok": True,
        "runs": runs,
        "pagination": {
            "limit": limit,
            "offset": offset,
            "total": total,
            "next_offset": offset + limit if offset + limit < total else None,
        },
        "stats": get_scheduler_run_stats(status, channel),
    }


def list_scheduler_run_details(status=None, channel=None):
    import_scheduler_json_history()
    total = count_scheduler_run_records(status, channel)
    return list_scheduler_run_records(max(1, min(total or 1, 10000)), 0, status, channel)


def list_scheduler_runs_from_json(limit=50):
    SCHEDULER_HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    items = []

    for path in sorted(SCHEDULER_HISTORY_DIR.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        try:
            with path.open("r", encoding="utf-8") as f:
                record = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue

        items.append({
            "id": record.get("id") or path.stem,
            "status": record.get("status"),
            "created_at": record.get("created_at"),
            "scheduled_for": record.get("scheduled_for"),
            "started_at": record.get("started_at"),
            "finished_at": record.get("finished_at"),
            "channels": record.get("channels"),
            "format": record.get("format"),
            "posts_processed": record.get("posts_processed"),
            "channels_ok": record.get("channels_ok"),
            "channels_failed": record.get("channels_failed"),
            "error": record.get("error"),
        })

        if len(items) >= limit:
            break

    return items


def reconcile_incomplete_scheduler_runs():
    import_scheduler_json_history()

    for record in list_scheduler_run_details():
        if record.get("status") not in {"QUEUED", "RUNNING"}:
            continue

        record.update({
            "status": "CANCELLED",
            "finished_at": now_iso(),
            "error": {
                "type": "DashboardRestarted",
                "message": "Dashboard process restarted before this scheduled run completed.",
            },
        })
        write_scheduler_run(record)


def create_scheduler_run(payload, status="QUEUED", reason=None):
    run_id = f"scheduler_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    record = {
        "id": run_id,
        "status": status,
        "created_at": now_iso(),
        "scheduled_for": now_iso(),
        "started_at": None,
        "finished_at": now_iso() if status in {"SKIPPED", "FAILED", "CANCELLED"} else None,
        "channels": payload.get("channel"),
        "format": payload.get("format"),
        "flags": {
            "download_media": bool(payload.get("download_media")),
            "anonymize": bool(payload.get("anonymize")),
            "incremental": bool(payload.get("incremental")),
        },
        "command": [],
        "returncode": None,
        "posts_processed": 0,
        "channels_ok": 0,
        "channels_failed": 0,
        "completed_channels": [],
        "failed_channels": [],
        "summary": None,
        "error": classify_scheduler_error(reason) if reason else None,
        "lines": [],
    }
    write_scheduler_run(record)
    return run_id


def update_scheduler_run(run_id, **updates):
    if not run_id:
        return None

    try:
        record = read_scheduler_run(run_id)
    except FileNotFoundError:
        return None

    record.update(updates)
    write_scheduler_run(record)
    return record


def classify_scheduler_error(message):
    if not message:
        return None

    if isinstance(message, ApplicationError):
        return {"type": type(message).__name__, "code": message.code, "message": str(message)}

    text = str(message)
    flood_wait = re.search(r"FloodWaitError: Telegram requested wait for (\d+) seconds", text)

    if flood_wait:
        return {
            "type": "TelegramFloodWait",
            "message": text,
            "wait_seconds": int(flood_wait.group(1)),
        }

    if "Export is already running" in text:
        return {
            "type": "ExportAlreadyRunning",
            "message": text,
        }

    if "Missing required config value" in text:
        return {
            "type": "ConfigurationError",
            "message": text,
        }

    if "Failed to start export" in text:
        return {
            "type": "ProcessStartError",
            "message": text,
        }

    return {
        "type": "ExportError",
        "message": text,
    }


def finish_scheduler_run_from_export(run_id, returncode, export_snapshot):
    if not run_id:
        return

    summary = export_snapshot.get("summary") or {}
    failed_channels = export_snapshot.get("failed_channels") or summary.get("failed_channels") or []
    completed_channels = export_snapshot.get("completed_channels") or []
    channel_summaries = export_snapshot.get("channel_summaries") or []
    lines = export_snapshot.get("lines") or []
    last_error = export_snapshot.get("last_error")
    posts_processed = sum(int(item.get("posts_processed") or 0) for item in channel_summaries if isinstance(item, dict))

    if returncode == 0 and not failed_channels:
        status = "SUCCESS"
    elif returncode == 0:
        status = "PARTIAL"
    elif returncode in {-15, -9, 130}:
        status = "CANCELLED"
    elif completed_channels and failed_channels:
        status = "PARTIAL"
    else:
        status = "FAILED"

    update_scheduler_run(
        run_id,
        status=status,
        finished_at=now_iso(),
        returncode=returncode,
        posts_processed=posts_processed,
        channels_ok=summary.get("channels_ok", len(completed_channels)),
        channels_failed=summary.get("channels_failed", len(failed_channels)),
        completed_channels=completed_channels,
        failed_channels=failed_channels,
        channel_summaries=channel_summaries,
        summary=summary or None,
        error=classify_scheduler_error(last_error) if last_error else None,
        lines=lines[-120:],
    )

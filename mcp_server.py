import json
import os
import subprocess
import sys
import time
from pathlib import Path

from mcp.server.fastmcp import FastMCP


ROOT = Path(__file__).resolve().parent
RAW_DIR = ROOT / "data" / "raw"
ANALYSIS_DIR = ROOT / "data" / "analysis"
STATE_DIR = ROOT / "data" / "state"
ENV_FILE = ROOT / ".env"
SAFE_CONFIG_KEYS = {
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
    "POSTGRES_TABLE",
    "LLM_ENDPOINT",
    "LLM_MODEL",
}
SECRET_CONFIG_KEYS = {
    "API_ID",
    "API_HASH",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
}
EXPORT_PROCESS = {
    "process": None,
    "started_at": None,
    "command": None,
    "log_path": None,
}


mcp = FastMCP("telegram-parser")


def parse_env_file(path=ENV_FILE):
    values = {}

    if not path.exists():
        return values

    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()

        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue

        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")

    return values


def resolve_safe_file(base_dir, value):
    path = Path(value)

    if not path.is_absolute():
        path = base_dir / value

    resolved = path.resolve()
    base = base_dir.resolve()

    try:
        resolved.relative_to(base)
    except ValueError as e:
        raise ValueError(f"Path must stay under {base_dir}: {value}")

    if not resolved.is_file():
        raise FileNotFoundError(f"File not found: {value}")

    return resolved


def load_export(file_name):
    path = resolve_safe_file(RAW_DIR, file_name)

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError(f"Export JSON must contain a list of posts: {file_name}")

    return path, data


def iter_comments(posts):
    for post in posts:
        if not isinstance(post, dict):
            continue

        for comment in post.get("comments") or []:
            if isinstance(comment, dict):
                yield post, comment


def summarize_posts(posts):
    comments_count = 0
    reactions_count = 0
    users = set()

    for post in posts:
        if not isinstance(post, dict):
            continue

        for reaction in post.get("post_reactions") or []:
            reactions_count += int((reaction or {}).get("count") or 0)

        for comment in post.get("comments") or []:
            if not isinstance(comment, dict):
                continue

            comments_count += 1

            for reaction in comment.get("comment_reactions") or []:
                reactions_count += int((reaction or {}).get("count") or 0)

            user = comment.get("user") or {}
            user_id = user.get("user_id")

            if user_id:
                users.add(str(user_id))

    return {
        "posts_count": len(posts),
        "comments_count": comments_count,
        "unique_users_count": len(users),
        "reactions_count": reactions_count,
    }


@mcp.tool()
def get_config_safe() -> dict:
    """Return non-secret .env configuration with secret keys masked."""
    values = parse_env_file()
    safe = {key: values.get(key, os.getenv(key, "")) for key in sorted(SAFE_CONFIG_KEYS)}

    for key in sorted(SECRET_CONFIG_KEYS):
        if values.get(key) or os.getenv(key):
            safe[key] = "***"

    return safe


@mcp.tool()
def list_exports() -> list[dict]:
    """List JSON export files from data/raw with basic file metadata."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    items = []

    for path in sorted(RAW_DIR.glob("*.json")):
        stat = path.stat()
        items.append({
            "file": path.name,
            "size_bytes": stat.st_size,
            "modified_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(stat.st_mtime)),
        })

    return items


@mcp.tool()
def get_export_summary(file_name: str) -> dict:
    """Return post/comment/user/reaction counts for one export JSON file."""
    path, posts = load_export(file_name)
    summary = summarize_posts(posts)
    summary["file"] = path.name
    return summary


@mcp.tool()
def search_comments(file_name: str, query: str, limit: int = 20) -> list[dict]:
    """Search comments by text in one export JSON file."""
    _, posts = load_export(file_name)
    needle = query.casefold()
    results = []

    if not needle:
        return results

    for post, comment in iter_comments(posts):
        text = str(comment.get("comment_text") or "")

        if needle not in text.casefold():
            continue

        user = comment.get("user") or {}
        results.append({
            "post_id": post.get("post_id"),
            "comment_id": comment.get("comment_id"),
            "comment_date": comment.get("comment_date"),
            "comment_text": text,
            "username": user.get("username"),
            "first_name": user.get("first_name"),
            "comment_link": comment.get("comment_link"),
            "post_link": post.get("post_link"),
        })

        if len(results) >= limit:
            break

    return results


@mcp.tool()
def get_post(file_name: str, post_id: int) -> dict:
    """Return one post by post_id from an export JSON file."""
    _, posts = load_export(file_name)

    for post in posts:
        if isinstance(post, dict) and post.get("post_id") == post_id:
            return post

    raise ValueError(f"Post not found: {post_id}")


@mcp.tool()
def list_analysis_files() -> list[dict]:
    """List analysis JSON files from data/analysis."""
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    items = []

    for path in sorted(ANALYSIS_DIR.glob("*.json")):
        stat = path.stat()
        items.append({
            "file": path.name,
            "size_bytes": stat.st_size,
            "modified_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(stat.st_mtime)),
        })

    return items


@mcp.tool()
def read_analysis(file_name: str) -> dict:
    """Read one analysis JSON file from data/analysis."""
    path = resolve_safe_file(ANALYSIS_DIR, file_name)

    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


@mcp.tool()
def run_analysis(file_name: str, limit: int | None = None, language: str = "ru", prompt_file: str | None = None) -> dict:
    """Run LLM analysis for an export file and return process output."""
    command = [sys.executable, "main.py", "analyze", file_name]

    if limit is not None:
        command.extend(["--limit", str(limit)])

    if prompt_file:
        command.extend(["--prompt-file", prompt_file])
    elif language:
        command.extend(["--language", language])

    result = subprocess.run(
        command,
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )

    return {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


@mcp.tool()
def start_export(
    confirm: bool = False,
    export_format: str = "json",
    incremental: bool = True,
    download_media: bool = False,
    anonymize: bool = False,
) -> dict:
    """Start a Telegram export in the background. Requires confirm=true."""
    if not confirm:
        return {
            "started": False,
            "error": "Set confirm=true to start a live Telegram export.",
        }

    if EXPORT_PROCESS["process"] and EXPORT_PROCESS["process"].poll() is None:
        return {
            "started": False,
            "error": "An export process is already running.",
            "status": get_export_process_status(),
        }

    if export_format not in {"json", "csv", "postgresql", "parquet"}:
        raise ValueError(f"Unsupported export format: {export_format}")

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    log_path = STATE_DIR / f"mcp_export_{time.strftime('%Y%m%d_%H%M%S')}.log"
    command = [sys.executable, "main.py", "export", export_format]

    if incremental:
        command.append("--incremental")

    if download_media:
        command.append("--download-media")

    if anonymize:
        command.append("--anonymize")

    log_file = log_path.open("w", encoding="utf-8")
    process = subprocess.Popen(
        command,
        cwd=str(ROOT),
        stdout=log_file,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    log_file.close()

    EXPORT_PROCESS.update({
        "process": process,
        "started_at": time.time(),
        "command": command,
        "log_path": log_path,
    })

    return {
        "started": True,
        "pid": process.pid,
        "command": command,
        "log_path": str(log_path),
    }


@mcp.tool()
def get_export_process_status() -> dict:
    """Return status for the background export started via MCP."""
    process = EXPORT_PROCESS.get("process")

    if not process:
        return {
            "running": False,
            "returncode": None,
            "message": "No MCP export process has been started.",
        }

    log_path = EXPORT_PROCESS["log_path"]
    recent_log = []

    if log_path and Path(log_path).exists():
        recent_log = Path(log_path).read_text(encoding="utf-8", errors="replace").splitlines()[-80:]

    return {
        "running": process.poll() is None,
        "returncode": process.poll(),
        "pid": process.pid,
        "started_at": EXPORT_PROCESS["started_at"],
        "command": EXPORT_PROCESS["command"],
        "log_path": str(log_path) if log_path else None,
        "recent_log": recent_log,
    }


def main():
    mcp.run()


if __name__ == "__main__":
    main()

"""Export file access and indexing shared by CLI, HTTP and MCP.

Entrypoints choose their access policy: HTTP/MCP resolve paths inside approved
directories, while the CLI also accepts explicit paths outside data/raw.
"""
import json
import time
from pathlib import Path

from analytics.export_summary import extract_channel_from_export_name
from storage import sqlite_store
from storage.json_files import load_json_dataset
from errors import DatasetCorruptedError


def resolve_safe_file(base_dir, value):
    base_dir = Path(base_dir)
    path = Path(value)
    if not path.is_absolute():
        path = base_dir / path
    resolved = path.resolve()
    try:
        resolved.relative_to(base_dir.resolve())
    except ValueError as e:
        raise ValueError(f"Path must stay under {base_dir}: {value}") from e
    if not resolved.is_file():
        raise FileNotFoundError(f"File not found: {value}")
    return resolved


def load_posts(path):
    """Read legacy list-shaped exports without modifying malformed files."""
    path = Path(path)
    try:
        with path.open("r", encoding="utf-8") as stream:
            posts = json.load(stream)
    except (json.JSONDecodeError, UnicodeError) as error:
        raise DatasetCorruptedError("Export contains invalid JSON") from error
    if not isinstance(posts, list):
        raise DatasetCorruptedError("Export JSON must contain a list of posts")
    return posts


def ensure_index(path, posts=None, *, force=False):
    """Refresh stale SQLite data, including indexes that need FTS rebuilding."""
    path = Path(path)
    if not force:
        stat = path.stat()
        modified_at = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(stat.st_mtime))
        indexed = sqlite_store.get_indexed_export(path.name)
        if (
            indexed
            and indexed["modified_at"] == modified_at
            and indexed["size_bytes"] == stat.st_size
            and not sqlite_store.needs_fts_reindex(path.name)
        ):
            return
    if posts is None:
        posts = load_posts(path)
    sqlite_store.sync_export_file(
        path.name, extract_channel_from_export_name(path.name), posts, path,
    )


def index_paths(paths):
    """Explicit CLI reindex, retaining its existing damaged-file backup policy."""
    indexed = []
    for path in paths:
        path = Path(path)
        ensure_index(path, load_json_dataset(path), force=True)
        indexed.append(str(path))
    return indexed

"""Dashboard export queries and HTTP response adaptation."""
from errors import IndexUnavailableError
import json
import time
from pathlib import Path
from analytics.export_summary import extract_channel_from_export_name, summarize_export_posts
from analytics.period_compare import compare_periods
from services.paths import DATA_DIR
from services.exports import (
    load_posts,
    ensure_index,
    resolve_safe_file,
)
from storage.sqlite_store import (
    compare_periods as compare_periods_sqlite,
    get_export_charts as get_export_charts_sqlite,
    get_filtered_summary as get_filtered_summary_sqlite,
    get_export_summary as get_export_summary_sqlite,
    get_post as get_post_sqlite,
    list_indexed_exports,
    list_export_states,
    list_posts as list_posts_sqlite,
    search_all_comments,
)


def resolve_raw_json_file(file_name):
    if not file_name or Path(file_name).name != file_name:
        raise ValueError("Export file name must not contain path separators")

    raw_dir = (DATA_DIR / "raw").resolve()
    if Path(file_name).suffix.lower() != ".json":
        raise ValueError("Only JSON exports are supported")
    try:
        return resolve_safe_file(raw_dir, file_name)
    except FileNotFoundError as e:
        raise FileNotFoundError(f"Export file not found: {file_name}") from e


def load_export_posts(file_name):
    path = resolve_raw_json_file(file_name)
    return path, load_posts(path)


def ensure_sqlite_export_index(file_name, path=None, posts=None):
    ensure_index(path or resolve_raw_json_file(file_name), posts)


def ensure_all_sqlite_export_indexes():
    raw_dir = DATA_DIR / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    indexed = 0

    for path in raw_dir.glob("*.json"):
        try:
            ensure_sqlite_export_index(path.name, path)
            indexed += 1
        except (IndexUnavailableError, OSError, ValueError, json.JSONDecodeError) as e:
            print(f"SQLite index skipped for {path.name}: {e}")

    return indexed


def first_query_value(query, key, default=""):
    return (query.get(key) or [default])[0]


def search_indexed_comments(query):
    search_text = first_query_value(query, "q").strip()

    if not search_text:
        raise ValueError("Search query is required")

    try:
        limit = int(first_query_value(query, "limit", "50"))
    except ValueError as e:
        raise ValueError("Search limit must be an integer") from e

    limit = max(1, min(limit, 200))
    indexed_count = ensure_all_sqlite_export_indexes()
    results = search_all_comments(
        search_text,
        limit=limit,
        channel_key=first_query_value(query, "channel").strip() or None,
        date_from=first_query_value(query, "from").strip() or None,
        date_to=first_query_value(query, "to").strip() or None,
        user=first_query_value(query, "user").strip() or None,
    )

    return {
        "ok": True,
        "query": search_text,
        "indexed_count": indexed_count,
        "results": results,
    }


def list_export_files(sort_by="date"):
    raw_dir = DATA_DIR / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    current_files = {path.name for path in raw_dir.glob("*.json")}

    for path in sorted(raw_dir.glob("*.json")):
        try:
            ensure_sqlite_export_index(path.name, path)
        except (IndexUnavailableError, OSError, ValueError, json.JSONDecodeError) as e:
            print(f"SQLite export list index skipped for {path.name}: {e}")

    try:
        states = {record["channel_key"]: record for record in list_export_states()}
        items = [
            export_record_to_response(record, states.get(record["channel_key"]))
            for record in list_indexed_exports()
            if record["file_name"] in current_files
        ]
    except IndexUnavailableError as e:
        print(f"SQLite export list failed: {e}")
        items = []

    if not items and current_files:
        items = list_export_files_from_disk(raw_dir)

    if sort_by == "channel":
        items = sorted(items, key=lambda item: item["modified_at"], reverse=True)
        return sorted(items, key=lambda item: item["channel"].casefold())

    return sorted(items, key=lambda item: item["modified_at"], reverse=True)


def export_record_to_response(record, state=None):
    item = {
        "file": record["file_name"],
        "channel": record["channel_key"],
        "size_bytes": record["size_bytes"],
        "modified_at": record["modified_at"],
        "indexed_at": record["indexed_at"],
        "posts_count": record["posts_count"],
        "comments_count": record["comments_count"],
        "unique_users_count": record["unique_users_count"],
        "reactions_count": record["reactions_count"],
        "url": f"/data/raw/{record['file_name']}",
    }
    if state:
        item["export_state"] = state
    return item


def list_export_files_from_disk(raw_dir):
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

    return items


def get_export_summary(file_name):
    path = resolve_raw_json_file(file_name)
    stat = path.stat()
    try:
        ensure_sqlite_export_index(path.name, path)
        summary = get_export_summary_sqlite(path.name)
    except IndexUnavailableError as e:
        print(f"SQLite summary failed for {path.name}: {e}")
        summary = None

    if summary is None:
        _, posts = load_export_posts(path.name)
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


def get_export_charts(file_name):
    path = resolve_raw_json_file(file_name)
    try:
        ensure_sqlite_export_index(path.name, path)
        charts = get_export_charts_sqlite(path.name)
    except IndexUnavailableError as e:
        print(f"SQLite charts failed for {path.name}: {e}")
        charts = None

    if charts is None:
        raise IndexUnavailableError(f"Export is not indexed: {file_name}")

    return {
        "ok": True,
        "file": path.name,
        "channel": extract_channel_from_export_name(path.name),
        **charts,
    }


def get_export_posts(file_name, query):
    path = resolve_raw_json_file(file_name)
    ensure_sqlite_export_index(path.name, path)

    try:
        limit = int(first_query_value(query, "limit", "100"))
    except ValueError as e:
        raise ValueError("Posts limit must be an integer") from e

    try:
        offset = int(first_query_value(query, "offset", "0"))
    except ValueError as e:
        raise ValueError("Posts offset must be an integer") from e

    result = list_posts_sqlite(
        path.name,
        limit=limit,
        offset=offset,
        **parse_post_filter_query(query),
    )

    if result is None:
        raise IndexUnavailableError(f"Export is not indexed: {file_name}")

    return {
        "ok": True,
        "file": path.name,
        "channel": extract_channel_from_export_name(path.name),
        **result,
    }


def get_export_filtered_summary(file_name, query):
    path = resolve_raw_json_file(file_name)
    ensure_sqlite_export_index(path.name, path)

    summary = get_filtered_summary_sqlite(
        path.name,
        **parse_post_filter_query(query),
    )

    if summary is None:
        raise IndexUnavailableError(f"Export is not indexed: {file_name}")

    return {
        "ok": True,
        "file": path.name,
        "channel": extract_channel_from_export_name(path.name),
        **summary,
    }


def parse_post_filter_query(query):
    return {
        "query": first_query_value(query, "q").strip() or None,
        "user": first_query_value(query, "user").strip() or None,
        "date_from": first_query_value(query, "from").strip() or None,
        "date_to": first_query_value(query, "to").strip() or None,
        "emoji": first_query_value(query, "emoji").strip() or None,
        "media": first_query_value(query, "media").strip().lower() in {"1", "true", "yes"},
        "replies": first_query_value(query, "replies").strip().lower() in {"1", "true", "yes"},
    }


def get_export_post(file_name, post_id):
    path = resolve_raw_json_file(file_name)
    ensure_sqlite_export_index(path.name, path)

    try:
        clean_post_id = int(str(post_id).strip())
    except ValueError as e:
        raise ValueError("Post id must be an integer") from e

    post = get_post_sqlite(path.name, clean_post_id)
    if post is None:
        raise FileNotFoundError(f"Post not found: {post_id}")

    return {
        "ok": True,
        "file": path.name,
        "channel": extract_channel_from_export_name(path.name),
        "post": post,
    }


def get_export_period_compare(file_name, from_date, to_date):
    path = resolve_raw_json_file(file_name)
    try:
        ensure_sqlite_export_index(path.name, path)
        result = compare_periods_sqlite(path.name, from_date, to_date)
    except IndexUnavailableError as e:
        print(f"SQLite compare failed for {path.name}: {e}")
        result = None

    if result is None:
        _, posts = load_export_posts(path.name)
        result = compare_periods(posts, from_date, to_date)

    result.update({
        "ok": True,
        "file": path.name,
        "channel": extract_channel_from_export_name(path.name),
    })
    return result

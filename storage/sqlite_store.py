from errors import index_operation
import json
import sqlite3
import time
from datetime import datetime, time as datetime_time, timedelta, timezone
from pathlib import Path


DB_PATH = Path("data/state/tg.sqlite")


def connect(db_path=DB_PATH):
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    init_db(conn)
    return conn


def init_db(conn):
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS export_files (
            file_name TEXT PRIMARY KEY,
            channel_key TEXT NOT NULL,
            size_bytes INTEGER,
            modified_at TEXT,
            indexed_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS posts (
            file_name TEXT NOT NULL,
            channel_key TEXT NOT NULL,
            post_id INTEGER NOT NULL,
            post_date TEXT,
            post_text TEXT,
            post_views INTEGER,
            post_forwards INTEGER,
            post_link TEXT,
            post_media TEXT,
            post_media_error TEXT,
            export_errors TEXT,
            PRIMARY KEY (file_name, post_id),
            FOREIGN KEY (file_name) REFERENCES export_files(file_name) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS comments (
            file_name TEXT NOT NULL,
            channel_key TEXT NOT NULL,
            post_id INTEGER NOT NULL,
            comment_id INTEGER NOT NULL,
            comment_date TEXT,
            comment_text TEXT,
            comment_link TEXT,
            comment_media TEXT,
            reply_to_msg_id INTEGER,
            user_id TEXT,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            bot INTEGER,
            premium INTEGER,
            comment_media_error TEXT,
            PRIMARY KEY (file_name, post_id, comment_id),
            FOREIGN KEY (file_name, post_id) REFERENCES posts(file_name, post_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS reactions (
            file_name TEXT NOT NULL,
            target_type TEXT NOT NULL,
            post_id INTEGER NOT NULL,
            comment_id INTEGER,
            emoji TEXT NOT NULL,
            count INTEGER NOT NULL,
            PRIMARY KEY (file_name, target_type, post_id, comment_id, emoji),
            FOREIGN KEY (file_name) REFERENCES export_files(file_name) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_posts_file_date ON posts(file_name, post_date);
        CREATE INDEX IF NOT EXISTS idx_reactions_file_post ON reactions(file_name, post_id);
        CREATE INDEX IF NOT EXISTS idx_comments_file_date ON comments(file_name, comment_date);
        CREATE INDEX IF NOT EXISTS idx_comments_file_user ON comments(file_name, user_id);
        CREATE INDEX IF NOT EXISTS idx_comments_file_username ON comments(file_name, username);
        CREATE INDEX IF NOT EXISTS idx_comments_file_text ON comments(file_name, comment_text);

        CREATE TABLE IF NOT EXISTS export_states (
            channel_key TEXT PRIMARY KEY,
            dataset_file TEXT NOT NULL,
            last_post_id INTEGER,
            last_success_at TEXT,
            lookback_posts INTEGER,
            last_error TEXT,
            state_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_export_states_updated ON export_states(updated_at);
        CREATE INDEX IF NOT EXISTS idx_export_states_success ON export_states(last_success_at);

        CREATE TABLE IF NOT EXISTS scheduler_runs (
            id TEXT PRIMARY KEY,
            status TEXT,
            channels TEXT,
            format TEXT,
            created_at TEXT,
            scheduled_for TEXT,
            started_at TEXT,
            finished_at TEXT,
            returncode INTEGER,
            posts_processed INTEGER,
            channels_ok INTEGER,
            channels_failed INTEGER,
            error_type TEXT,
            error_message TEXT,
            record_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_scheduler_runs_created ON scheduler_runs(created_at);
        CREATE INDEX IF NOT EXISTS idx_scheduler_runs_status ON scheduler_runs(status);
        CREATE INDEX IF NOT EXISTS idx_scheduler_runs_channels ON scheduler_runs(channels);
        CREATE INDEX IF NOT EXISTS idx_scheduler_runs_error_type ON scheduler_runs(error_type);

        CREATE TABLE IF NOT EXISTS analysis_files (
            file_name TEXT PRIMARY KEY,
            source_export TEXT,
            size_bytes INTEGER,
            modified_at TEXT,
            created_at TEXT,
            prompt_language TEXT,
            posts_analyzed INTEGER,
            status TEXT NOT NULL,
            analysis_errors_count INTEGER NOT NULL DEFAULT 0,
            record_json TEXT NOT NULL,
            indexed_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS analysis_results (
            file_name TEXT NOT NULL,
            post_id TEXT NOT NULL,
            post_date TEXT,
            comments_count INTEGER,
            status TEXT NOT NULL,
            analysis_error TEXT,
            prompt_language TEXT,
            result_json TEXT NOT NULL,
            PRIMARY KEY (file_name, post_id),
            FOREIGN KEY (file_name) REFERENCES analysis_files(file_name) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS analysis_cache (
            source_file TEXT NOT NULL,
            post_id TEXT NOT NULL,
            post_hash TEXT NOT NULL,
            prompt_hash TEXT NOT NULL,
            model TEXT NOT NULL,
            status TEXT NOT NULL,
            analysis_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (source_file, post_id, post_hash, prompt_hash, model)
        );

        CREATE INDEX IF NOT EXISTS idx_analysis_files_source ON analysis_files(source_export);
        CREATE INDEX IF NOT EXISTS idx_analysis_files_status ON analysis_files(status);
        CREATE INDEX IF NOT EXISTS idx_analysis_results_status ON analysis_results(file_name, status);
        CREATE INDEX IF NOT EXISTS idx_analysis_results_post_id ON analysis_results(post_id);
        CREATE INDEX IF NOT EXISTS idx_analysis_cache_source ON analysis_cache(source_file, post_id);
        CREATE INDEX IF NOT EXISTS idx_analysis_cache_status ON analysis_cache(status);
        """
    )
    init_fts(conn)


def init_fts(conn):
    try:
        conn.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS comments_fts USING fts5(
                file_name UNINDEXED,
                channel_key UNINDEXED,
                post_id UNINDEXED,
                comment_id UNINDEXED,
                comment_text,
                username,
                first_name,
                last_name
            )
            """
        )
    except sqlite3.OperationalError:
        pass


def has_fts(conn):
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'comments_fts'"
    ).fetchone()
    return row is not None


def json_text(value):
    return json.dumps(value, ensure_ascii=False) if value else None


def bool_int(value):
    if value is None:
        return None
    return 1 if value else 0


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())


@index_operation
def upsert_export_state(state):
    if not isinstance(state, dict):
        raise ValueError("Export state must be an object")

    channel_key = state.get("channel_key") or state.get("channel")
    dataset_file = state.get("dataset_file") or state.get("dataset_path")

    if not channel_key:
        raise ValueError("Export state must have a channel_key")
    if not dataset_file:
        raise ValueError("Export state must have a dataset_file")

    with connect() as conn:
        previous = conn.execute(
            "SELECT last_success_at FROM export_states WHERE channel_key = ?",
            (str(channel_key),),
        ).fetchone()
        last_success_at = state.get("last_success_at")
        if not last_success_at and previous:
            last_success_at = previous["last_success_at"]

        updated_at = state.get("updated_at") or now_iso()
        state = {
            **state,
            "channel_key": str(channel_key),
            "dataset_file": str(dataset_file),
            "last_success_at": last_success_at,
            "updated_at": updated_at,
        }
        conn.execute(
            """
            INSERT INTO export_states (
                channel_key, dataset_file, last_post_id, last_success_at,
                lookback_posts, last_error, state_json, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(channel_key) DO UPDATE SET
                dataset_file = excluded.dataset_file,
                last_post_id = excluded.last_post_id,
                last_success_at = COALESCE(excluded.last_success_at, export_states.last_success_at),
                lookback_posts = excluded.lookback_posts,
                last_error = excluded.last_error,
                state_json = excluded.state_json,
                updated_at = excluded.updated_at
            """,
            (
                state["channel_key"],
                state["dataset_file"],
                state.get("last_post_id"),
                state.get("last_success_at"),
                state.get("lookback_posts"),
                state.get("last_error"),
                json.dumps(state, ensure_ascii=False),
                updated_at,
            ),
        )


@index_operation
def get_export_state(channel_key):
    with connect() as conn:
        row = conn.execute(
            "SELECT state_json FROM export_states WHERE channel_key = ?",
            (str(channel_key),),
        ).fetchone()

    if not row:
        return None

    return json.loads(row["state_json"])


@index_operation
def list_export_states():
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT
                channel_key, dataset_file, last_post_id, last_success_at,
                lookback_posts, last_error, updated_at
            FROM export_states
            ORDER BY COALESCE(last_success_at, updated_at) DESC, channel_key
            """
        ).fetchall()

    return [dict(row) for row in rows]


@index_operation
def upsert_scheduler_run(record):
    if not isinstance(record, dict):
        raise ValueError("Scheduler run record must be an object")

    run_id = record.get("id")
    if not run_id:
        raise ValueError("Scheduler run record must have an id")

    error = record.get("error") or {}

    with connect() as conn:
        conn.execute(
            """
            INSERT INTO scheduler_runs (
                id, status, channels, format, created_at, scheduled_for, started_at,
                finished_at, returncode, posts_processed, channels_ok, channels_failed,
                error_type, error_message, record_json, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                status = excluded.status,
                channels = excluded.channels,
                format = excluded.format,
                created_at = excluded.created_at,
                scheduled_for = excluded.scheduled_for,
                started_at = excluded.started_at,
                finished_at = excluded.finished_at,
                returncode = excluded.returncode,
                posts_processed = excluded.posts_processed,
                channels_ok = excluded.channels_ok,
                channels_failed = excluded.channels_failed,
                error_type = excluded.error_type,
                error_message = excluded.error_message,
                record_json = excluded.record_json,
                updated_at = excluded.updated_at
            """,
            (
                run_id,
                record.get("status"),
                record.get("channels"),
                record.get("format"),
                record.get("created_at"),
                record.get("scheduled_for"),
                record.get("started_at"),
                record.get("finished_at"),
                record.get("returncode"),
                int(record.get("posts_processed") or 0),
                int(record.get("channels_ok") or 0),
                int(record.get("channels_failed") or 0),
                error.get("type") if isinstance(error, dict) else None,
                error.get("message") if isinstance(error, dict) else None,
                json.dumps(record, ensure_ascii=False),
                now_iso(),
            ),
        )


@index_operation
def read_scheduler_run_record(run_id):
    with connect() as conn:
        row = conn.execute(
            "SELECT record_json FROM scheduler_runs WHERE id = ?",
            (run_id,),
        ).fetchone()

    if not row:
        return None

    return json.loads(row["record_json"])


@index_operation
def list_scheduler_run_records(limit=50, offset=0, status=None, channel=None):
    safe_limit = max(1, min(int(limit or 50), 200))
    safe_offset = max(0, int(offset or 0))
    where, params = build_scheduler_run_filters(status, channel)

    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT record_json
            FROM scheduler_runs
            {where}
            ORDER BY COALESCE(finished_at, started_at, created_at) DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            params + [safe_limit, safe_offset],
        ).fetchall()

    return [json.loads(row["record_json"]) for row in rows]


@index_operation
def count_scheduler_run_records(status=None, channel=None):
    where, params = build_scheduler_run_filters(status, channel)

    with connect() as conn:
        row = conn.execute(
            f"SELECT COUNT(*) AS count FROM scheduler_runs {where}",
            params,
        ).fetchone()

    return row["count"]


def build_scheduler_run_filters(status=None, channel=None):
    clauses = []
    params = []

    if status:
        clauses.append("status = ?")
        params.append(str(status).strip().upper())

    if channel:
        clauses.append("channels LIKE ? COLLATE NOCASE")
        params.append(f"%{str(channel).strip()}%")

    if not clauses:
        return "", params

    return "WHERE " + " AND ".join(clauses), params


@index_operation
def get_scheduler_run_stats(status=None, channel=None):
    where, params = build_scheduler_run_filters(status, channel)

    with connect() as conn:
        totals = conn.execute(
            f"""
            SELECT
                COUNT(*) AS total,
                COALESCE(SUM(posts_processed), 0) AS posts_processed,
                COALESCE(SUM(channels_ok), 0) AS channels_ok,
                COALESCE(SUM(channels_failed), 0) AS channels_failed
            FROM scheduler_runs
            {where}
            """,
            params,
        ).fetchone()
        statuses = conn.execute(
            f"""
            SELECT status, COUNT(*) AS count
            FROM scheduler_runs
            {where}
            GROUP BY status
            ORDER BY count DESC, status
            """,
            params,
        ).fetchall()
        errors = conn.execute(
            f"""
            SELECT error_type, COUNT(*) AS count
            FROM scheduler_runs
            {where} {"AND" if where else "WHERE"} error_type IS NOT NULL
            GROUP BY error_type
            ORDER BY count DESC, error_type
            """,
            params,
        ).fetchall()

    return {
        "total": totals["total"],
        "posts_processed": totals["posts_processed"],
        "channels_ok": totals["channels_ok"],
        "channels_failed": totals["channels_failed"],
        "by_status": {row["status"] or "UNKNOWN": row["count"] for row in statuses},
        "by_error_type": {row["error_type"] or "UNKNOWN": row["count"] for row in errors},
    }


def file_modified_iso(path):
    source = Path(path)
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(source.stat().st_mtime))


def extract_analysis_rows(analysis_payload):
    analyses = analysis_payload.get("analyses")
    if isinstance(analyses, list):
        return [item for item in analyses if isinstance(item, dict)]
    return []


def analysis_status(rows):
    if not rows:
        return "EMPTY"

    errors = sum(1 for row in rows if row.get("analysis_error"))
    if errors == 0:
        return "OK"
    if errors == len(rows):
        return "FAILED"
    return "PARTIAL"


@index_operation
def get_analysis_cache_entry(source_file, post_id, post_hash, prompt_hash, model, status="OK"):
    with connect() as conn:
        row = conn.execute(
            """
            SELECT analysis_json
            FROM analysis_cache
            WHERE source_file = ?
                AND post_id = ?
                AND post_hash = ?
                AND prompt_hash = ?
                AND model = ?
                AND status = ?
            """,
            (
                str(source_file),
                str(post_id),
                str(post_hash),
                str(prompt_hash),
                str(model),
                str(status),
            ),
        ).fetchone()

    if not row:
        return None

    return json.loads(row["analysis_json"])


@index_operation
def upsert_analysis_cache_entry(source_file, post_id, post_hash, prompt_hash, model, status, analysis_item):
    if not isinstance(analysis_item, dict):
        raise ValueError("Analysis cache item must be an object")

    current_time = now_iso()

    with connect() as conn:
        existing = conn.execute(
            """
            SELECT created_at
            FROM analysis_cache
            WHERE source_file = ?
                AND post_id = ?
                AND post_hash = ?
                AND prompt_hash = ?
                AND model = ?
            """,
            (
                str(source_file),
                str(post_id),
                str(post_hash),
                str(prompt_hash),
                str(model),
            ),
        ).fetchone()
        created_at = existing["created_at"] if existing else current_time
        conn.execute(
            """
            INSERT INTO analysis_cache (
                source_file, post_id, post_hash, prompt_hash, model,
                status, analysis_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_file, post_id, post_hash, prompt_hash, model) DO UPDATE SET
                status = excluded.status,
                analysis_json = excluded.analysis_json,
                updated_at = excluded.updated_at
            """,
            (
                str(source_file),
                str(post_id),
                str(post_hash),
                str(prompt_hash),
                str(model),
                str(status),
                json.dumps(analysis_item, ensure_ascii=False),
                created_at,
                current_time,
            ),
        )


@index_operation
def sync_analysis_file(file_name, analysis_payload, source_path=None):
    if not isinstance(analysis_payload, dict):
        raise ValueError("Analysis payload must be an object")

    path = Path(source_path) if source_path else None
    size_bytes = path.stat().st_size if path and path.exists() else None
    modified_at = file_modified_iso(path) if path and path.exists() else None
    rows = extract_analysis_rows(analysis_payload)
    prompt_language = analysis_payload.get("prompt_language")
    status = analysis_status(rows)
    errors_count = sum(1 for row in rows if row.get("analysis_error"))
    source_export = analysis_payload.get("source_file")
    if source_export:
        source_export = Path(source_export).name

    with connect() as conn:
        conn.execute("DELETE FROM analysis_files WHERE file_name = ?", (file_name,))
        conn.execute(
            """
            INSERT INTO analysis_files (
                file_name, source_export, size_bytes, modified_at, created_at,
                prompt_language, posts_analyzed, status, analysis_errors_count,
                record_json, indexed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                file_name,
                source_export,
                size_bytes,
                modified_at,
                modified_at,
                prompt_language,
                int(analysis_payload.get("posts_analyzed") or len(rows)),
                status,
                errors_count,
                json.dumps(analysis_payload, ensure_ascii=False),
                now_iso(),
            ),
        )

        for index, row in enumerate(rows, start=1):
            post_id = row.get("post_id")
            if post_id is None:
                post_id = f"row:{index}"

            row_status = "ERROR" if row.get("analysis_error") else "OK"
            conn.execute(
                """
                INSERT INTO analysis_results (
                    file_name, post_id, post_date, comments_count, status,
                    analysis_error, prompt_language, result_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    file_name,
                    str(post_id),
                    row.get("post_date"),
                    row.get("comments_count"),
                    row_status,
                    row.get("analysis_error"),
                    prompt_language,
                    json.dumps(row, ensure_ascii=False),
                ),
            )


@index_operation
def get_indexed_analysis(file_name):
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM analysis_files WHERE file_name = ?",
            (file_name,),
        ).fetchone()


@index_operation
def list_analysis_file_records():
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT
                file_name, source_export, size_bytes, modified_at, created_at,
                prompt_language, posts_analyzed, status, analysis_errors_count,
                indexed_at
            FROM analysis_files
            ORDER BY COALESCE(modified_at, created_at, indexed_at) DESC, file_name
            """
        ).fetchall()

    return [dict(row) for row in rows]


@index_operation
def read_analysis_record(file_name):
    with connect() as conn:
        row = conn.execute(
            "SELECT record_json FROM analysis_files WHERE file_name = ?",
            (file_name,),
        ).fetchone()

    if not row:
        return None

    return json.loads(row["record_json"])


@index_operation
def list_analysis_result_records(file_name, status=None, limit=50, offset=0):
    safe_limit = max(1, min(int(limit or 50), 200))
    safe_offset = max(0, int(offset or 0))
    clauses = ["file_name = ?"]
    params = [file_name]

    if status:
        clauses.append("status = ?")
        params.append(str(status).strip().upper())

    params.extend([safe_limit, safe_offset])

    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT
                file_name, post_id, post_date, comments_count, status,
                analysis_error, prompt_language
            FROM analysis_results
            WHERE {" AND ".join(clauses)}
            ORDER BY post_date, post_id
            LIMIT ? OFFSET ?
            """,
            params,
        ).fetchall()

    return [dict(row) for row in rows]


@index_operation
def sync_export_file(file_name, channel_key, posts, source_path=None):
    if not isinstance(posts, list):
        raise ValueError("Export posts must be a list")

    path = Path(source_path) if source_path else None
    size_bytes = path.stat().st_size if path and path.exists() else None
    modified_at = (
        time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(path.stat().st_mtime))
        if path and path.exists()
        else None
    )

    with connect() as conn:
        conn.execute("DELETE FROM export_files WHERE file_name = ?", (file_name,))
        delete_fts_file(conn, file_name)
        conn.execute(
            """
            INSERT INTO export_files (file_name, channel_key, size_bytes, modified_at, indexed_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (file_name, channel_key, size_bytes, modified_at, now_iso()),
        )

        insert_export_posts(conn, file_name, channel_key, posts)


def export_file_signature(path):
    path = Path(path)
    if not path.exists():
        return None
    stat = path.stat()
    return (stat.st_size, time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(stat.st_mtime)))


@index_operation
def sync_export_posts(file_name, channel_key, posts, source_path, previous_signature, full_posts):
    """Replace only changed posts when the index matches the previous JSON.

    JSON is written first. A missing/stale index (including a previous failed
    update) is rebuilt from the complete dataset rather than marked current
    after an incomplete patch.
    """
    signature = export_file_signature(source_path)
    if not isinstance(posts, list):
        raise ValueError("Export posts must be a list")
    with connect() as conn:
        indexed = conn.execute(
            "SELECT * FROM export_files WHERE file_name = ?", (file_name,),
        ).fetchone()
        fts_missing = has_fts(conn) and conn.execute(
            "SELECT 1 FROM comments WHERE file_name = ? LIMIT 1", (file_name,),
        ).fetchone() and not conn.execute(
            "SELECT 1 FROM comments_fts WHERE file_name = ? LIMIT 1", (file_name,),
        ).fetchone()
        if (
            not indexed or not previous_signature or not signature or fts_missing
            or indexed["channel_key"] != channel_key
            or (indexed["size_bytes"], indexed["modified_at"]) != previous_signature
        ):
            rebuild = True
        else:
            rebuild = False
            # One FTS scan per batch; other tables use file/post indexes.
            post_ids = list({p["post_id"] for p in posts if isinstance(p, dict) and p.get("post_id") is not None})
            for offset in range(0, len(post_ids), 500):
                chunk = post_ids[offset:offset + 500]
                placeholders = ",".join("?" for _ in chunk)
                parameters = [file_name, *chunk]
                if has_fts(conn):
                    conn.execute(f"DELETE FROM comments_fts WHERE file_name = ? AND post_id IN ({placeholders})", parameters)
                conn.execute(f"DELETE FROM reactions WHERE file_name = ? AND post_id IN ({placeholders})", parameters)
                conn.execute(f"DELETE FROM posts WHERE file_name = ? AND post_id IN ({placeholders})", parameters)
            insert_export_posts(conn, file_name, channel_key, posts)
            conn.execute(
                "UPDATE export_files SET size_bytes = ?, modified_at = ?, indexed_at = ? WHERE file_name = ?",
                (*signature, now_iso(), file_name),
            )
    if rebuild:
        sync_export_file(file_name, channel_key, full_posts, source_path)


def insert_export_posts(conn, file_name, channel_key, posts):
    for post in posts:
        if not isinstance(post, dict):
            continue

        post_id = post.get("post_id")
        if post_id is None:
            continue

        conn.execute(
            """
            INSERT INTO posts (
                file_name, channel_key, post_id, post_date, post_text, post_views,
                post_forwards, post_link, post_media, post_media_error, export_errors
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                file_name,
                channel_key,
                post_id,
                post.get("post_date"),
                post.get("post_text"),
                post.get("post_views"),
                post.get("post_forwards"),
                post.get("post_link"),
                post.get("post_media"),
                post.get("post_media_error"),
                json_text(post.get("export_errors")),
            ),
        )
        insert_reactions(conn, file_name, "post", post_id, None, post.get("post_reactions"))

        for comment in post.get("comments") or []:
            if not isinstance(comment, dict):
                continue

            comment_id = comment.get("comment_id")
            if comment_id is None:
                continue

            user = comment.get("user") or {}
            conn.execute(
                """
                INSERT INTO comments (
                    file_name, channel_key, post_id, comment_id, comment_date, comment_text,
                    comment_link, comment_media, reply_to_msg_id, user_id, username,
                    first_name, last_name, bot, premium, comment_media_error
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    file_name,
                    channel_key,
                    post_id,
                    comment_id,
                    comment.get("comment_date"),
                    comment.get("comment_text"),
                    comment.get("comment_link"),
                    comment.get("comment_media"),
                    comment.get("reply_to_msg_id"),
                    None if user.get("user_id") is None else str(user.get("user_id")),
                    user.get("username"),
                    user.get("first_name"),
                    user.get("last_name"),
                    bool_int(user.get("bot")),
                    bool_int(user.get("premium")),
                    comment.get("comment_media_error"),
                ),
            )
            insert_reactions(conn, file_name, "comment", post_id, comment_id, comment.get("comment_reactions"))
            insert_fts_comment(conn, file_name, channel_key, post_id, comment_id, comment, user)


def insert_reactions(conn, file_name, target_type, post_id, comment_id, reactions):
    for reaction in reactions or []:
        if not isinstance(reaction, dict):
            continue

        emoji = reaction.get("emoji")
        if not emoji:
            continue

        conn.execute(
            """
            INSERT INTO reactions (file_name, target_type, post_id, comment_id, emoji, count)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                file_name,
                target_type,
                post_id,
                comment_id,
                emoji,
                int(reaction.get("count") or 0),
            ),
        )


def delete_fts_file(conn, file_name):
    if not has_fts(conn):
        return

    conn.execute("DELETE FROM comments_fts WHERE file_name = ?", (file_name,))


def insert_fts_comment(conn, file_name, channel_key, post_id, comment_id, comment, user):
    if not has_fts(conn):
        return

    conn.execute(
        """
        INSERT INTO comments_fts (
            file_name, channel_key, post_id, comment_id, comment_text,
            username, first_name, last_name
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            file_name,
            channel_key,
            post_id,
            comment_id,
            comment.get("comment_text"),
            user.get("username"),
            user.get("first_name"),
            user.get("last_name"),
        ),
    )


@index_operation
def is_indexed(file_name):
    with connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM export_files WHERE file_name = ?",
            (file_name,),
        ).fetchone()
    return row is not None


@index_operation
def get_indexed_export(file_name):
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM export_files WHERE file_name = ?",
            (file_name,),
        ).fetchone()


@index_operation
def list_indexed_exports():
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT
                e.file_name,
                e.channel_key,
                e.size_bytes,
                e.modified_at,
                e.indexed_at,
                (SELECT COUNT(*) FROM posts p WHERE p.file_name = e.file_name) AS posts_count,
                (SELECT COUNT(*) FROM comments c WHERE c.file_name = e.file_name) AS comments_count,
                (
                    SELECT COUNT(DISTINCT c.user_id)
                    FROM comments c
                    WHERE c.file_name = e.file_name AND c.user_id IS NOT NULL
                ) AS unique_users_count,
                (
                    SELECT COALESCE(SUM(r.count), 0)
                    FROM reactions r
                    WHERE r.file_name = e.file_name
                ) AS reactions_count
            FROM export_files e
            ORDER BY COALESCE(e.modified_at, e.indexed_at) DESC, e.file_name
            """
        ).fetchall()

    return [dict(row) for row in rows]


@index_operation
def needs_fts_reindex(file_name):
    with connect() as conn:
        if not has_fts(conn):
            return False

        comments_count = conn.execute(
            "SELECT COUNT(*) AS count FROM comments WHERE file_name = ?",
            (file_name,),
        ).fetchone()["count"]

        if comments_count == 0:
            return False

        fts_count = conn.execute(
            "SELECT COUNT(*) AS count FROM comments_fts WHERE file_name = ?",
            (file_name,),
        ).fetchone()["count"]

    return fts_count == 0


@index_operation
def get_export_summary(file_name):
    with connect() as conn:
        export_file = conn.execute(
            "SELECT * FROM export_files WHERE file_name = ?",
            (file_name,),
        ).fetchone()

        if not export_file:
            return None

        counts = conn.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM posts WHERE file_name = ?) AS posts_count,
                (SELECT COUNT(*) FROM comments WHERE file_name = ?) AS comments_count,
                (SELECT COUNT(DISTINCT user_id) FROM comments WHERE file_name = ? AND user_id IS NOT NULL) AS unique_users_count,
                (SELECT COALESCE(SUM(count), 0) FROM reactions WHERE file_name = ?) AS reactions_count
            """,
            (file_name, file_name, file_name, file_name),
        ).fetchone()

    return {
        "posts_count": counts["posts_count"],
        "comments_count": counts["comments_count"],
        "unique_users_count": counts["unique_users_count"],
        "reactions_count": counts["reactions_count"],
    }


@index_operation
def comments_by_day(file_name):
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT substr(comment_date, 1, 10) AS label, COUNT(*) AS value
            FROM comments
            WHERE file_name = ?
                AND comment_date IS NOT NULL
                AND trim(comment_date) != ''
            GROUP BY label
            ORDER BY label
            """,
            (file_name,),
        ).fetchall()

    return [dict(row) for row in rows if row["label"]]


@index_operation
def top_users(file_name, limit=10):
    safe_limit = max(1, min(int(limit or 10), 100))
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT
                user_id,
                username,
                first_name,
                last_name,
                COALESCE(NULLIF(trim(COALESCE(first_name, '') || ' ' || COALESCE(last_name, '')), ''), username, user_id, 'Unknown user') AS label,
                COUNT(*) AS value
            FROM comments
            WHERE file_name = ?
                AND user_id IS NOT NULL
            GROUP BY user_id, username, first_name, last_name
            ORDER BY value DESC, label
            LIMIT ?
            """,
            (file_name, safe_limit),
        ).fetchall()

    return [
        {
            "label": row["label"],
            "value": row["value"],
            "userId": row["user_id"],
            "username": row["username"],
        }
        for row in rows
    ]


@index_operation
def top_reactions(file_name, limit=10):
    safe_limit = max(1, min(int(limit or 10), 100))
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT emoji AS label, COALESCE(SUM(count), 0) AS value
            FROM reactions
            WHERE file_name = ?
            GROUP BY emoji
            HAVING value > 0
            ORDER BY value DESC, emoji
            LIMIT ?
            """,
            (file_name, safe_limit),
        ).fetchall()

    return [dict(row) for row in rows]


@index_operation
def top_posts_by_comments(file_name, limit=10):
    safe_limit = max(1, min(int(limit or 10), 100))
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT
                p.post_id,
                'Post ' || p.post_id AS label,
                COUNT(c.comment_id) AS value
            FROM posts p
            LEFT JOIN comments c
                ON c.file_name = p.file_name
                AND c.post_id = p.post_id
            WHERE p.file_name = ?
            GROUP BY p.post_id
            HAVING value > 0
            ORDER BY value DESC, p.post_id DESC
            LIMIT ?
            """,
            (file_name, safe_limit),
        ).fetchall()

    return [
        {
            "label": row["label"],
            "value": row["value"],
            "postId": str(row["post_id"]),
        }
        for row in rows
    ]


@index_operation
def activity_heatmap(file_name):
    matrix = [[0 for _hour in range(24)] for _day in range(7)]

    with connect() as conn:
        rows = conn.execute(
            """
            SELECT
                ((CAST(strftime('%w', comment_date) AS INTEGER) + 6) % 7) AS day_index,
                CAST(strftime('%H', comment_date) AS INTEGER) AS hour,
                COUNT(*) AS value
            FROM comments
            WHERE file_name = ?
                AND comment_date IS NOT NULL
                AND trim(comment_date) != ''
            GROUP BY day_index, hour
            """,
            (file_name,),
        ).fetchall()

    for row in rows:
        day_index = row["day_index"]
        hour = row["hour"]
        if day_index is None or hour is None:
            continue
        if 0 <= day_index < 7 and 0 <= hour < 24:
            matrix[day_index][hour] = row["value"]

    return matrix


@index_operation
def get_export_charts(file_name, limit=10):
    with connect() as conn:
        indexed = conn.execute(
            "SELECT 1 FROM export_files WHERE file_name = ?",
            (file_name,),
        ).fetchone()

    if not indexed:
        return None

    return {
        "comments_by_day": comments_by_day(file_name),
        "top_users": top_users(file_name, limit),
        "top_reactions": top_reactions(file_name, limit),
        "top_posts_by_comments": top_posts_by_comments(file_name, limit),
        "activity_heatmap": activity_heatmap(file_name),
    }


def parse_period_date(value):
    if not value:
        raise ValueError("Period date is required")

    text = str(value).strip()
    if len(text) == 10:
        parsed = datetime.combine(datetime.fromisoformat(text).date(), datetime_time.min)
    else:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))

    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)

    return parsed


def period_metrics(conn, file_name, start, end):
    row = conn.execute(
        """
        SELECT COUNT(*) AS comments, COUNT(DISTINCT user_id) AS users
        FROM comments
        WHERE file_name = ?
            AND comment_date >= ?
            AND comment_date < ?
        """,
        (file_name, start.isoformat(sep=" "), end.isoformat(sep=" ")),
    ).fetchone()
    reactions = conn.execute(
        """
        SELECT COALESCE(SUM(r.count), 0) AS reactions
        FROM reactions r
        JOIN comments c
            ON c.file_name = r.file_name
            AND c.post_id = r.post_id
            AND c.comment_id = r.comment_id
        WHERE r.file_name = ?
            AND r.target_type = 'comment'
            AND c.comment_date >= ?
            AND c.comment_date < ?
        """,
        (file_name, start.isoformat(sep=" "), end.isoformat(sep=" ")),
    ).fetchone()
    return {
        "comments": row["comments"],
        "users": row["users"],
        "reactions": reactions["reactions"],
    }


def build_diff(current, previous):
    result = {}
    for key, value in current.items():
        previous_value = previous.get(key, 0)
        delta = value - previous_value
        percent = None if previous_value == 0 else (delta / previous_value) * 100
        result[key] = {
            "current": value,
            "previous": previous_value,
            "delta": delta,
            "percent": percent,
        }
    return result


@index_operation
def compare_periods(file_name, from_date, to_date):
    current_start = parse_period_date(from_date)
    current_end = parse_period_date(to_date)

    if current_end <= current_start:
        raise ValueError("--to must be later than --from")

    duration = current_end - current_start
    previous_start = current_start - duration
    previous_end = current_start

    with connect() as conn:
        indexed = conn.execute(
            "SELECT 1 FROM export_files WHERE file_name = ?",
            (file_name,),
        ).fetchone()
        if not indexed:
            return None

        current = period_metrics(conn, file_name, current_start, current_end)
        previous = period_metrics(conn, file_name, previous_start, previous_end)

    return {
        "current_period": {
            "from": current_start.date().isoformat(),
            "to": current_end.date().isoformat(),
        },
        "previous_period": {
            "from": previous_start.date().isoformat(),
            "to": previous_end.date().isoformat(),
        },
        "metrics": build_diff(current, previous),
    }


def reaction_rows(conn, file_name, target_type, post_id, comment_id=None):
    if comment_id is None:
        rows = conn.execute(
            """
            SELECT emoji, count FROM reactions
            WHERE file_name = ? AND target_type = ? AND post_id = ? AND comment_id IS NULL
            ORDER BY count DESC, emoji
            """,
            (file_name, target_type, post_id),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT emoji, count FROM reactions
            WHERE file_name = ? AND target_type = ? AND post_id = ? AND comment_id = ?
            ORDER BY count DESC, emoji
            """,
            (file_name, target_type, post_id, comment_id),
        ).fetchall()

    return [{"emoji": row["emoji"], "count": row["count"]} for row in rows]


def decode_json_list(value):
    if not value:
        return None
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError:
        return None
    return decoded if isinstance(decoded, list) else None


def restore_user_id(value):
    if value is None:
        return None
    text = str(value)
    return int(text) if text.isdigit() else value


@index_operation
def get_post(file_name, post_id):
    with connect() as conn:
        post = conn.execute(
            "SELECT * FROM posts WHERE file_name = ? AND post_id = ?",
            (file_name, post_id),
        ).fetchone()

        if not post:
            return None

        result = {
            "post_id": post["post_id"],
            "post_date": post["post_date"],
            "post_text": post["post_text"],
            "post_views": post["post_views"],
            "post_forwards": post["post_forwards"],
            "post_link": post["post_link"],
            "post_media": post["post_media"],
            "post_reactions": reaction_rows(conn, file_name, "post", post_id),
            "comments": [],
        }

        if post["post_media_error"]:
            result["post_media_error"] = post["post_media_error"]

        export_errors = decode_json_list(post["export_errors"])
        if export_errors:
            result["export_errors"] = export_errors

        comments = conn.execute(
            """
            SELECT * FROM comments
            WHERE file_name = ? AND post_id = ?
            ORDER BY comment_date, comment_id
            """,
            (file_name, post_id),
        ).fetchall()

        for comment in comments:
            item = {
                "comment_id": comment["comment_id"],
                "comment_date": comment["comment_date"],
                "comment_text": comment["comment_text"],
                "comment_link": comment["comment_link"],
                "comment_media": comment["comment_media"],
                "reply_to_msg_id": comment["reply_to_msg_id"],
                "comment_reactions": reaction_rows(conn, file_name, "comment", post_id, comment["comment_id"]),
                "user": {
                    "user_id": restore_user_id(comment["user_id"]),
                    "username": comment["username"],
                    "first_name": comment["first_name"],
                    "last_name": comment["last_name"],
                    "bot": None if comment["bot"] is None else bool(comment["bot"]),
                    "premium": None if comment["premium"] is None else bool(comment["premium"]),
                },
            }
            if comment["comment_media_error"]:
                item["comment_media_error"] = comment["comment_media_error"]
            result["comments"].append(item)

    return result


@index_operation
def list_posts(
    file_name,
    limit=100,
    offset=0,
    query=None,
    user=None,
    date_from=None,
    date_to=None,
    emoji=None,
    media=False,
    replies=False,
):
    safe_limit = max(1, min(int(limit or 100), 500))
    safe_offset = max(0, int(offset or 0))
    where, params = build_posts_filters(
        file_name,
        query=query,
        user=user,
        date_from=date_from,
        date_to=date_to,
        emoji=emoji,
        media=media,
        replies=replies,
    )

    with connect() as conn:
        indexed = conn.execute(
            "SELECT 1 FROM export_files WHERE file_name = ?",
            (file_name,),
        ).fetchone()
        if not indexed:
            return None

        total = conn.execute(
            f"SELECT COUNT(*) AS count FROM posts p WHERE {where}",
            params,
        ).fetchone()["count"]
        rows = conn.execute(
            f"""
            SELECT
                p.*,
                (SELECT COUNT(*) FROM comments c WHERE c.file_name = p.file_name AND c.post_id = p.post_id) AS comments_count
            FROM posts p
            WHERE {where}
            ORDER BY p.post_date DESC, p.post_id DESC
            LIMIT ? OFFSET ?
            """,
            params + [safe_limit, safe_offset],
        ).fetchall()

        posts = []
        for row in rows:
            post = post_row_to_json(conn, row)
            post["comments_count"] = row["comments_count"]
            posts.append(post)

    return {
        "total": total,
        "limit": safe_limit,
        "offset": safe_offset,
        "posts": posts,
    }


@index_operation
def get_filtered_summary(
    file_name,
    query=None,
    user=None,
    date_from=None,
    date_to=None,
    emoji=None,
    media=False,
    replies=False,
):
    where, params = build_posts_filters(
        file_name,
        query=query,
        user=user,
        date_from=date_from,
        date_to=date_to,
        emoji=emoji,
        media=media,
        replies=replies,
    )

    with connect() as conn:
        indexed = conn.execute(
            "SELECT 1 FROM export_files WHERE file_name = ?",
            (file_name,),
        ).fetchone()
        if not indexed:
            return None

        counts = conn.execute(
            f"""
            WITH filtered_posts AS (
                SELECT p.file_name, p.post_id
                FROM posts p
                WHERE {where}
            )
            SELECT
                (SELECT COUNT(*) FROM filtered_posts) AS posts_count,
                (
                    SELECT COUNT(*)
                    FROM comments c
                    JOIN filtered_posts fp
                        ON fp.file_name = c.file_name
                        AND fp.post_id = c.post_id
                ) AS comments_count,
                (
                    SELECT COUNT(DISTINCT c.user_id)
                    FROM comments c
                    JOIN filtered_posts fp
                        ON fp.file_name = c.file_name
                        AND fp.post_id = c.post_id
                    WHERE c.user_id IS NOT NULL
                ) AS unique_users_count,
                (
                    SELECT COALESCE(SUM(r.count), 0)
                    FROM reactions r
                    JOIN filtered_posts fp
                        ON fp.file_name = r.file_name
                        AND fp.post_id = r.post_id
                ) AS reactions_count
            """,
            params,
        ).fetchone()

    return {
        "posts_count": counts["posts_count"],
        "comments_count": counts["comments_count"],
        "unique_users_count": counts["unique_users_count"],
        "reactions_count": counts["reactions_count"],
    }


def build_posts_filters(
    file_name,
    query=None,
    user=None,
    date_from=None,
    date_to=None,
    emoji=None,
    media=False,
    replies=False,
):
    clauses = ["p.file_name = ?"]
    params = [file_name]
    needle = str(query or "").strip()

    if needle:
        like = f"%{needle}%"
        clauses.append(
            """
            (
                CAST(p.post_id AS TEXT) LIKE ? COLLATE NOCASE
                OR p.post_text LIKE ? COLLATE NOCASE
                OR p.post_date LIKE ? COLLATE NOCASE
                OR EXISTS (
                    SELECT 1 FROM comments c
                    WHERE c.file_name = p.file_name
                        AND c.post_id = p.post_id
                        AND (
                            CAST(c.comment_id AS TEXT) LIKE ? COLLATE NOCASE
                            OR c.comment_text LIKE ? COLLATE NOCASE
                            OR c.username LIKE ? COLLATE NOCASE
                            OR c.first_name LIKE ? COLLATE NOCASE
                            OR c.last_name LIKE ? COLLATE NOCASE
                            OR c.user_id LIKE ? COLLATE NOCASE
                        )
                )
            )
            """
        )
        params.extend([like, like, like, like, like, like, like, like, like])

    if user:
        clean_user = str(user).strip().lstrip("@")
        clauses.append(
            """
            EXISTS (
                SELECT 1 FROM comments c
                WHERE c.file_name = p.file_name
                    AND c.post_id = p.post_id
                    AND (c.user_id = ? OR c.username = ?)
            )
            """
        )
        params.extend([clean_user, clean_user])

    if date_from:
        clauses.append("p.post_date >= ?")
        params.append(normalize_date_filter(date_from, is_end=False))

    if date_to:
        clauses.append("p.post_date < ?")
        params.append(normalize_date_filter(date_to, is_end=True))

    if emoji:
        clauses.append(
            """
            EXISTS (
                SELECT 1 FROM reactions r
                WHERE r.file_name = p.file_name
                    AND r.post_id = p.post_id
                    AND r.emoji = ?
            )
            """
        )
        params.append(str(emoji))

    if media:
        clauses.append(
            """
            (
                p.post_media IS NOT NULL
                OR EXISTS (
                    SELECT 1 FROM comments c
                    WHERE c.file_name = p.file_name
                        AND c.post_id = p.post_id
                        AND c.comment_media IS NOT NULL
                )
            )
            """
        )

    if replies:
        clauses.append(
            """
            EXISTS (
                SELECT 1 FROM comments c
                WHERE c.file_name = p.file_name
                    AND c.post_id = p.post_id
                    AND c.reply_to_msg_id IS NOT NULL
            )
            """
        )

    return " AND ".join(clauses), params


def post_row_to_json(conn, post):
    result = {
        "post_id": post["post_id"],
        "post_date": post["post_date"],
        "post_text": post["post_text"],
        "post_views": post["post_views"],
        "post_forwards": post["post_forwards"],
        "post_link": post["post_link"],
        "post_media": post["post_media"],
        "post_reactions": reaction_rows(conn, post["file_name"], "post", post["post_id"]),
        "comments": [],
    }

    if post["post_media_error"]:
        result["post_media_error"] = post["post_media_error"]

    export_errors = decode_json_list(post["export_errors"])
    if export_errors:
        result["export_errors"] = export_errors

    return result


def search_comments(file_name, query, limit=20, date_from=None, date_to=None, user=None):
    needle = str(query or "").strip()
    if not needle:
        return []

    safe_limit = max(1, min(int(limit or 20), 200))
    fts_results = search_comments_fts(
        needle,
        safe_limit,
        file_name=file_name,
        date_from=date_from,
        date_to=date_to,
        user=user,
    )

    if fts_results:
        return fts_results

    return search_comments_like(
        needle,
        safe_limit,
        file_name=file_name,
        date_from=date_from,
        date_to=date_to,
        user=user,
    )


@index_operation
def search_comments_like(
    needle,
    limit=20,
    file_name=None,
    channel_key=None,
    date_from=None,
    date_to=None,
    user=None,
):
    pattern = f"%{needle}%"
    params = [pattern]
    file_clause = ""
    channel_clause = ""
    date_from_clause = ""
    date_to_clause = ""
    user_clause = ""

    if file_name:
        file_clause = "AND c.file_name = ?"
        params.append(file_name)

    if channel_key:
        channel_clause = "AND c.channel_key = ?"
        params.append(channel_key)

    if date_from:
        date_from_clause = "AND c.comment_date >= ?"
        params.append(normalize_date_filter(date_from, is_end=False))

    if date_to:
        date_to_clause = "AND c.comment_date < ?"
        params.append(normalize_date_filter(date_to, is_end=True))

    if user:
        user_clause = "AND (c.user_id = ? OR c.username = ?)"
        clean_user = str(user).strip().lstrip("@")
        params.extend([clean_user, clean_user])

    params.append(limit)

    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT
                c.file_name, c.channel_key, c.post_id, c.comment_id, c.comment_date, c.comment_text,
                c.user_id, c.username, c.first_name, c.last_name, c.comment_link, p.post_link
            FROM comments c
            JOIN posts p ON p.file_name = c.file_name AND p.post_id = c.post_id
            WHERE c.comment_text LIKE ? COLLATE NOCASE
                {file_clause}
                {channel_clause}
                {date_from_clause}
                {date_to_clause}
                {user_clause}
            ORDER BY c.comment_date DESC, c.file_name, c.comment_id DESC
            LIMIT ?
            """,
            params,
        ).fetchall()

    return [dict(row) for row in rows]


@index_operation
def search_comments_fts(
    needle,
    limit=20,
    file_name=None,
    channel_key=None,
    date_from=None,
    date_to=None,
    user=None,
):
    params = [needle]
    file_clause = ""
    channel_clause = ""
    date_from_clause = ""
    date_to_clause = ""
    user_clause = ""

    if file_name:
        file_clause = "AND comments_fts.file_name = ?"
        params.append(file_name)

    if channel_key:
        channel_clause = "AND comments_fts.channel_key = ?"
        params.append(channel_key)

    if date_from:
        date_from_clause = "AND c.comment_date >= ?"
        params.append(normalize_date_filter(date_from, is_end=False))

    if date_to:
        date_to_clause = "AND c.comment_date < ?"
        params.append(normalize_date_filter(date_to, is_end=True))

    if user:
        user_clause = "AND (c.user_id = ? OR c.username = ?)"
        clean_user = str(user).strip().lstrip("@")
        params.extend([clean_user, clean_user])

    params.append(limit)

    with connect() as conn:
        if not has_fts(conn):
            return None

        try:
            rows = conn.execute(
                f"""
                SELECT
                    c.file_name, c.channel_key, c.post_id, c.comment_id, c.comment_date,
                    c.comment_text, c.user_id, c.username, c.first_name, c.last_name, c.comment_link, p.post_link,
                    snippet(comments_fts, 4, '<mark>', '</mark>', '...', 12) AS snippet,
                    bm25(comments_fts) AS rank
                FROM comments_fts
                JOIN comments c
                    ON c.file_name = comments_fts.file_name
                    AND c.post_id = comments_fts.post_id
                    AND c.comment_id = comments_fts.comment_id
                JOIN posts p ON p.file_name = c.file_name AND p.post_id = c.post_id
                WHERE comments_fts MATCH ?
                    {file_clause}
                    {channel_clause}
                    {date_from_clause}
                    {date_to_clause}
                    {user_clause}
                ORDER BY rank, c.comment_date DESC, c.file_name, c.comment_id DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        except sqlite3.OperationalError:
            return None

    return [dict(row) for row in rows]


def normalize_date_filter(value, is_end=False):
    text = str(value or "").strip()
    if not text:
        return None

    if len(text) == 10:
        parsed = datetime.combine(datetime.fromisoformat(text).date(), datetime_time.min)
        if is_end:
            parsed += timedelta(days=1)
        return parsed.isoformat(sep=" ")

    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed.isoformat(sep=" ")


def search_all_comments(query, limit=20, channel_key=None, date_from=None, date_to=None, user=None):
    needle = str(query or "").strip()
    if not needle:
        return []

    safe_limit = max(1, min(int(limit or 20), 200))
    fts_results = search_comments_fts(
        needle,
        safe_limit,
        channel_key=channel_key,
        date_from=date_from,
        date_to=date_to,
        user=user,
    )

    if fts_results:
        return fts_results

    return search_comments_like(
        needle,
        safe_limit,
        channel_key=channel_key,
        date_from=date_from,
        date_to=date_to,
        user=user,
    )

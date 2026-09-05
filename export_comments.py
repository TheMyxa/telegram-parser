import argparse
import asyncio
import csv
import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path

from telethon import TelegramClient
from telethon.errors import FloodWaitError, RPCError
from telethon.tl.functions.messages import GetDiscussionMessageRequest

from config import (
    API_HASH,
    API_ID,
    CHANNEL,
    CHANNELS,
    INCREMENTAL_LOOKBACK_POSTS,
    OUTPUT_FILE as CONFIG_OUTPUT_FILE,
    POST_LIMIT,
    POSTS_PAUSE_AFTER_POSTS,
    POSTS_PAUSE_SECONDS,
    TELEGRAM_SESSION,
    POSTGRES_DB,
    POSTGRES_HOST,
    POSTGRES_PASSWORD,
    POSTGRES_PORT,
    POSTGRES_TABLE,
    POSTGRES_USER,
)


EXPORT_FORMATS = ("json", "csv", "postgresql", "parquet")
OUTPUT_DIR = os.path.dirname(CONFIG_OUTPUT_FILE) or "."
STATE_DIR = Path("data/state")
RETRY_ATTEMPTS = 3
RETRY_BASE_DELAY_SECONDS = 2


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Export Telegram post comments.")
    parser.add_argument(
        "export_format",
        nargs="?",
        choices=EXPORT_FORMATS,
        help="Export format: json, csv, postgresql, parquet.",
    )
    parser.add_argument(
        "--format",
        dest="format_flag",
        choices=EXPORT_FORMATS,
        help="Export format: json, csv, postgresql, parquet.",
    )
    parser.add_argument(
        "--download-media",
        action="store_true",
        help="Download post and comment media to data/content/<export_run_id>/.",
    )
    parser.add_argument(
        "--anonymize",
        action="store_true",
        help="Replace user_id, username, first_name and last_name with aliases from anonymizer file.",
    )
    parser.add_argument(
        "--anonymizer-file",
        default="anonymizer",
        help="Text file with anonymized names, one alias per line. Default: anonymizer.",
    )
    parser.add_argument(
        "--incremental",
        action="store_true",
        help="Update an existing channel dataset and download only missing media.",
    )
    args = parser.parse_args(argv)
    args.export_format = args.format_flag or args.export_format or "json"
    return args


def get_channel_name(channel):
    channel_name = str(channel).rstrip("/").split("/")[-1].lstrip("@")
    channel_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", channel_name).strip("_")
    return channel_name or "channel"


def get_channel_link_name(channel):
    channel_name = str(channel).rstrip("/").split("/")[-1].lstrip("@")
    return channel_name or str(channel).lstrip("@")


def build_post_link(channel, post_id):
    channel_name = get_channel_link_name(channel)
    return f"https://t.me/{channel_name}/{post_id}"


def build_message_link(chat, message_id):
    username = getattr(chat, "username", None)

    if username:
        return f"https://t.me/{username}/{message_id}"

    chat_id = str(getattr(chat, "id", "")).removeprefix("-100").removeprefix("-")

    if chat_id:
        return f"https://t.me/c/{chat_id}/{message_id}"

    return None


def build_export_target(channel, export_format):
    channel_name = get_channel_name(channel)
    saved_at = datetime.now().strftime("%Y%m%d_%H%M%S")
    export_run_id = f"{channel_name}_{saved_at}"

    if export_format == "postgresql":
        return {
            "format": export_format,
            "run_id": export_run_id,
            "path": None,
        }

    extension = "json" if export_format == "json" else export_format
    return {
        "format": export_format,
        "run_id": export_run_id,
        "path": os.path.join(OUTPUT_DIR, f"{export_run_id}.{extension}"),
    }


def build_incremental_export_target(channel, export_format):
    channel_name = get_channel_name(channel)
    export_run_id = f"{channel_name}_dataset"

    if export_format == "postgresql":
        return {
            "format": export_format,
            "run_id": export_run_id,
            "path": None,
        }

    extension = "json" if export_format == "json" else export_format
    return {
        "format": export_format,
        "run_id": export_run_id,
        "path": os.path.join(OUTPUT_DIR, f"{export_run_id}.{extension}"),
    }


def get_incremental_dataset_path(channel):
    return Path(OUTPUT_DIR) / f"{get_channel_name(channel)}_dataset.json"


def get_incremental_state_path(channel):
    return STATE_DIR / f"{get_channel_name(channel)}_state.json"


def build_content_dir(export_target):
    return Path("data/content") / export_target["run_id"]


def normalize_media_path(path):
    if not path:
        return None

    return str(Path(path).as_posix())


def existing_media_path(path):
    if not path:
        return None

    media_path = Path(path)

    if media_path.is_file():
        return normalize_media_path(media_path)

    return None


async def download_message_media(client, message, content_dir, prefix):
    if not message or not getattr(message, "media", None):
        return None

    media_dir = content_dir / prefix.rstrip("_")
    media_dir.mkdir(parents=True, exist_ok=True)
    media_path = await run_with_retries(
        f"Download media for message {getattr(message, 'id', 'unknown')}",
        lambda: client.download_media(message, file=str(media_dir)),
    )
    return normalize_media_path(media_path)


def extract_reactions(message):
    result = []

    if not message or not message.reactions:
        return result

    for reaction_count in message.reactions.results:
        reaction = reaction_count.reaction
        result.append({
            "emoji": getattr(reaction, "emoticon", None),
            "count": getattr(reaction_count, "count", 0),
        })

    return result


def load_json_dataset(path):
    dataset_path = Path(path)

    if not dataset_path.exists():
        return []

    try:
        with dataset_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        backup_path = backup_problem_file(dataset_path)
        print(f"Cannot read JSON dataset {dataset_path}: {e}. Backup saved to {backup_path}. Starting empty dataset.")
        return []

    if not isinstance(data, list):
        raise ValueError(f"Dataset must contain a JSON list: {dataset_path}")

    return data


def load_incremental_state(channel):
    state_path = get_incremental_state_path(channel)

    if not state_path.exists():
        return {}

    try:
        with state_path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        backup_path = backup_problem_file(state_path)
        print(f"Cannot read incremental state {state_path}: {e}. Backup saved to {backup_path}. Starting empty state.")
        return {}


def backup_problem_file(path):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = path.with_name(f"{path.name}.bak_{timestamp}")
    shutil.copy2(path, backup_path)
    return backup_path


def save_incremental_state(channel, export_target, export_data):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    state_path = get_incremental_state_path(channel)
    last_post_id = get_last_post_id(export_data)
    payload = {
        "channel": str(channel),
        "last_post_id": last_post_id,
        "dataset_path": str(get_incremental_dataset_path(channel).as_posix()),
        "export_format": export_target["format"],
        "export_target": describe_export_target(export_target),
        "lookback_posts": INCREMENTAL_LOOKBACK_POSTS,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }

    write_json_atomic(payload, state_path)


def get_last_post_id(export_data):
    post_ids = [
        post.get("post_id")
        for post in export_data
        if isinstance(post, dict) and isinstance(post.get("post_id"), int)
    ]
    return max(post_ids) if post_ids else None


def merge_post(existing_post, new_post):
    if not existing_post:
        return new_post

    merged_post = {**existing_post, **new_post}
    existing_comments = {
        comment.get("comment_id"): comment
        for comment in existing_post.get("comments", [])
        if isinstance(comment, dict)
    }

    for comment in new_post.get("comments", []):
        comment_id = comment.get("comment_id")
        if comment_id in existing_comments:
            existing_comments[comment_id] = {**existing_comments[comment_id], **comment}
        else:
            existing_comments[comment_id] = comment

    merged_comments = sorted(
        existing_comments.values(),
        key=lambda item: item.get("comment_date") or "",
    )
    merged_post["comments"] = merged_comments
    return merged_post


def merge_export_data(existing_data, new_data):
    posts_by_id = {
        post.get("post_id"): post
        for post in existing_data
        if isinstance(post, dict)
    }

    for post in new_data:
        post_id = post.get("post_id")
        posts_by_id[post_id] = merge_post(posts_by_id.get(post_id), post)

    return sorted(
        posts_by_id.values(),
        key=lambda item: item.get("post_id") or 0,
        reverse=True,
    )


class UserAnonymizer:
    def __init__(self, path):
        self.aliases = self.load_aliases(path)
        self.mapping = {}

    @staticmethod
    def load_aliases(path):
        alias_path = Path(path)

        if not alias_path.exists():
            raise FileNotFoundError(f"Anonymizer file not found: {path}")

        aliases = [
            line.strip()
            for line in alias_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]

        if not aliases:
            raise ValueError(f"Anonymizer file is empty: {path}")

        return aliases

    def get_alias(self, user_id):
        key = str(user_id)

        if key not in self.mapping:
            index = len(self.mapping)
            base_alias = self.aliases[index % len(self.aliases)]
            suffix = "" if index < len(self.aliases) else f"_{index + 1}"
            alias = f"{base_alias}{suffix}"

            self.mapping[key] = {
                "user_id": index + 1,
                "username": f"user_{index + 1}",
                "first_name": alias,
                "last_name": None,
            }

        return self.mapping[key]

    def anonymize_user(self, user_data):
        if not user_data:
            return None

        alias = self.get_alias(user_data["user_id"])

        return {
            **user_data,
            "user_id": alias["user_id"],
            "username": alias["username"],
            "first_name": alias["first_name"],
            "last_name": alias["last_name"],
        }


def user_to_dict(user, anonymizer=None):
    if not user:
        return None

    user_data = {
        "user_id": user.id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "bot": user.bot,
        "premium": getattr(user, "premium", None),
    }

    if anonymizer:
        return anonymizer.anonymize_user(user_data)

    return user_data


def flatten_export_data(export_data, export_run_id):
    rows = []

    for post in export_data:
        comments = post.get("comments") or [None]

        for comment in comments:
            user = (comment or {}).get("user") or {}
            rows.append({
                "export_run_id": export_run_id,
                "post_id": post.get("post_id"),
                "post_date": post.get("post_date"),
                "post_text": post.get("post_text"),
                "post_views": post.get("post_views"),
                "post_forwards": post.get("post_forwards"),
                "post_link": post.get("post_link"),
                "post_media": post.get("post_media"),
                "post_reactions": json.dumps(post.get("post_reactions", []), ensure_ascii=False),
                "comment_id": (comment or {}).get("comment_id"),
                "comment_date": (comment or {}).get("comment_date"),
                "comment_text": (comment or {}).get("comment_text"),
                "comment_link": (comment or {}).get("comment_link"),
                "comment_media": (comment or {}).get("comment_media"),
                "reply_to_msg_id": (comment or {}).get("reply_to_msg_id"),
                "comment_reactions": json.dumps((comment or {}).get("comment_reactions", []), ensure_ascii=False),
                "user_id": user.get("user_id"),
                "username": user.get("username"),
                "first_name": user.get("first_name"),
                "last_name": user.get("last_name"),
                "bot": user.get("bot"),
                "premium": user.get("premium"),
            })

    return rows


def validate_postgres_identifier(value):
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", value):
        raise ValueError(f"Invalid PostgreSQL identifier: {value}")

    return value


def ensure_parent_dir(path):
    parent = os.path.dirname(path)

    if parent:
        os.makedirs(parent, exist_ok=True)


def write_json_atomic(data, path):
    target_path = Path(path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = target_path.with_name(f"{target_path.name}.tmp")

    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=5)

    os.replace(tmp_path, target_path)


def save_json(export_data, path):
    write_json_atomic(export_data, path)


def save_csv(export_data, path, export_run_id):
    rows = flatten_export_data(export_data, export_run_id)
    ensure_parent_dir(path)

    fieldnames = [
        "export_run_id",
        "post_id",
        "post_date",
        "post_text",
        "post_views",
        "post_forwards",
        "post_link",
        "post_media",
        "post_reactions",
        "comment_id",
        "comment_date",
        "comment_text",
        "comment_link",
        "comment_media",
        "reply_to_msg_id",
        "comment_reactions",
        "user_id",
        "username",
        "first_name",
        "last_name",
        "bot",
        "premium",
    ]

    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def save_parquet(export_data, path, export_run_id):
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as e:
        raise RuntimeError("Parquet export requires pyarrow. Run: pip install pyarrow") from e

    rows = flatten_export_data(export_data, export_run_id)
    ensure_parent_dir(path)

    table = pa.Table.from_pylist(rows)
    pq.write_table(table, path)


def save_postgresql(export_data, export_run_id):
    try:
        import psycopg2
        from psycopg2.extras import Json, execute_values
    except ImportError as e:
        raise RuntimeError("PostgreSQL export requires psycopg2-binary. Run: pip install psycopg2-binary") from e

    rows = flatten_export_data(export_data, export_run_id)
    columns = [
        "export_run_id",
        "post_id",
        "post_date",
        "post_text",
        "post_views",
        "post_forwards",
        "post_link",
        "post_media",
        "post_reactions",
        "comment_id",
        "comment_date",
        "comment_text",
        "comment_link",
        "comment_media",
        "reply_to_msg_id",
        "comment_reactions",
        "user_id",
        "username",
        "first_name",
        "last_name",
        "bot",
        "premium",
    ]

    table_name = validate_postgres_identifier(POSTGRES_TABLE)
    create_table_sql = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            export_run_id TEXT NOT NULL,
            post_id BIGINT,
            post_date TEXT,
            post_text TEXT,
            post_views BIGINT,
            post_forwards BIGINT,
            post_link TEXT,
            post_media TEXT,
            post_reactions JSONB,
            comment_id BIGINT,
            comment_date TEXT,
            comment_text TEXT,
            comment_link TEXT,
            comment_media TEXT,
            reply_to_msg_id BIGINT,
            comment_reactions JSONB,
            user_id BIGINT,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            bot BOOLEAN,
            premium BOOLEAN
        )
    """
    alter_table_sql = [
        f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS post_link TEXT",
        f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS post_media TEXT",
        f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS comment_link TEXT",
        f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS comment_media TEXT",
    ]

    values = []

    for row in rows:
        values.append([
            Json(json.loads(row[column])) if column in ("post_reactions", "comment_reactions") else row[column]
            for column in columns
        ])

    with psycopg2.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        dbname=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(create_table_sql)
            for statement in alter_table_sql:
                cur.execute(statement)
            cur.execute(f"DELETE FROM {table_name} WHERE export_run_id = %s", (export_run_id,))

            if values:
                execute_values(
                    cur,
                    f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES %s",
                    values,
                )


def save_export_data(export_data, export_target):
    export_format = export_target["format"]
    export_run_id = export_target["run_id"]
    path = export_target["path"]

    if export_format == "json":
        save_json(export_data, path)
    elif export_format == "csv":
        save_csv(export_data, path, export_run_id)
    elif export_format == "parquet":
        save_parquet(export_data, path, export_run_id)
    elif export_format == "postgresql":
        save_postgresql(export_data, export_run_id)
    else:
        raise ValueError(f"Unsupported export format: {export_format}")


def save_incremental_export_data(export_data, export_target, channel):
    dataset_path = get_incremental_dataset_path(channel)
    save_json(export_data, str(dataset_path))

    if export_target["format"] != "json":
        save_export_data(export_data, export_target)

    save_incremental_state(channel, export_target, export_data)


def describe_export_target(export_target):
    if export_target["format"] == "postgresql":
        return f"PostgreSQL table {POSTGRES_TABLE}, run_id={export_target['run_id']}"

    return export_target["path"]


async def safe_sleep(seconds=1):
    await asyncio.sleep(seconds)


def is_retryable_error(error):
    return isinstance(error, (OSError, TimeoutError, asyncio.TimeoutError, RPCError))


async def run_with_retries(label, operation, attempts=RETRY_ATTEMPTS):
    last_error = None

    for attempt in range(1, attempts + 1):
        try:
            return await operation()
        except FloodWaitError:
            raise
        except Exception as e:
            if not is_retryable_error(e) or attempt == attempts:
                raise

            last_error = e
            delay = RETRY_BASE_DELAY_SECONDS * attempt
            print(f"{label} failed ({attempt}/{attempts}): {e}. Retrying in {delay} seconds.")
            await safe_sleep(delay)

    raise last_error


async def pause_after_processed_posts(processed_posts):
    should_pause = (
        processed_posts > 0
        and POSTS_PAUSE_AFTER_POSTS > 0
        and processed_posts % POSTS_PAUSE_AFTER_POSTS == 0
    )

    if should_pause and POSTS_PAUSE_SECONDS > 0:
        print(f"Processed {processed_posts} posts. Sleeping {POSTS_PAUSE_SECONDS} seconds.")
        await safe_sleep(POSTS_PAUSE_SECONDS)


async def fetch_posts_for_export(client, channel, incremental, last_post_id):
    if not incremental or not last_post_id:
        posts = await run_with_retries(
            f"Get posts for channel {channel}",
            lambda: client.get_messages(channel, limit=POST_LIMIT),
        )
        return list(posts)

    async def collect_incremental_posts():
        posts = []
        new_posts = 0
        old_posts = 0
        max_posts = POST_LIMIT + INCREMENTAL_LOOKBACK_POSTS

        async for post in client.iter_messages(channel):
            if post.id > last_post_id:
                if new_posts >= POST_LIMIT:
                    break

                posts.append(post)
                new_posts += 1
            else:
                if old_posts >= INCREMENTAL_LOOKBACK_POSTS:
                    break

                posts.append(post)
                old_posts += 1

            if len(posts) >= max_posts:
                break

        print(
            "Incremental scan:",
            f"new_posts={new_posts}",
            f"lookback_posts={old_posts}",
            f"last_post_id={last_post_id}",
        )
        return posts

    return await run_with_retries(
        f"Get incremental posts for channel {channel}",
        collect_incremental_posts,
    )


async def export_channel(client, channel, args, anonymizer):
    channel_errors = []
    incremental = getattr(args, "incremental", False)
    if incremental:
        export_target = build_incremental_export_target(channel, args.export_format)
        dataset_path = get_incremental_dataset_path(channel)
        existing_data = load_json_dataset(dataset_path)
        incremental_state = load_incremental_state(channel)
    else:
        export_target = build_export_target(channel, args.export_format)
        dataset_path = None
        existing_data = []
        incremental_state = {}

    content_dir = build_content_dir(export_target)

    print("Channel:", channel)
    print("Export format:", args.export_format)
    print("Export target:", describe_export_target(export_target))
    print("Incremental export:", incremental)
    if incremental:
        print("Dataset path:", dataset_path)
        print("Existing posts:", len(existing_data))
        print("Last post_id:", get_last_post_id(existing_data) or incremental_state.get("last_post_id"))
        print("Incremental lookback posts:", INCREMENTAL_LOOKBACK_POSTS)
    print("Download media:", args.download_media)
    print("Anonymize users:", args.anonymize)
    if args.download_media:
        print("Content dir:", content_dir)

    export_data = []
    existing_posts = {
        post.get("post_id"): post
        for post in existing_data
        if isinstance(post, dict)
    }
    processed_posts = 0

    def current_export_data(extra_post=None):
        collected = export_data + ([extra_post] if extra_post else [])

        if incremental:
            return merge_export_data(existing_data, collected)

        return collected

    def save_current_export(extra_post=None):
        data = current_export_data(extra_post)

        if incremental:
            save_incremental_export_data(data, export_target, channel)
        else:
            save_export_data(data, export_target)

    try:
        last_post_id = get_last_post_id(existing_data) or incremental_state.get("last_post_id")
        posts = await fetch_posts_for_export(client, channel, incremental, last_post_id)

        for post in posts:
            post_errors = []
            existing_post = existing_posts.get(post.id) or {}
            post_media = existing_media_path(existing_post.get("post_media"))
            post_data = {
                "post_id": post.id,
                "post_date": str(post.date),
                "post_text": post.text,
                "post_views": post.views,
                "post_forwards": post.forwards,
                "post_link": build_post_link(channel, post.id),
                "post_media": post_media,
                "post_reactions": extract_reactions(post),
                "comments": [],
            }
            existing_comments = {
                comment.get("comment_id"): comment
                for comment in existing_post.get("comments", [])
                if isinstance(comment, dict)
            }

            print(f"Processing post {post.id}")
            if args.download_media and not post_data["post_media"]:
                try:
                    post_data["post_media"] = await download_message_media(
                        client,
                        post,
                        content_dir,
                        f"post_{post.id}_",
                    )
                except Exception as e:
                    error_message = f"Post media download failed: {e}"
                    print(f"Post {post.id}: {error_message}")
                    post_data["post_media_error"] = error_message
                    post_errors.append(error_message)
            await safe_sleep(1)

            if not post.replies:
                print(f"Post {post.id} has no comments")
                if post_errors:
                    post_data["export_errors"] = post_errors
                export_data.append(post_data)
                processed_posts += 1
                await pause_after_processed_posts(processed_posts)
                continue

            try:
                discussion = await run_with_retries(
                    f"Get discussion for post {post.id}",
                    lambda: client(
                        GetDiscussionMessageRequest(
                            peer=channel,
                            msg_id=post.id,
                        )
                    ),
                )

                await safe_sleep(1)

                if not discussion.chats or not discussion.messages:
                    if post_errors:
                        post_data["export_errors"] = post_errors
                    export_data.append(post_data)
                    processed_posts += 1
                    await pause_after_processed_posts(processed_posts)
                    continue

                discussion_chat = discussion.chats[0]
                root_message_id = discussion.messages[0].id

                async for comment in client.iter_messages(
                    discussion_chat,
                    reply_to=root_message_id,
                ):
                    try:
                        sender = await run_with_retries(
                            f"Get sender for comment {comment.id}",
                            lambda: comment.get_sender(),
                        )
                    except Exception as e:
                        error_message = f"Comment sender fetch failed: {e}"
                        print(f"Post {post.id}, comment {comment.id}: {error_message}")
                        sender = None

                    comment_data = {
                        "comment_id": comment.id,
                        "comment_date": str(comment.date),
                        "comment_text": comment.text,
                        "comment_link": build_message_link(discussion_chat, comment.id),
                        "comment_media": existing_media_path(
                            (existing_comments.get(comment.id) or {}).get("comment_media")
                        ),
                        "reply_to_msg_id": comment.reply_to_msg_id,
                        "comment_reactions": extract_reactions(comment),
                        "user": user_to_dict(sender, anonymizer),
                    }

                    if args.download_media and not comment_data["comment_media"]:
                        try:
                            comment_data["comment_media"] = await download_message_media(
                                client,
                                comment,
                                content_dir,
                                f"post_{post.id}_comment_{comment.id}_",
                            )
                        except Exception as e:
                            error_message = f"Comment media download failed: {e}"
                            print(f"Post {post.id}, comment {comment.id}: {error_message}")
                            comment_data["comment_media_error"] = error_message

                    post_data["comments"].append(comment_data)
                    await safe_sleep(1)

            except FloodWaitError as e:
                print(f"FloodWaitError: Telegram requested wait for {e.seconds} seconds")
                save_current_export(post_data)
                print(f"Partial export saved to {describe_export_target(export_target)}")
                await asyncio.sleep(e.seconds)

            except Exception as e:
                error_message = f"Error while processing post {post.id}: {e}"
                print(error_message)
                post_errors.append(error_message)

            if post_errors:
                post_data["export_errors"] = post_errors
            export_data.append(post_data)
            processed_posts += 1
            await pause_after_processed_posts(processed_posts)
            await safe_sleep(1)

    except FloodWaitError as e:
        error_message = f"FloodWaitError: Telegram requested wait for {e.seconds} seconds"
        print(error_message)
        channel_errors.append(error_message)
        save_current_export()
        print(f"Partial export saved to {describe_export_target(export_target)}")
        await asyncio.sleep(e.seconds)

    except Exception as e:
        error_message = f"Channel {channel} failed: {e}"
        print(error_message)
        channel_errors.append(error_message)
        save_current_export()
        print(f"Partial export saved to {describe_export_target(export_target)}")

    save_current_export()
    print(f"Done. Saved to {describe_export_target(export_target)}")
    return {
        "channel": str(channel),
        "ok": not channel_errors,
        "posts_processed": processed_posts,
        "errors_count": len(channel_errors),
        "errors": channel_errors,
        "output": describe_export_target(export_target),
    }


async def main(args=None):
    if args is None:
        args = parse_args()

    if not CHANNELS:
        raise RuntimeError("Missing required config value: CHANNEL")

    anonymizer = UserAnonymizer(args.anonymizer_file) if args.anonymize else None

    await asyncio.sleep(2)

    print("Channels:", ", ".join(CHANNELS))
    print("API_ID =", API_ID)
    print("API_HASH length =", len(API_HASH))
    print("Current working dir:", os.getcwd())
    print("Session file:", os.path.abspath(TELEGRAM_SESSION))
    print("Data path:", os.path.abspath("data"))

    session_parent = Path(TELEGRAM_SESSION).parent
    if str(session_parent) not in ("", "."):
        session_parent.mkdir(parents=True, exist_ok=True)

    client = TelegramClient(TELEGRAM_SESSION, API_ID, API_HASH)
    await client.start()

    try:
        summaries = []
        for channel in CHANNELS:
            print("")
            try:
                summary = await export_channel(client, channel, args, anonymizer)
            except Exception as e:
                error_message = f"Channel {channel} failed before export could start: {e}"
                print(error_message)
                summary = {
                    "channel": str(channel),
                    "ok": False,
                    "posts_processed": 0,
                    "errors_count": 1,
                    "errors": [error_message],
                    "output": None,
                }
            summaries.append(summary)
            print("CHANNEL_STATUS", json.dumps(summary, ensure_ascii=False))
    finally:
        await client.disconnect()

    failed_channels = [summary for summary in summaries if not summary["ok"]]
    final_summary = {
        "channels_total": len(summaries),
        "channels_ok": len(summaries) - len(failed_channels),
        "channels_failed": len(failed_channels),
        "failed_channels": [summary["channel"] for summary in failed_channels],
    }
    print("EXPORT_SUMMARY", json.dumps(final_summary, ensure_ascii=False))

    if summaries and len(failed_channels) == len(summaries):
        raise RuntimeError("All channel exports failed")


if __name__ == "__main__":
    asyncio.run(main())

import argparse
import asyncio
import csv
import json
import os
import re
from datetime import datetime
from pathlib import Path

from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.tl.functions.messages import GetDiscussionMessageRequest

from config import (
    API_HASH,
    API_ID,
    CHANNEL,
    OUTPUT_FILE as CONFIG_OUTPUT_FILE,
    PAUSE_AFTER_500_POSTS_SECONDS,
    PAUSE_AFTER_1000_POSTS_SECONDS,
    POST_LIMIT,
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
    media_path = await client.download_media(message, file=str(media_dir))
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

    with dataset_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError(f"Dataset must contain a JSON list: {dataset_path}")

    return data


def load_incremental_state(channel):
    state_path = get_incremental_state_path(channel)

    if not state_path.exists():
        return {}

    with state_path.open("r", encoding="utf-8") as f:
        return json.load(f)


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
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }

    with state_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


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


def save_json(export_data, path):
    ensure_parent_dir(path)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(export_data, f, ensure_ascii=False, indent=5)


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


async def pause_after_processed_posts(processed_posts):
    pause_seconds = 0

    if processed_posts > 0 and processed_posts % 1000 == 0:
        pause_seconds = PAUSE_AFTER_1000_POSTS_SECONDS
    elif processed_posts > 0 and processed_posts % 500 == 0:
        pause_seconds = PAUSE_AFTER_500_POSTS_SECONDS

    if pause_seconds > 0:
        print(f"Processed {processed_posts} posts. Sleeping {pause_seconds} seconds.")
        await safe_sleep(pause_seconds)


async def main(args=None):
    if args is None:
        args = parse_args()

    incremental = getattr(args, "incremental", False)
    if incremental:
        export_target = build_incremental_export_target(CHANNEL, args.export_format)
        dataset_path = get_incremental_dataset_path(CHANNEL)
        existing_data = load_json_dataset(dataset_path)
        incremental_state = load_incremental_state(CHANNEL)
    else:
        export_target = build_export_target(CHANNEL, args.export_format)
        dataset_path = None
        existing_data = []
        incremental_state = {}

    content_dir = build_content_dir(export_target)
    anonymizer = UserAnonymizer(args.anonymizer_file) if args.anonymize else None

    await asyncio.sleep(2)

    print("Export format:", args.export_format)
    print("Export target:", describe_export_target(export_target))
    print("Incremental export:", incremental)
    if incremental:
        print("Dataset path:", dataset_path)
        print("Existing posts:", len(existing_data))
        print("Last post_id:", get_last_post_id(existing_data) or incremental_state.get("last_post_id"))
    print("Download media:", args.download_media)
    print("Anonymize users:", args.anonymize)
    if args.download_media:
        print("Content dir:", content_dir)
    print("API_ID =", API_ID)
    print("API_HASH length =", len(API_HASH))
    print("Current working dir:", os.getcwd())
    print("Session path:", os.path.abspath("sessions"))
    print("Data path:", os.path.abspath("data"))

    client = TelegramClient("/app/sessions/session_el_liz00", API_ID, API_HASH)
    await client.start()

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
            save_incremental_export_data(data, export_target, CHANNEL)
        else:
            save_export_data(data, export_target)

    try:
        posts = await client.get_messages(CHANNEL, limit=POST_LIMIT)

        for post in posts:
            existing_post = existing_posts.get(post.id) or {}
            post_media = existing_media_path(existing_post.get("post_media"))
            post_data = {
                "post_id": post.id,
                "post_date": str(post.date),
                "post_text": post.text,
                "post_views": post.views,
                "post_forwards": post.forwards,
                "post_link": build_post_link(CHANNEL, post.id),
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
                post_data["post_media"] = await download_message_media(
                    client,
                    post,
                    content_dir,
                    f"post_{post.id}_",
                )
            await safe_sleep(1)

            if not post.replies:
                print(f"Post {post.id} has no comments")
                export_data.append(post_data)
                processed_posts += 1
                await pause_after_processed_posts(processed_posts)
                continue

            try:
                discussion = await client(
                    GetDiscussionMessageRequest(
                        peer=CHANNEL,
                        msg_id=post.id,
                    )
                )

                await safe_sleep(1)

                if not discussion.chats or not discussion.messages:
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
                    sender = await comment.get_sender()

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
                        comment_data["comment_media"] = await download_message_media(
                            client,
                            comment,
                            content_dir,
                            f"post_{post.id}_comment_{comment.id}_",
                        )

                    post_data["comments"].append(comment_data)
                    await safe_sleep(1)

            except FloodWaitError as e:
                print(f"FloodWaitError: Telegram requested wait for {e.seconds} seconds")
                save_current_export(post_data)
                print(f"Partial export saved to {describe_export_target(export_target)}")
                await asyncio.sleep(e.seconds)

            except Exception as e:
                print(f"Error while processing post {post.id}: {e}")

            export_data.append(post_data)
            processed_posts += 1
            await pause_after_processed_posts(processed_posts)
            await safe_sleep(1)

    except FloodWaitError as e:
        print(f"FloodWaitError: Telegram requested wait for {e.seconds} seconds")
        save_current_export()
        print(f"Partial export saved to {describe_export_target(export_target)}")
        await asyncio.sleep(e.seconds)

    finally:
        await client.disconnect()

    save_current_export()
    print(f"Done. Saved to {describe_export_target(export_target)}")


if __name__ == "__main__":
    asyncio.run(main())

import json
from datetime import datetime, time, timezone
from pathlib import Path


def parse_period_date(value, is_end=False):
    if not value:
        raise ValueError("Period date is required")

    text = str(value).strip()

    if len(text) == 10:
        parsed = datetime.combine(datetime.fromisoformat(text).date(), time.min)
    else:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))

    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)

    return parsed


def parse_export_datetime(value):
    if not value:
        return None

    text = str(value).strip()

    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None

    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)

    return parsed


def sum_reactions(reactions):
    total = 0

    for reaction in reactions or []:
        if isinstance(reaction, dict):
            total += int(reaction.get("count") or 0)

    return total


def collect_period_metrics(posts, start, end):
    users = set()
    comments_count = 0
    reactions_count = 0

    for post in posts:
        if not isinstance(post, dict):
            continue

        for comment in post.get("comments") or []:
            if not isinstance(comment, dict):
                continue

            comment_date = parse_export_datetime(comment.get("comment_date"))

            if not comment_date or comment_date < start or comment_date >= end:
                continue

            comments_count += 1
            reactions_count += sum_reactions(comment.get("comment_reactions"))

            user = comment.get("user") or {}
            user_id = user.get("user_id")

            if user_id:
                users.add(str(user_id))

    return {
        "comments": comments_count,
        "users": len(users),
        "reactions": reactions_count,
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


def compare_periods(posts, from_date, to_date):
    current_start = parse_period_date(from_date)
    current_end = parse_period_date(to_date, is_end=True)

    if current_end <= current_start:
        raise ValueError("--to must be later than --from")

    duration = current_end - current_start
    previous_start = current_start - duration
    previous_end = current_start
    current = collect_period_metrics(posts, current_start, current_end)
    previous = collect_period_metrics(posts, previous_start, previous_end)

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


def load_posts(path):
    source = Path(path)

    with source.open("r", encoding="utf-8") as f:
        posts = json.load(f)

    if not isinstance(posts, list):
        raise ValueError(f"Export JSON must contain a list of posts: {path}")

    return posts

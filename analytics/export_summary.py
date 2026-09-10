import re
from pathlib import Path


def extract_channel_from_export_name(file_name):
    stem = Path(file_name).stem

    if stem.endswith("_dataset"):
        return stem.removesuffix("_dataset")

    match = re.match(r"^(.+)_\d{8}_\d{6}$", stem)
    if match:
        candidate = match.group(1).rstrip("_")
        if candidate:
            return candidate

    return stem


def summarize_export_posts(posts):
    comments_count = 0
    reactions_count = 0
    users = set()

    for post in posts:
        if not isinstance(post, dict):
            continue

        for reaction in post.get("post_reactions") or []:
            if isinstance(reaction, dict):
                reactions_count += int(reaction.get("count") or 0)

        for comment in post.get("comments") or []:
            if not isinstance(comment, dict):
                continue

            comments_count += 1

            for reaction in comment.get("comment_reactions") or []:
                if isinstance(reaction, dict):
                    reactions_count += int(reaction.get("count") or 0)

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

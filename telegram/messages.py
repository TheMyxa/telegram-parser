import re

from telegram.anonymization import UserAnonymizer


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


def user_to_dict(user, anonymizer=None, channel=None):
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
        return anonymizer.anonymize_user(user_data, channel)

    return user_data

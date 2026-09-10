import re


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


class UserAnonymizer:
    def __init__(self, path):
        self.aliases = self.load_aliases(path)
        self.mapping = {}

    @staticmethod
    def load_aliases(path):
        from pathlib import Path

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

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ExportConfig:
    api_id: int
    api_hash: str
    channel: str
    channels: list[str]
    telegram_session: str
    output_file: str
    post_limit: int
    incremental_lookback_posts: int
    posts_pause_seconds: int
    posts_pause_after_posts: int


@dataclass(frozen=True)
class LlmConfig:
    endpoint: str
    model: str


@dataclass(frozen=True)
class PostgresConfig:
    host: str
    port: int
    db: str
    user: str
    password: str
    table: str


def load_dotenv(path=".env"):
    env_path = Path(path)

    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        os.environ.setdefault(key, value)


def get_required(name):
    value = os.getenv(name)

    if not value:
        raise RuntimeError(f"Missing required config value: {name}")

    return value


def get_int(name, default):
    value = os.getenv(name)

    if value is None or value == "":
        return default

    return int(value)


def get_required_int(name):
    return int(get_required(name))


def get_first_int(names, default):
    for name in names:
        value = os.getenv(name)

        if value is not None and value != "":
            return int(value)

    return default


def parse_list(value):
    return [
        item.strip()
        for item in value.replace("\n", ",").replace(";", ",").split(",")
        if item.strip()
    ]


def load_export_config():
    channel = get_required("CHANNEL")
    channels = parse_list(channel)

    if not channels:
        raise RuntimeError("Missing required config value: CHANNEL")

    return ExportConfig(
        api_id=get_required_int("API_ID"),
        api_hash=get_required("API_HASH"),
        channel=channel,
        channels=channels,
        telegram_session=os.getenv("TELEGRAM_SESSION", "sessions/session"),
        output_file=os.getenv("OUTPUT_FILE", "data/raw/export.json"),
        post_limit=get_int("POST_LIMIT", 500),
        incremental_lookback_posts=get_int("INCREMENTAL_LOOKBACK_POSTS", 50),
        posts_pause_seconds=get_first_int(
            ("POSTS_PAUSE_SECONDS", "PAUSE_AFTER_500_POSTS_SECONDS", "PAUSE_AFTER_1000_POSTS_SECONDS"),
            30,
        ),
        posts_pause_after_posts=get_int("POSTS_PAUSE_AFTER_POSTS", 500),
    )


def load_llm_config():
    return LlmConfig(
        endpoint=get_required("LLM_ENDPOINT"),
        model=get_required("LLM_MODEL"),
    )


def load_postgres_config():
    return PostgresConfig(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=get_int("POSTGRES_PORT", 5432),
        db=os.getenv("POSTGRES_DB", "telegram_parser"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", ""),
        table=os.getenv("POSTGRES_TABLE", "telegram_comments_export"),
    )


load_dotenv()

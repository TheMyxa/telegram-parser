import os
from pathlib import Path


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


def parse_list(value):
    return [
        item.strip()
        for item in value.replace("\n", ",").replace(";", ",").split(",")
        if item.strip()
    ]


load_dotenv()

API_ID = get_required_int("API_ID")
API_HASH = get_required("API_HASH")

CHANNEL = get_required("CHANNEL")
CHANNELS = parse_list(CHANNEL)
TELEGRAM_SESSION = os.getenv("TELEGRAM_SESSION", "sessions/session")
OUTPUT_FILE = os.getenv("OUTPUT_FILE", "data/raw/export.json")

POST_LIMIT = get_int("POST_LIMIT", 500)
INCREMENTAL_LOOKBACK_POSTS = get_int("INCREMENTAL_LOOKBACK_POSTS", 50)
POSTS_PAUSE_SECONDS = get_int(
    "POSTS_PAUSE_SECONDS",
    get_int("PAUSE_AFTER_500_POSTS_SECONDS", get_int("PAUSE_AFTER_1000_POSTS_SECONDS", 30)),
)
POSTS_PAUSE_AFTER_POSTS = get_int("POSTS_PAUSE_AFTER_POSTS", 500)

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = get_int("POSTGRES_PORT", 5432)
POSTGRES_DB = os.getenv("POSTGRES_DB", "telegram_parser")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")
POSTGRES_TABLE = os.getenv("POSTGRES_TABLE", "telegram_comments_export")

LLM_ENDPOINT = get_required("LLM_ENDPOINT")
LLM_MODEL = get_required("LLM_MODEL")

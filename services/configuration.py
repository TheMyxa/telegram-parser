"""Dashboard environment configuration and validation."""
import os
from pathlib import Path
from services.paths import ROOT

ENV_FILE = Path(os.getenv("TG_ENV_FILE", str(ROOT / ".env")))
ENV_EXAMPLE_FILE = ROOT / ".env.example"
CONFIG_KEYS = [
    "API_ID",
    "API_HASH",
    "CHANNEL",
    "TELEGRAM_SESSION",
    "OUTPUT_FILE",
    "POST_LIMIT",
    "INCREMENTAL_LOOKBACK_POSTS",
    "POSTS_PAUSE_SECONDS",
    "POSTS_PAUSE_AFTER_POSTS",
    "POSTGRES_HOST",
    "POSTGRES_PORT",
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_TABLE",
    "LLM_ENDPOINT",
    "LLM_MODEL",
]
INT_CONFIG_KEYS = {
    "API_ID",
    "POST_LIMIT",
    "INCREMENTAL_LOOKBACK_POSTS",
    "POSTS_PAUSE_SECONDS",
    "POSTS_PAUSE_AFTER_POSTS",
    "POSTGRES_PORT",
}


def ensure_env_file():
    if ENV_FILE.exists() or os.getenv("TG_BOOTSTRAP_ENV", "").lower() not in {"1", "true", "yes"}:
        return

    if not ENV_EXAMPLE_FILE.exists():
        return

    ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
    ENV_FILE.write_text(ENV_EXAMPLE_FILE.read_text(encoding="utf-8"), encoding="utf-8")


def parse_env_file(path=ENV_FILE):
    values = {}

    if not path.exists():
        return values

    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()

        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue

        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key:
            values[key] = value

    return values


def read_config():
    file_values = parse_env_file()
    config = {}

    for key in CONFIG_KEYS:
        config[key] = file_values.get(key, os.getenv(key, ""))

    return config


def normalize_config_payload(payload):
    if not isinstance(payload, dict):
        raise ValueError("Config payload must be an object")

    normalized = {}

    for key in CONFIG_KEYS:
        if key not in payload:
            continue

        value = "" if payload[key] is None else str(payload[key]).strip()

        if "\n" in value or "\r" in value:
            raise ValueError(f"{key} cannot contain new lines")

        if key in INT_CONFIG_KEYS and value:
            try:
                int(value)
            except ValueError as e:
                raise ValueError(f"{key} must be an integer") from e

        normalized[key] = value

    return normalized


def save_config_values(payload):
    updates = normalize_config_payload(payload)

    if not updates:
        return read_config()

    lines = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
    seen = set()
    updated_lines = []

    for line in lines:
        stripped = line.strip()

        if not stripped or stripped.startswith("#") or "=" not in stripped:
            updated_lines.append(line)
            continue

        key = stripped.split("=", 1)[0].strip()

        if key in updates:
            updated_lines.append(f"{key}={updates[key]}")
            seen.add(key)
        else:
            updated_lines.append(line)

    if updated_lines and updated_lines[-1].strip():
        updated_lines.append("")

    for key in CONFIG_KEYS:
        if key in updates and key not in seen:
            updated_lines.append(f"{key}={updates[key]}")

    ENV_FILE.write_text("\n".join(updated_lines).rstrip() + "\n", encoding="utf-8")

    for key, value in updates.items():
        os.environ[key] = value

    return read_config()

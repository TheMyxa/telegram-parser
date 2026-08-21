# TG

[Русский](README_ru.md) | [中文](README_cn.md)

TG is a Telegram comments exporter and local analytics dashboard. It exports channel posts, discussion comments, reactions, media links, optional media files, and can update the same dataset incrementally.

![Dashboard screenshot](docs/screenshots/dashboard.png)

## Features

- Export Telegram channel posts and comments with Telethon.
- Save data as `JSON`, `CSV`, `Parquet`, or into `PostgreSQL`.
- Incremental export: remembers the last `post_id`, updates the existing dataset, and downloads only missing media.
- Optional media download into `data/content/<dataset_name>/`.
- Optional anonymization of `user_id`, `username`, `first_name`, and `last_name`.
- Web UI on port `9595` with dashboard, post view, comment tree, filters, user profiles, and export launch screen.
- LLM analyzer for exported JSON files.
- Docker Compose setup for one-command local start.

## Screenshots

### Dashboard

![Dashboard](docs/screenshots/dashboard.png)

### Export Screen

![Export screen](docs/screenshots/export.png)

## Demo JSON

A small demo dataset is available at [examples/example.json](examples/example.json).

Open the dashboard and upload this file to test charts, post details, users, reactions, links, and comment tree without connecting to Telegram.

## Project Structure

```text
.
├── main.py                    # Unified CLI: export, analyze, dashboard, config-check
├── export_comments.py         # Telegram exporter
├── comments_dashboard.html    # Web dashboard
├── web_server.py              # Local web server and export API
├── llm_analyzer.py            # LLM analysis for exported JSON
├── config.py                  # .env/config loader
├── docker-compose.yml         # Docker Compose services
├── anonymizer                 # Aliases for anonymized users
├── data/
│   ├── raw/                   # Exported datasets
│   ├── content/               # Downloaded media
│   ├── analysis/              # LLM analysis output
│   └── state/                 # Incremental export state
└── examples/
    └── demo_export.json       # Demo dataset
```

## Requirements

- Docker Desktop, recommended.
- Telegram API credentials: `API_ID` and `API_HASH`.
- A Telegram account session for Telethon.
- Optional: PostgreSQL if you use `postgresql` export.
- Optional: local or remote LLM endpoint if you use `analyze`.

Get Telegram API credentials at `https://my.telegram.org/apps`.

## Configuration

Create `.env` from the example:

```powershell
Copy-Item .env.example .env
```

Edit `.env`:

```env
API_ID=123456
API_HASH=your_api_hash_here
CHANNEL=your_channel
OUTPUT_FILE=data/raw/export.json
POST_LIMIT=500
PAUSE_AFTER_500_POSTS_SECONDS=30
PAUSE_AFTER_1000_POSTS_SECONDS=60

POSTGRES_HOST=host.docker.internal
POSTGRES_PORT=5432
POSTGRES_DB=telegram_parser
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_postgres_password_here
POSTGRES_TABLE=telegram_comments_export

LLM_ENDPOINT=http://localhost:1234/v1/chat/completions
LLM_MODEL=local-model
```

Important fields:

- `API_ID`, `API_HASH`: Telegram API app credentials.
- `CHANNEL`: channel username, for example `durov` or `https://t.me/durov`.
- `POST_LIMIT`: how many latest posts to scan per export run.
- `PAUSE_AFTER_500_POSTS_SECONDS`, `PAUSE_AFTER_1000_POSTS_SECONDS`: safety pauses.
- `OUTPUT_FILE`: base output directory is taken from this path, usually `data/raw/export.json`.
- `LLM_ENDPOINT`, `LLM_MODEL`: used only by `analyze`.

## Docker Usage

Start the web UI:

```powershell
docker compose up --build dashboard
```

Open:

```text
http://localhost:9595
```

Run CLI help:

```powershell
docker compose run --rm cli --help
```

Check config:

```powershell
docker compose run --rm cli config-check
```

## CLI Commands

The project uses one CLI entrypoint:

```text
tg <command> [options]
```

In Docker, use:

```powershell
docker compose run --rm cli <command> [options]
```

### Export JSON

```powershell
docker compose run --rm cli export json
```

Output example:

```text
data/raw/<channel>_20260710_120000.json
```

### Incremental Export

```powershell
docker compose run --rm cli export json --incremental
```

Incremental mode writes and updates:

```text
data/raw/<channel>_dataset.json
data/state/<channel>_state.json
```

It merges posts by `post_id`, merges comments by `comment_id`, refreshes counters and reactions, and keeps already downloaded media files.

### Export With Media

```powershell
docker compose run --rm cli export json --incremental --download-media
```

Media is saved to:

```text
data/content/<channel>_dataset/
```

### Export CSV

```powershell
docker compose run --rm cli export csv
```

### Export Parquet

```powershell
docker compose run --rm cli export parquet
```

### Export To PostgreSQL

```powershell
docker compose run --rm cli export postgresql
```

PostgreSQL settings are read from `.env`.

### Anonymized Export

```powershell
docker compose run --rm cli export json --incremental --anonymize
```

Aliases are loaded from:

```text
anonymizer
```

Use a custom file:

```powershell
docker compose run --rm cli export json --anonymize --anonymizer-file anonymizer
```

### Analyze Exported JSON With LLM

```powershell
docker compose run --rm cli analyze <file_name_from_data_raw>.json
```

Example:

```powershell
docker compose run --rm cli analyze durov_dataset.json --limit 10
```

Analysis files are saved to:

```text
data/analysis/analysis_<source_file>.json
```

### Run Dashboard

```powershell
docker compose up dashboard
```

The dashboard can:

- upload a JSON file;
- show file name, posts, comments, unique users, reactions;
- draw charts by day, top users, top emoji, discussed posts;
- open a post and show comments as a tree;
- filter by `user_id`, `username`, date range, emoji, media, and replies;
- open user details;
- edit `.env` settings from the Export tab;
- start exports from the browser and show progress.

## Local Python Usage

If you do not use Docker, install dependencies:

```powershell
pip install -r requirements.txt
```

Run commands:

```powershell
python main.py --help
python main.py config-check
python main.py export json --incremental
python main.py dashboard
```

## Data Format

The main JSON format is a list of posts:

```json
[
  {
    "post_id": 101,
    "post_date": "2026-07-10 10:00:00+00:00",
    "post_text": "Post text",
    "post_views": 1200,
    "post_forwards": 10,
    "post_link": "https://t.me/channel/101",
    "post_media": null,
    "post_reactions": [{"emoji": "🔥", "count": 12}],
    "comments": [
      {
        "comment_id": 501,
        "comment_date": "2026-07-10 10:05:00+00:00",
        "comment_text": "Comment text",
        "comment_link": "https://t.me/channel/501",
        "comment_media": null,
        "reply_to_msg_id": null,
        "comment_reactions": [],
        "user": {
          "user_id": 1001,
          "username": "alice",
          "first_name": "Alice",
          "last_name": null,
          "bot": false,
          "premium": false
        }
      }
    ]
  }
]
```

See [examples/example.json](examples/example.json) for a complete demo file.

## Notes About Telegram Limits

Telegram does not publish one fixed universal limit for every Telethon workflow. The exporter includes pauses and handles `FloodWaitError` by saving already collected data before waiting.

Recommended practice:

- keep `POST_LIMIT` reasonable;
- use incremental export instead of full re-export;
- keep pauses enabled;
- avoid frequent repeated exports of the same large channel;
- do not run many sessions in parallel from the same account.

## Troubleshooting

### Docker is not running

Start Docker Desktop and run again:

```powershell
docker compose up --build dashboard
```

### Missing API_ID or API_HASH

Check `.env`:

```powershell
docker compose run --rm cli config-check
```

### First Telethon Login

On first run Telethon may ask for phone/login code. The session is stored in:

```text
sessions/
```

The folder is mounted into Docker, so the session can be reused between runs.

### Parquet Export Fails

Make sure Docker image was rebuilt after dependencies changed:

```powershell
docker compose build --no-cache
```

### PostgreSQL Export Fails

Check:

- `POSTGRES_HOST`
- `POSTGRES_PORT`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- network access from Docker to PostgreSQL

## Git Ignore Policy

Runtime data is intentionally ignored:

- `.env`
- `sessions/`
- `data/raw/*`
- `data/content/*`
- `data/analysis/*`
- `data/state/*`

Keep secrets, sessions, exported private data, and downloaded media out of Git.

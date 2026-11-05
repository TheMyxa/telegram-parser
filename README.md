# TG

[Русский](README_ru.md) | [中文](README_cn.md)

TG is a local-first Telegram comments exporter and analytics dashboard. It exports channel posts, discussion comments, reactions, links, optional media files, and can update existing datasets incrementally.

Current version: `3.0.0`.

![Dashboard screenshot](docs/screenshots/dashboard.png)

## Features

- Export Telegram channel posts and comments with Telethon.
- Use one or more channels in `CHANNEL`, separated by commas.
- Save exports as `JSON`, `CSV`, `Parquet`, or `PostgreSQL`.
- True incremental export: scan new posts and revisit older exported posts to refresh comments, reactions, and counters.
- Optional media download into `data/content/<dataset_name>/`.
- Optional anonymization of `user_id`, `username`, `first_name`, and `last_name`.
- Web UI on port `9595` with dashboard, activity heatmap, global search, post view, comment tree, filters, user profiles, export launch screen, Scheduler mode, and Watch mode.
- Open local JSON exports from `data/raw` directly in the dashboard, sorted by date or channel.
- Maintain a local SQLite index in `data/state/tg.sqlite` for faster dashboard summaries, period comparison, and full-text MCP/CLI search.
- LLM analyzer for exported JSON files with Russian, English, and Chinese prompt files.
- Period comparison for comments, users, and reactions with `tg compare`.
- MCP server for local automation through AI clients.
- Docker Compose setup for local use.

## Screenshots

### Dashboard

![Dashboard](docs/screenshots/dashboard.png)

### Export Screen

![Export screen](docs/screenshots/export.png)

## Demo JSON

Use [examples/example.json](examples/example.json) to test the dashboard without connecting to Telegram.

## Project Structure

```text
.
├── main.py                    # Unified CLI: export, index, search, analyze, dashboard, config-check, mcp
├── export_comments.py         # Compatibility entrypoint for exporters.telegram_exporter
├── web/
│   ├── comments_dashboard.html # Web dashboard markup
│   ├── css/                    # Dashboard styles
│   └── js/                     # Dashboard scripts
├── web_server.py              # Compatibility entrypoint for api.web_server
├── api/                       # Local web server and dashboard API
├── telegram/                  # Telegram message serialization helpers
├── exporters/                 # Telegram export orchestration and output formats
├── storage/                   # JSON file loading, atomic writes, and SQLite index
├── analytics/                 # Export summaries and dataset analytics helpers
├── llm/                       # LLM analysis implementation
├── mcp_server.py              # MCP server for local exports and analysis
├── llm_analyzer.py            # Compatibility entrypoint for llm.analyzer
├── config.py                  # .env/config loader
├── docker-compose.yml         # Docker Compose services
├── anonymizer                 # Aliases for anonymized users
├── prompts/                   # LLM prompt files
├── data/
│   ├── raw/                   # Exported datasets
│   ├── content/               # Downloaded media
│   ├── analysis/              # LLM analysis output
│   └── state/                 # Incremental export state
└── examples/
    ├── example.json
    └── demo_export.json
```

## Requirements

- Docker Desktop, recommended.
- Telegram API credentials: `API_ID` and `API_HASH`.
- A Telegram account session for Telethon.
- Optional: PostgreSQL if you use `postgresql` export.
- Optional: local or remote LLM endpoint if you use `analyze`.

Get Telegram API credentials at `https://my.telegram.org/apps`.

## Configuration

Docker creates `.env` from `.env.example` on the first start, so new users can begin with one command:

```powershell
docker compose up --build
```

Then open `http://localhost:9595` and fill in Telegram settings in the Export tab.

If you prefer to edit the file before starting, create `.env` manually:

```powershell
Copy-Item .env.example .env
```

Edit `.env`:

```env
API_ID=123456
API_HASH=your_api_hash_here
CHANNEL=your_channel,another_channel
TELEGRAM_SESSION=sessions/session
OUTPUT_FILE=data/raw/export.json
POST_LIMIT=500
INCREMENTAL_LOOKBACK_POSTS=50
POSTS_PAUSE_SECONDS=30
POSTS_PAUSE_AFTER_POSTS=500

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
- `CHANNEL`: one or more channel usernames or links separated by commas, for example `durov,telegram`.
- `TELEGRAM_SESSION`: Telethon session file path, usually inside `sessions/`.
- `POST_LIMIT`: how many new/latest posts to scan per export run.
- `INCREMENTAL_LOOKBACK_POSTS`: in incremental mode, how many already exported older posts to revisit at or below the saved `last_post_id`.
- `POSTS_PAUSE_SECONDS`: pause duration in seconds.
- `POSTS_PAUSE_AFTER_POSTS`: pause after every N processed posts.
- `OUTPUT_FILE`: base output directory is taken from this path, usually `data/raw/export.json`.
- `LLM_ENDPOINT`, `LLM_MODEL`: used by `analyze`.

Configuration is validated per command: `export` requires Telegram settings, `analyze` requires LLM settings, and PostgreSQL settings are loaded only for `postgresql` export.

## Docker Usage

Start the web UI with one command:

```powershell
docker compose up --build
```

Open:

```text
http://localhost:9595
```

Run CLI commands:

```powershell
docker compose run --rm cli --help
docker compose run --rm cli config-check
```

## CLI Commands

The project uses one CLI entrypoint:

```text
tg <command> [options]
```

In Docker:

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
data/state/tg.sqlite
```

Incremental state is stored in SQLite table `export_states`; the per-channel JSON state file remains a compatibility fallback and migration source.

It scans posts newer than the saved `last_post_id` plus `INCREMENTAL_LOOKBACK_POSTS` already exported posts at or below that `last_post_id`. This refreshes counters, reactions, and comments on older posts that changed after a previous run. It merges posts by `post_id`, merges comments by `comment_id`, and keeps already downloaded media files.

JSON exports are also indexed into local SQLite at `data/state/tg.sqlite`. The database is runtime data and can be rebuilt from JSON exports.

### Watch Mode

```powershell
docker compose run --rm cli watch --poll-interval 30 --refresh-active-posts 20
```

Watch mode is a long-running process that keeps the Telethon session open, watches selected channels for new posts, tracks discussion activity for recent posts, and updates changed posts in `data/raw/<channel>_dataset.json`. The poll interval refreshes recent posts for counters, reactions, nested replies, and missed events.

### Export With Media

```powershell
docker compose run --rm cli export json --incremental --download-media
```

Media is saved to:

```text
data/content/<channel>_dataset/
```

### Other Export Formats

```powershell
docker compose run --rm cli export csv
docker compose run --rm cli export parquet
docker compose run --rm cli export postgresql
```

PostgreSQL settings are read from `.env`.

### Anonymized Export

```powershell
docker compose run --rm cli export json --incremental --anonymize
```

Aliases are loaded from `anonymizer`. Use `--anonymizer-file <path>` to pass a custom file.

### Analyze Exported JSON With LLM

```powershell
docker compose run --rm cli analyze durov_dataset.json --limit 10
```

Use a built-in prompt language:

```powershell
docker compose run --rm cli analyze durov_dataset.json --limit 10 --language en
docker compose run --rm cli analyze durov_dataset.json --limit 10 --language zh
```

Built-in prompt files:

- `prompts/llm_ru.json`
- `prompts/llm_en.json`
- `prompts/llm_zh.json`

Pass a custom prompt file:

```powershell
docker compose run --rm cli analyze durov_dataset.json --prompt-file prompts/llm_en.json
```

### Compare Periods

Compare comments, unique users, and comment reactions for a selected period against the immediately previous period of the same length:

```powershell
docker compose run --rm cli compare --from 2026-07-01 --to 2026-08-01 --file durov_dataset.json
```

`--to` is exclusive. If `--file` is omitted, the newest JSON export from `data/raw` is used.

### Index JSON Exports

Build or refresh the local SQLite index without running a Telegram export:

```powershell
docker compose run --rm cli index
docker compose run --rm cli index --file durov_dataset.json
```

The dashboard and MCP server also index JSON exports lazily when they need them.

### Search Indexed Comments

Search one export:

```powershell
docker compose run --rm cli search "telegram" --file durov_dataset.json
```

Search all JSON exports from `data/raw`:

```powershell
docker compose run --rm cli search "telegram" --limit 50
```

Search uses SQLite FTS5 when available and falls back to regular `LIKE` matching when FTS5 is unavailable or the FTS query is invalid.

Prompt files are JSON objects with `system` and `user_template` fields. `user_template` must include `{data}`.

Per-post LLM results are cached in SQLite table `analysis_cache` by `source_file`, `post_id`, `post_hash`, `prompt_hash`, and `model`. Re-running analysis skips unchanged posts with a successful cached result and continues writing the JSON output incrementally.

Analysis files are saved to:

```text
data/analysis/analysis_<source_file>.json
```

### MCP Server

Run a Model Context Protocol server over stdio:

```powershell
docker compose run --rm -i cli mcp
```

Local Python:

```powershell
python main.py mcp
```

The MCP server exposes tools for local automation:

- `get_config_safe`: read non-secret config values with secrets masked.
- `list_exports`, `get_export_summary`, `get_post`, `search_comments`, `search_all_comments`: inspect JSON exports in `data/raw`. Search uses SQLite FTS5 when available, with `LIKE` fallback.
- `list_analysis_files`, `list_analysis_results`, `read_analysis`, `run_analysis`: work with LLM analysis files. Analysis metadata is indexed in SQLite for fast listing and error inspection.
- `start_export`, `get_export_process_status`: start and monitor a Telegram export. `start_export` requires `confirm=true`.

### Run Dashboard

```powershell
docker compose up
```

The dashboard can:

- upload a JSON file;
- open a local JSON export from `data/raw`;
- show file name, posts, comments, unique users, reactions;
- draw charts by day, top users, top emoji, discussed posts;
- draw an activity heatmap by weekday and hour;
- open a post and show comments as a tree;
- filter by user, date range, emoji, media, and replies;
- open user details;
- edit `.env` settings from the Export tab;
- start exports from the browser and show progress.
- enable Scheduler mode to update selected channels automatically every N minutes.
- enable Watch mode to keep watching channels and update changed JSON dataset posts continuously.
- show the app version from `version.py` through `/api/version`.

Dashboard API endpoints:

- `GET /api/version`: return the current app version.
- `GET /api/exports?sort=date|channel`: list JSON exports from `data/raw` with SQLite-indexed counts when available.
- `GET /api/search?q=text&channel=name&from=YYYY-MM-DD&to=YYYY-MM-DD&user=username&limit=50`: search indexed comments across all local JSON exports.
- `GET /api/export/<file>/summary`: return counts and metadata for one JSON export.
- `GET /api/export/<file>/filtered-summary?q=text&user=username&from=YYYY-MM-DD&to=YYYY-MM-DD&emoji=👍&media=1&replies=1`: return SQLite-backed counts for filtered dashboard views.
- `GET /api/export/<file>/charts`: return SQLite-backed dashboard chart aggregates for one JSON export.
- `GET /api/export/<file>/posts?limit=100&offset=0&q=text&user=username&from=YYYY-MM-DD&to=YYYY-MM-DD&emoji=👍&media=1&replies=1`: return SQLite-backed post rows for the dashboard table.
- `GET /api/export/<file>/post/<post_id>`: return one reconstructed post with comments from SQLite.
- `GET /api/export/<file>/compare?from=YYYY-MM-DD&to=YYYY-MM-DD`: compare comments, users, and reactions between periods.
- `GET /api/scheduler/status`: return current scheduler state.
- `GET /api/scheduler/history?limit=50&offset=0&status=FAILED&channel=durov`: list persisted scheduled run records from SQLite with pagination, filters, and stats.
- `GET /api/scheduler/history/<run_id>`: return one scheduled run detail card.
- `POST /api/scheduler/history/<run_id>/retry`: retry a saved scheduled run with the same channels, format, and export flags.
- `POST /api/scheduler/start`: start scheduled exports with `channel`, `interval_minutes`, format, and export flags.
- `POST /api/scheduler/stop`: stop scheduled exports.
- `GET /api/watch/status`: return current Watch mode state.
- `POST /api/watch/start`: start Watch mode with `channel`, `poll_interval`, `refresh_active_posts`, and export flags.
- `POST /api/watch/stop`: stop Watch mode.

Scheduler mode starts the first export immediately, then repeats every configured interval. If an export is still running when the next interval arrives, that run is skipped.

Scheduler history is stored in the local SQLite index at `data/state/tg.sqlite`. Older JSON records from `data/scheduler/` are imported lazily when history is read. Each scheduled run has status `QUEUED`, `RUNNING`, `SUCCESS`, `PARTIAL`, `FAILED`, `SKIPPED`, or `CANCELLED`, plus channel results, structured error information, and recent log lines.

Watch mode is separate from Scheduler mode. It stays running and updates changed posts as channel or discussion activity arrives, with a periodic refresh for counters and missed comment updates.

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
python main.py watch --poll-interval 30 --refresh-active-posts 20
python main.py index --file durov_dataset.json
python main.py search "telegram" --file durov_dataset.json
python main.py compare --from 2026-07-01 --to 2026-08-01 --file durov_dataset.json
python main.py dashboard
python main.py mcp
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
    "post_reactions": [{"emoji": "fire", "count": 12}],
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

When an exporter step fails but partial data can still be saved, posts may include optional `post_media_error` or `export_errors` fields, and comments may include `comment_media_error`.

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

### Docker Is Not Running

Start Docker Desktop and run again:

```powershell
docker compose up --build
```

### Missing API_ID Or API_HASH

Check `.env`:

```powershell
docker compose run --rm cli config-check
```

### First Telethon Login

On first run Telethon may ask for phone/login code. The session file is configured with `TELEGRAM_SESSION` and is usually stored in:

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

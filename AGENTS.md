# AGENTS.md

This file is guidance for coding agents working in this repository.

## Project Summary

TG is a local-first Telegram comments exporter and analytics dashboard.

Core capabilities:

- Export Telegram channel posts, comments, reactions, links, and optional media.
- Save exports as JSON, CSV, Parquet, or PostgreSQL rows.
- Support incremental exports with saved state.
- Run a local Web UI on port `9595`.
- Analyze exported JSON files through an LLM endpoint.

## Important Files

- `main.py` - unified CLI entrypoint.
- `export_comments.py` - Telethon export logic.
- `comments_dashboard.html` - single-file Web UI.
- `web_server.py` - HTTP server, dashboard API, export runner, `.env` editor.
- `llm_analyzer.py` - LLM analysis for exported JSON files.
- `config.py` - `.env` loader and runtime configuration.
- `version.py` - application version.
- `.env.example` - safe example config.
- `docker-compose.yml` - Docker services for dashboard and CLI.
- `examples/example.json` - English demo dataset.
- `examples/demo_export.json` - demo dataset.

## Runtime Data

Runtime files may contain secrets, Telegram sessions, private comments, media, or analysis output. Do not commit them.

Ignored runtime paths:

- `.env`
- `sessions/*`
- `data/raw/*`
- `data/content/*`
- `data/analysis/*`
- `data/state/*`

Keep `.gitkeep` files in these folders so the directory structure exists after clone.

## Configuration

Configuration is loaded from `.env` by `config.py`.

Required values:

- `API_ID`
- `API_HASH`
- `CHANNEL`
- `LLM_ENDPOINT`
- `LLM_MODEL`

The Web UI can read and write `.env` through `/api/config`. In Docker, `.env` is bind-mounted to `/app/.env`.

Never print or expose secret values unnecessarily. `API_HASH`, PostgreSQL passwords, session files, exported datasets, and media should be treated as sensitive.

## Commands

Use Docker when possible:

```powershell
docker compose up --build dashboard
docker compose run --rm cli --help
docker compose run --rm cli config-check
docker compose run --rm cli export json --incremental
docker compose run --rm cli export json --incremental --download-media
docker compose run --rm cli analyze example.json --limit 5
```

Local Python commands:

```powershell
python main.py --help
python main.py config-check
python main.py export json --incremental
python main.py dashboard
```

On some Windows machines, the `python.exe` Store alias may be broken. If local Python fails, prefer Docker checks.

## Validation

Before finishing code changes, run the most relevant checks that do not require Telegram network access:

```powershell
docker compose config
```

If Python is available:

```powershell
python -m py_compile main.py export_comments.py web_server.py llm_analyzer.py config.py version.py
```

For JSON examples:

```powershell
Get-Content -Raw -Path examples\example.json | ConvertFrom-Json
```

Only run live Telegram exports when the user explicitly expects it and credentials/session are available.

## Coding Guidelines

- Keep changes scoped to the requested behavior.
- Preserve compatibility with old JSON exports that are a plain list of posts.
- Do not remove existing runtime files unless the user explicitly asks.
- Prefer small helper functions over duplicating parsing or merge logic.
- Keep the dashboard dependency-free unless there is a strong reason to add a build step.
- Keep user-facing text clear and practical.
- Use `version.py` as the single source of truth for the app version.

## Export Data Shape

The dashboard currently expects a JSON array of posts:

```json
[
  {
    "post_id": 1001,
    "post_date": "2026-07-10 10:00:00+00:00",
    "post_text": "Post text",
    "post_views": 1200,
    "post_forwards": 10,
    "post_link": "https://t.me/channel/1001",
    "post_media": null,
    "post_reactions": [],
    "comments": []
  }
]
```

Comment objects may include:

- `comment_id`
- `comment_date`
- `comment_text`
- `comment_link`
- `comment_media`
- `reply_to_msg_id`
- `comment_reactions`
- `user`

When changing the schema, add backward-compatible loaders before changing exporter output.

## Incremental Export Notes

Incremental mode uses:

- `data/raw/<channel>_dataset.json`
- `data/state/<channel>_state.json`
- `data/content/<channel>_dataset/`

Expected behavior:

- Merge posts by `post_id`.
- Merge comments by `comment_id`.
- Refresh post/comment counters and reactions.
- Reuse already downloaded media when the referenced file still exists.
- Save partial data before long `FloodWaitError` waits.

## Web UI Notes

The dashboard is a single HTML file. API endpoints live in `web_server.py`.

Current endpoints:

- `GET /api/version`
- `GET /api/config`
- `POST /api/config`
- `POST /api/export/start`
- `GET /api/export/status`
- `GET /data/...`

When adding UI controls, wire them through:

1. HTML markup.
2. `el` element map.
3. Event listeners.
4. API payload/response handling.

## Docker Notes

The dashboard service runs:

```text
python main.py dashboard
```

The CLI service is intended for one-off commands:

```powershell
docker compose run --rm cli export json --incremental
```

Do not bake `.env`, sessions, exported datasets, or media into the Docker image.

## Documentation

Update `README.md` when changing:

- CLI commands.
- Docker commands.
- `.env` keys.
- export formats.
- dashboard features.
- data format.
- versioned behavior that affects users.

Keep examples safe and synthetic. Do not use real exported comments in `examples/`.

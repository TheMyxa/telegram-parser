# AGENTS.md

This file is guidance for coding agents working in this repository.

## Project Summary

TG is a local-first Telegram comments exporter, analytics dashboard, LLM analyzer, and MCP server.

Core capabilities:

- Export Telegram channel posts, comments, reactions, links, and optional media.
- Support one or more channels in `CHANNEL`, separated by commas.
- Save exports as JSON, CSV, Parquet, or PostgreSQL rows.
- Support incremental exports with saved state and a configurable old-post lookback window.
- Run a local Web UI on port `9595`.
- Analyze exported JSON files through an LLM endpoint using prompt files.
- Expose local export/analysis tools through an MCP server over stdio.

## Important Files

- `main.py` - unified CLI entrypoint: `export`, `analyze`, `dashboard`, `config-check`, `mcp`.
- `export_comments.py` - Telethon export logic, multi-channel export, incremental merge, retry/error handling.
- `comments_dashboard.html` - single-file Web UI.
- `web_server.py` - HTTP server, dashboard API, export runner, `.env` editor.
- `llm_analyzer.py` - LLM analysis for exported JSON files.
- `mcp_server.py` - MCP server tools for config, exports, search, analysis, and controlled export starts.
- `config.py` - `.env` loader and runtime configuration.
- `version.py` - application version.
- `prompts/llm_ru.json` - Russian LLM prompt file.
- `prompts/llm_en.json` - English LLM prompt file.
- `prompts/llm_zh.json` - Chinese LLM prompt file.
- `.env.example` - safe example config.
- `docker-compose.yml` - Docker services for dashboard and CLI.
- `examples/example.json` - English demo dataset.
- `README.md`, `README_ru.md`, `README_cn.md` - user documentation.

## Runtime Data

Runtime files may contain secrets, Telegram sessions, private comments, media, logs, state, or analysis output. Do not commit them.

Ignored runtime paths:

- `.env`
- `sessions/*`
- `data/raw/*`
- `data/content/*`
- `data/analysis/*`
- `data/state/*`

Keep `.gitkeep` files in runtime folders so the directory structure exists after clone.

## Configuration

Configuration is loaded from `.env` by `config.py`.

Required values:

- `API_ID`
- `API_HASH`
- `CHANNEL`
- `LLM_ENDPOINT`
- `LLM_MODEL`

Important optional/defaulted values:

- `TELEGRAM_SESSION` - Telethon session file path, usually `sessions/session`.
- `OUTPUT_FILE` - base path used to derive export output directory.
- `POST_LIMIT` - number of new/latest posts to scan.
- `INCREMENTAL_LOOKBACK_POSTS` - number of already exported older posts to revisit in incremental mode.
- `POSTS_PAUSE_SECONDS` - pause duration in seconds.
- `POSTS_PAUSE_AFTER_POSTS` - pause after every N processed posts.
- `POSTGRES_*` - PostgreSQL export settings.

The Web UI can read and write `.env` through `/api/config`. In Docker, `.env` is bind-mounted to `/app/.env`.

Never print or expose secret values unnecessarily. `API_HASH`, PostgreSQL credentials, session files, exported datasets, downloaded media, and analysis outputs should be treated as sensitive.

## Commands

Use Docker when possible:

```powershell
docker compose up --build dashboard
docker compose run --rm cli --help
docker compose run --rm cli config-check
docker compose run --rm cli export json --incremental
docker compose run --rm cli export json --incremental --download-media
docker compose run --rm cli analyze example.json --limit 5
docker compose run --rm cli analyze example.json --limit 5 --language en
docker compose run --rm -i cli mcp
```

Local Python commands:

```powershell
python main.py --help
python main.py config-check
python main.py export json --incremental
python main.py analyze example.json --limit 5
python main.py dashboard
python main.py mcp
```

On some Windows machines, the `python.exe` Store alias may be broken. If local Python fails, prefer Docker checks.

## Validation

Before finishing code changes, run the most relevant checks that do not require Telegram network access:

```powershell
docker compose config
```

If dependencies or Docker image contents changed:

```powershell
docker compose build dashboard
```

If Python is available:

```powershell
python -m py_compile main.py export_comments.py web_server.py llm_analyzer.py mcp_server.py config.py version.py
```

If local Python is broken, use Docker:

```powershell
docker compose run --rm --entrypoint python cli -m py_compile main.py export_comments.py web_server.py llm_analyzer.py mcp_server.py config.py version.py
```

For JSON examples and prompts:

```powershell
Get-Content -Raw -Path examples\example.json | ConvertFrom-Json
Get-Content -Raw -Path prompts\llm_ru.json | ConvertFrom-Json
Get-Content -Raw -Path prompts\llm_en.json | ConvertFrom-Json
Get-Content -Raw -Path prompts\llm_zh.json | ConvertFrom-Json
```

Only run live Telegram exports when the user explicitly expects it and credentials/session are available.

## Coding Guidelines

- Keep changes scoped to the requested behavior.
- Preserve compatibility with old JSON exports that are a plain list of posts.
- Do not remove existing runtime files unless the user explicitly asks.
- Prefer small helper functions over duplicating parsing, merge, retry, or path-safety logic.
- Keep the dashboard dependency-free unless there is a strong reason to add a build step.
- Keep user-facing text clear and practical.
- Use `version.py` as the single source of truth for the app version.
- Use atomic writes for JSON dataset/state/analysis files when practical.
- Do not log full secrets, raw session paths with sensitive names, or private comment contents unless necessary for the requested task.

## Export Data Shape

The dashboard expects a JSON array of posts:

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
- `comment_media_error`

Post objects may include:

- `post_media_error`
- `export_errors`

When changing the schema, add backward-compatible loaders before changing exporter output.

## Incremental Export Notes

Incremental mode uses one dataset/state/content folder per channel:

- `data/raw/<channel>_dataset.json`
- `data/state/<channel>_state.json`
- `data/content/<channel>_dataset/`

Expected behavior:

- Process posts newer than saved `last_post_id`.
- Also revisit `INCREMENTAL_LOOKBACK_POSTS` already exported posts at or below `last_post_id`.
- Merge posts by `post_id`.
- Merge comments by `comment_id`.
- Refresh post/comment counters and reactions.
- Reuse already downloaded media when the referenced file still exists.
- Save partial data before long `FloodWaitError` waits and after recoverable failures where possible.
- Keep channel failures isolated so one failed channel does not stop all subsequent channels.

Do not simplify incremental mode to only `min_id = last_post_id`; old posts can receive new comments, reactions, and counter updates.

## LLM Analyzer Notes

Prompt text lives in `prompts/*.json`, not inline in `llm_analyzer.py`.

Prompt file shape:

```json
{
  "language": "en",
  "system": "System prompt",
  "user_template": "Prompt with {data}"
}
```

Rules:

- `user_template` must include `{data}`.
- Built-in language shortcuts are `ru`, `en`, `zh`.
- `--prompt-file` overrides `--language`.
- Analyzer should continue when one post fails and write partial analysis output incrementally.

## MCP Server Notes

`mcp_server.py` uses `mcp.server.fastmcp.FastMCP` and runs over stdio:

```powershell
python main.py mcp
docker compose run --rm -i cli mcp
```

MCP tools should default to safe local operations:

- Read exports and analysis files only from `data/raw` and `data/analysis`.
- Mask secrets in config tools.
- Use path validation to prevent traversal outside expected runtime directories.
- Require `confirm=true` before starting live Telegram exports.
- Avoid exposing `.env`, session files, raw private datasets, or media outside explicit read/search tools.

Current MCP tools include:

- `get_config_safe`
- `list_exports`
- `get_export_summary`
- `search_comments`
- `get_post`
- `list_analysis_files`
- `read_analysis`
- `run_analysis`
- `start_export`
- `get_export_process_status`

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
3. Translations if user-facing text is shown.
4. Event listeners.
5. API payload/response handling.

## Docker Notes

The dashboard service runs:

```text
python main.py dashboard
```

The CLI service is intended for one-off commands:

```powershell
docker compose run --rm cli export json --incremental
```

MCP over stdio needs interactive stdin:

```powershell
docker compose run --rm -i cli mcp
```

Do not bake `.env`, sessions, exported datasets, analysis outputs, logs, or media into the Docker image.

## Documentation

Update `README.md`, `README_ru.md`, and `README_cn.md` when changing:

- CLI commands.
- Docker commands.
- `.env` keys.
- export formats.
- dashboard features.
- MCP tools.
- LLM prompt behavior.
- data format.
- versioned behavior that affects users.

Keep examples safe and synthetic. Do not use real exported comments in `examples/`.

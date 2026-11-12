# Dashboard HTTP API

[English README](../README.md) · [Русский](../README_ru.md) · [中文](../README_cn.md)

The dashboard listens on port `9595`. Endpoints below are implemented in
`api/web_server.py`; application logic is in `services/`. Responses are JSON
unless a static file is requested. The server has no authentication: `/api/config`
contains sensitive values and mutation endpoints can start real Telegram work.
Use trusted local access; a deployment beyond that needs its own access control.

## Configuration and exports

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/version` | Version from `version.py` |
| GET / POST | `/api/config` | Read / update supported `.env` fields |
| GET | `/api/exports` | List local JSON exports; `sort=date` or `sort=channel` |
| GET | `/api/search` | Search indexed comments across exports |
| GET | `/api/export/<file>/summary` | Counts, channel, file metadata |
| GET | `/api/export/<file>/filtered-summary` | Counts for the selected filters |
| GET | `/api/export/<file>/charts` | Chart and heatmap aggregates |
| GET | `/api/export/<file>/posts` | Paginated post rows |
| GET | `/api/export/<file>/post/<post_id>` | Full post and comments |
| GET | `/api/export/<file>/compare` | Current/previous period metrics |
| POST | `/api/export/start` | Start a one-off export |
| GET | `/api/export/status` | In-memory export status and recent output |

`<file>` is a basename under `data/raw`, restricted to JSON. Search lazily indexes
local JSON exports. `q` is required for `/api/search`; optional parameters are
`channel`, `from`, `to`, `user`, `limit` (default 50, clamped to 1–200). Search uses
FTS5, with LIKE fallback if FTS5 is unavailable or the query is invalid.

`posts` and `filtered-summary` accept `q`, `user`, `from`, `to`, `emoji`, `media=1`
and `replies=1`. `posts` also accepts `limit` (default 100) and `offset` (default 0).
`compare` requires `from` and `to` dates, with `to` exclusive, and compares the
selected period with the immediately preceding period of the same length.

`summary` and `compare` use SQLite with JSON fallback for an unavailable index.
Charts, paginated posts and filtered counts require SQLite. Programming errors
do not silently trigger JSON fallback. See [errors](errors.md) for status codes.

Example export payload (starts Telegram work on the normal server):

```json
{
  "channel": "demo_channel",
  "format": "json",
  "incremental": true,
  "download_media": false,
  "anonymize": false
}
```

Formats: `json`, `csv`, `parquet`, `postgresql`. An optional `config` object updates
configuration. `channel` may contain comma-separated channels.

## Scheduler and Watch

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/scheduler/start` | Export payload plus `interval_minutes >= 1` |
| POST | `/api/scheduler/stop` | Disable future scheduled runs |
| GET | `/api/scheduler/status` | In-memory scheduler state |
| GET | `/api/scheduler/history` | Persisted history, pagination and aggregate stats |
| GET | `/api/scheduler/history/<run_id>` | Full run details |
| POST | `/api/scheduler/history/<run_id>/retry` | New run using the original channel/format/flags |
| POST | `/api/watch/start` | Start continuous JSON dataset updates |
| POST | `/api/watch/stop` | Request Watch process termination |
| GET | `/api/watch/status` | Watch status, recent output and updates |

History accepts `limit` (default 50, clamped to 1–200), `offset`, `status`, `channel`.
The response contains `runs`, `pagination` and `stats`. Status values are `QUEUED`,
`RUNNING`, `SUCCESS`, `PARTIAL`, `FAILED`, `SKIPPED`, `CANCELLED`.

Scheduler starts immediately, skips a due run if an export is active, and stops
on dashboard restart. History survives in `data/state/tg.sqlite`; old JSON history
is imported from `data/scheduler`. Stopping the scheduler does not terminate a
currently running export.

Watch accepts `channel`, `download_media`, `anonymize`, optional `config`,
`poll_interval` (default 30 seconds, minimum 5), and `refresh_active_posts`
(default 20, minimum 1). It maintains incremental JSON, independently of Scheduler.

## Static files and JSON shape

- `/`, `/index.html`, `/comments_dashboard.html`: dashboard HTML.
- `/web/...`: frontend assets confined to `web/`.
- `/data/...`: files confined to `data/raw`, `data/content`, `data/analysis`.
- `data/private`, `data/state`, `data/scheduler`, `.env` and sessions are not
  available through the static data route.

JSON exports remain plain arrays, for example:

```json
[
  {
    "post_id": 1001,
    "post_date": "2026-07-10 10:00:00+00:00",
    "post_text": "Synthetic demonstration post",
    "post_views": 1200,
    "post_forwards": 10,
    "post_link": "https://t.me/demo_channel/1001",
    "post_media": null,
    "post_reactions": [],
    "comments": []
  }
]
```

Comments may include `comment_id`, `comment_date`, `comment_text`, `comment_link`,
`comment_media`, `reply_to_msg_id`, `comment_reactions`, `user`,
`comment_media_error`. Posts may also include `post_media_error` and
`export_errors`. See the [complete synthetic dataset](../examples/example.json).

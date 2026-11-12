# Application services

[English README](../README.md) · [Русский](../README_ru.md) · [中文](../README_cn.md)

`api/web_server.py` contains HTTP routing, request/response handling and static
file serving. Application logic lives in `services/`:

| Module | Responsibility |
| --- | --- |
| `paths.py` | Stable application root and runtime/web directories |
| `configuration.py` | Dashboard `.env` bootstrap, parsing, validation and updates |
| `exports.py` | Shared export path validation, list-shaped JSON loading and SQLite indexing for CLI, HTTP and MCP |
| `dashboard_exports.py` | Dashboard query parameters, export queries and response shapes, including existing JSON fallbacks |
| `processes.py` | Export/Watch subprocess launch, output parsing and in-memory process status |
| `scheduler_history.py` | SQLite run history, legacy JSON migration and outcome classification |
| `scheduler.py` | Immediate and periodic export scheduling, skip handling, retry and scheduler status |
| `tool_errors.py` | MCP boundary for expected application failures and unexpected exceptions |

`errors.py` defines shared failure categories. `api/error_handling.py` translates
those categories into HTTP status codes and logs unexpected failures.
`telegram/anonymization.py` owns pseudonym rules, private map persistence,
identity-mode validation and local conversion/restoration.

Dependencies flow from HTTP handlers to services. The scheduler calls process
services; process services report outcomes to scheduler history. History does not
import the scheduler or process services, avoiding circular imports.

The CLI and MCP import `services.exports` without importing HTTP, scheduler or
process state. HTTP retains its basename-only JSON policy; MCP confines files to
approved runtime directories; CLI indexing still accepts explicit file paths.
SQLite operational failures are translated to `IndexUnavailableError` while
programming errors propagate. Summary and comparison retain JSON fallback for
an unavailable index. The shared layer starts no background work on import.

Process and scheduler state remain in memory. Scheduler history, incremental
state and analysis metadata/cache are stored in SQLite. Compatibility entrypoints
`web_server.py`, `export_comments.py` and `llm_analyzer.py` remain available.

## Watch and storage

Watch event callbacks enqueue work. Per-channel workers collect events for one
second and process at most 20 distinct posts at a time. Unknown discussion roots
are coalesced into a recent-post scan. A batch reads JSON once and writes it once
when changed; `sync_export_posts()` replaces only changed post/comment/reaction/FTS
records. The existing complete dataset is available for full indexing fallback
when the index does not match the JSON from before the write. Explicit CLI
indexing and normal complete-export indexing still use `sync_export_file()`.

The canonical JSON stays a plain list of posts. State JSON remains a compatibility
fallback, and legacy scheduler-history JSON remains a migration source. The
private pseudonym map is separate, durable runtime data and cannot be rebuilt
from an anonymized export. See [pseudonyms](anonymization.md), [API](api.md) and
[errors](errors.md).

## Known limitations

- `llm/analyzer.py:build_post_prompt_payload()` currently constructs its payload
  without returning it. Prompts receive `null` and the content hash cannot track
  post/comment changes correctly. Cache schema exists, but content-sensitive LLM
  analysis must not be treated as verified until this is fixed.
- Exporter configuration and service process/scheduler state are mutable module
  globals. Dataset writes are not coordinated across independent Export/Watch
  processes; avoid simultaneous writers to the same archive/session.
- JSON writes use a fixed temporary filename; the JSON archive is still rewritten
  in full per changed batch. SQLite partial updates reduce indexing work, not
  the serialization cost of an individual JSON write.
- SQLite connections initialize the schema on opening; their transaction context
  does not itself guarantee connection closure.
- Private pseudonym-map locking waits synchronously and stale locks require
  manual recovery after checking active writers. Maps are not encrypted.
- Dashboard binds to all interfaces and has no built-in authentication. Static
  private paths are blocked, but configuration and mutation API endpoints remain
  intended for trusted local access.

These are implementation limits, not promises of planned behavior. Documentation
updates do not change runtime code.

## Validation

Run regression checks without Telegram access:

```powershell
docker compose run --rm --workdir /workspace --entrypoint python cli -m unittest discover -s tests -v
docker compose run --rm --workdir /workspace --entrypoint python cli -m compileall -q errors.py main.py mcp_server.py api services exporters storage telegram analytics llm tests
docker compose run --rm --workdir /workspace --entrypoint python cli docs/check_docs.py
```

Tests use synthetic datasets, temporary configuration files and temporary SQLite
databases. Telegram subprocesses are mocked.

For UI captures, use the isolated [screenshot workflow](screenshots.md), not a
dashboard instance with real runtime data.

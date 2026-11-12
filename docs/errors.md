# Error categories

[English README](../README.md) · [Русский](../README_ru.md) · [中文](../README_cn.md)

Expected application failures are defined in `errors.py`. They retain their
original cause with `raise ... from error` where a lower-level failure is
translated. Validation errors remain compatible with `ValueError`, and process
errors with `RuntimeError`, for existing Python callers.

| Category | Code | HTTP status |
| --- | --- | --- |
| `ValidationError` | `invalid_input` | 400 |
| `DatasetCorruptedError` | `dataset_corrupted` | 422 |
| `IdentityModeMismatchError` | `identity_mode_mismatch` | 409 |
| `AnonymizationRulesError` | `invalid_anonymization_rules` | 400 |
| `AnonymizationMapCorruptedError` | `anonymization_map_corrupted` | 422 |
| `AnonymizationMapLockedError` | `anonymization_map_locked` | 409 |
| `ProcessAlreadyRunningError` | `process_already_running` | 409 |
| `ProcessStartError` | `process_start_failed` | 500 |
| `IndexUnavailableError` | `index_unavailable` | 503 |

HTTP domain-error responses retain `ok` and `error` and add `error_code`:

```json
{"ok": false, "error": "Export is already running", "error_code": "process_already_running"}
```

Existing ordinary input/path validation responses remain supported. Unexpected
HTTP failures produce a generic 500 response with `error_code: "internal_error"`
and a server-side traceback. Internal details are not included in that response.

CLI expected failures produce a concise stderr message and exit code 2.
Unexpected failures log a traceback and return 1. Interrupts return 130.
Argparse and `config-check` retain their own exit behavior. MCP tools report
domain error codes in the tool error text; unexpected failures are logged and
reported as `Internal tool error`.

SQLite operations translate SQLite/OS failures to `IndexUnavailableError`.
`sqlite3.ProgrammingError` and Python programming exceptions propagate. Dashboard
summary/comparison and CLI comparison keep their JSON fallback for unavailable
indexes; unexpected failures do not silently trigger that fallback.

Invalid export JSON raises `DatasetCorruptedError`. The exporter loader
preserves its backup behavior, but no longer substitutes an empty archive.
Missing datasets still return an empty list. Read-only HTTP/MCP loaders do not
modify corrupt files. Restore or repair a corrupt archive before exporting or
indexing it again.

Scheduler history recognizes application-error objects by category and records
their code. Existing string-based classification remains for legacy records and
subprocess log messages.

The full endpoint list is in [HTTP API](api.md). These categories do not imply
that every legacy validation error has been migrated to a custom exception;
ordinary `ValueError`, file errors and command-specific exit behavior remain
where documented.

import logging
from errors import ApplicationError, IndexUnavailableError
import argparse
import asyncio
import json
import sys
from pathlib import Path


EXPORT_FORMATS = ("json", "csv", "postgresql", "parquet")


def build_parser():
    parser = argparse.ArgumentParser(
        prog="tg",
        description="TG comments exporter, analyzer and dashboard.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for operation in ("anonymize", "deanonymize"):
        identity_parser = subparsers.add_parser(operation, help=f"{operation.capitalize()} a local JSON export into a new file.")
        identity_parser.add_argument("--file", required=True)
        identity_parser.add_argument("--channel", required=True, help="Original channel name used by Export/Watch.")
        identity_parser.add_argument("--output", default=None, help="New file; existing files are never overwritten.")
        if operation == "anonymize":
            identity_parser.add_argument("--rules", default="anonymization_rules.json")
        else:
            identity_parser.add_argument("--map", default="data/private/anonymization_map.json")
        identity_parser.set_defaults(handler=run_identity_transform)

    export_parser = subparsers.add_parser(
        "export",
        help="Export Telegram posts and comments.",
        description="Export Telegram posts and comments.",
    )
    export_parser.add_argument(
        "export_format",
        nargs="?",
        choices=EXPORT_FORMATS,
        help="Export format: json, csv, postgresql, parquet.",
    )
    export_parser.add_argument(
        "--format",
        dest="format_flag",
        choices=EXPORT_FORMATS,
        help="Export format: json, csv, postgresql, parquet.",
    )
    export_parser.add_argument(
        "--download-media",
        action="store_true",
        help="Download post and comment media to data/content/<export_run_id>/.",
    )
    export_parser.add_argument(
        "--anonymize",
        action="store_true",
        help="Replace user_id, username, first_name and last_name with aliases.",
    )
    export_parser.add_argument(
        "--anonymizer-file",
        default="anonymization_rules.json",
        help="JSON naming rules or legacy text aliases. Default: anonymization_rules.json.",
    )
    export_parser.add_argument(
        "--incremental",
        action="store_true",
        help="Update an existing channel dataset and download only missing media.",
    )
    export_parser.set_defaults(handler=run_export)

    analyze_parser = subparsers.add_parser(
        "analyze",
        help="Analyze exported JSON with an LLM endpoint.",
        description="Analyze exported JSON with an LLM endpoint.",
    )
    analyze_parser.add_argument("file", help="JSON file name from data/raw or direct path.")
    analyze_parser.add_argument("--limit", type=int, default=None, help="Analyze only first N posts.")
    analyze_parser.add_argument(
        "--language",
        choices=("ru", "en", "zh"),
        default=None,
        help="Prompt language shortcut: ru, en, or zh. Default: ru.",
    )
    analyze_parser.add_argument(
        "--prompt-file",
        default=None,
        help="Path to a prompt JSON file. Overrides --language.",
    )
    analyze_parser.set_defaults(handler=run_analyze)

    compare_parser = subparsers.add_parser(
        "compare",
        help="Compare comments, users, and reactions between two periods.",
        description="Compare comments, users, and reactions between a selected period and the previous period of the same length.",
    )
    compare_parser.add_argument(
        "--from",
        dest="from_date",
        required=True,
        help="Current period start date, for example 2026-07-01.",
    )
    compare_parser.add_argument(
        "--to",
        dest="to_date",
        required=True,
        help="Current period end date, for example 2026-08-01. The end date is exclusive.",
    )
    compare_parser.add_argument(
        "--file",
        default=None,
        help="JSON file name from data/raw or direct path. Defaults to the newest JSON export in data/raw.",
    )
    compare_parser.set_defaults(handler=run_compare)

    index_parser = subparsers.add_parser(
        "index",
        help="Index JSON exports into the local SQLite database.",
        description="Index one or all JSON exports from data/raw into the local SQLite database.",
    )
    index_parser.add_argument(
        "--file",
        default=None,
        help="JSON file name from data/raw or direct path. If omitted, all data/raw JSON exports are indexed.",
    )
    index_parser.set_defaults(handler=run_index)

    search_parser = subparsers.add_parser(
        "search",
        help="Search indexed comments with SQLite FTS.",
        description="Search comments in one or all indexed JSON exports with SQLite FTS and LIKE fallback.",
    )
    search_parser.add_argument("query", help="Search query. FTS syntax is supported when available.")
    search_parser.add_argument(
        "--file",
        default=None,
        help="JSON file name from data/raw or direct path. If omitted, all data/raw JSON exports are searched.",
    )
    search_parser.add_argument(
        "--channel",
        default=None,
        help="Limit global search to one indexed channel key. Ignored when --file is used.",
    )
    search_parser.add_argument("--limit", type=int, default=20, help="Maximum results to return. Default: 20.")
    search_parser.set_defaults(handler=run_search)

    dashboard_parser = subparsers.add_parser(
        "dashboard",
        help="Run web dashboard on port 9595.",
        description="Run web dashboard on port 9595.",
    )
    dashboard_parser.set_defaults(handler=run_dashboard)

    watch_parser = subparsers.add_parser(
        "watch",
        help="Watch Telegram channels and update JSON datasets continuously.",
        description="Watch Telegram channels and update JSON datasets continuously.",
    )
    watch_parser.add_argument(
        "--download-media",
        action="store_true",
        help="Download post and comment media to data/content/<channel>_dataset/.",
    )
    watch_parser.add_argument(
        "--anonymize",
        action="store_true",
        help="Replace user_id, username, first_name and last_name with aliases.",
    )
    watch_parser.add_argument(
        "--anonymizer-file",
        default="anonymization_rules.json",
        help="JSON naming rules or legacy text aliases. Default: anonymization_rules.json.",
    )
    watch_parser.add_argument(
        "--poll-interval",
        type=int,
        default=30,
        help="Seconds between refresh passes for recent posts. Default: 30.",
    )
    watch_parser.add_argument(
        "--refresh-active-posts",
        type=int,
        default=20,
        help="How many latest posts per channel to refresh. Default: 20.",
    )
    watch_parser.set_defaults(handler=run_watch)

    config_parser = subparsers.add_parser(
        "config-check",
        help="Validate and print current configuration.",
        description="Validate and print current configuration.",
    )
    config_parser.set_defaults(handler=run_config_check)

    mcp_parser = subparsers.add_parser(
        "mcp",
        help="Run MCP server over stdio.",
        description="Run MCP server over stdio.",
    )
    mcp_parser.set_defaults(handler=run_mcp)

    return parser


def run_identity_transform(args):
    from services.exports import load_posts
    from storage.json_files import write_json_atomic
    from telegram.anonymization import MAP_PATH, transform_dataset

    source = Path(args.file)
    if not source.is_file():
        source = Path("data/raw") / args.file
    output = Path(args.output) if args.output else source.with_name(f"{source.stem}_{args.command}.json")
    if output.exists() or output.resolve() == source.resolve():
        raise ValueError("Output must be a new file")
    data = transform_dataset(load_posts(source), getattr(args, "map", MAP_PATH), args.channel, rules=getattr(args, "rules", None))
    # Reserve the output name so a concurrent conversion cannot overwrite it.
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8"):
        pass
    try:
        write_json_atomic(data, output)
    except BaseException:
        output.unlink(missing_ok=True)
        raise
    print(f"Created {output}")


def run_export(args):
    import export_comments

    args.export_format = args.format_flag or args.export_format or "json"
    asyncio.run(export_comments.main(args))


def run_analyze(args):
    import llm_analyzer

    llm_analyzer.main(args)


def resolve_compare_file(value=None):
    if value:
        path = Path(value)

        if path.exists():
            return path

        raw_path = Path("data/raw") / value

        if raw_path.exists():
            return raw_path

        raise FileNotFoundError(f"Compare file not found: {value}")

    candidates = sorted(Path("data/raw").glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)

    if not candidates:
        raise FileNotFoundError("No JSON exports found in data/raw. Pass --file.")

    return candidates[0]


def run_compare(args):
    from analytics.period_compare import compare_periods, load_posts
    from storage.sqlite_store import compare_periods as compare_periods_sqlite

    path = resolve_compare_file(args.file)
    result = None

    try:
        index_paths([path])
        result = compare_periods_sqlite(path.name, args.from_date, args.to_date)
    except IndexUnavailableError as e:
        print(f"SQLite compare failed for {path}: {e}", file=sys.stderr)

    if result is None:
        result = compare_periods(load_posts(path), args.from_date, args.to_date)

    result["file"] = str(path)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def resolve_index_files(value=None):
    if value:
        path = Path(value)

        if path.exists():
            return [path]

        raw_path = Path("data/raw") / value

        if raw_path.exists():
            return [raw_path]

        raise FileNotFoundError(f"Index file not found: {value}")

    return sorted(Path("data/raw").glob("*.json"))


def run_index(args):
    indexed = index_paths(resolve_index_files(args.file))
    print(json.dumps({"indexed": indexed, "count": len(indexed)}, ensure_ascii=False, indent=2))


def index_paths(paths):
    from services.exports import index_paths as index_export_paths

    return index_export_paths(paths)


def run_search(args):
    from storage.sqlite_store import search_all_comments, search_comments

    paths = resolve_index_files(args.file)
    indexed = index_paths(paths)

    if args.file:
        file_name = paths[0].name
        results = search_comments(file_name, args.query, args.limit)
    else:
        results = search_all_comments(args.query, args.limit, args.channel)

    print(json.dumps({
        "query": args.query,
        "indexed_count": len(indexed),
        "results": results,
    }, ensure_ascii=False, indent=2))


def run_dashboard(_args):
    import web_server

    web_server.main()


def run_watch(args):
    from exporters import telegram_exporter

    asyncio.run(telegram_exporter.watch_main(args))


def run_config_check(_args):
    import config

    ok = True

    try:
        export_config = config.load_export_config()
        print("Export config OK")
        print(f"CHANNEL={export_config.channel}")
        print(f"CHANNELS={', '.join(export_config.channels)}")
        print(f"TELEGRAM_SESSION={export_config.telegram_session}")
        print(f"POST_LIMIT={export_config.post_limit}")
        print(f"INCREMENTAL_LOOKBACK_POSTS={export_config.incremental_lookback_posts}")
        print(f"OUTPUT_FILE={export_config.output_file}")
    except Exception as e:
        ok = False
        print(f"Export config error: {e}", file=sys.stderr)

    try:
        llm_config = config.load_llm_config()
        print("LLM config OK")
        print(f"LLM_ENDPOINT={llm_config.endpoint}")
        print(f"LLM_MODEL={llm_config.model}")
    except Exception as e:
        ok = False
        print(f"LLM config error: {e}", file=sys.stderr)

    try:
        postgres_config = config.load_postgres_config()
        print("PostgreSQL config OK")
        print(f"POSTGRES_HOST={postgres_config.host}")
        print(f"POSTGRES_DB={postgres_config.db}")
        print(f"POSTGRES_TABLE={postgres_config.table}")
    except Exception as e:
        ok = False
        print(f"PostgreSQL config error: {e}", file=sys.stderr)

    if not ok:
        sys.exit(1)


def run_mcp(_args):
    import mcp_server

    mcp_server.main()


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    args.handler(args)


def run_cli(argv=None):
    """Keep expected errors concise; record tracebacks for unexpected failures."""
    try:
        main(argv)
        return 0
    except KeyboardInterrupt:
        return 130
    except (ApplicationError, ValueError, OSError) as error:
        print(f"{getattr(error, 'code', 'invalid_input')}: {error}", file=sys.stderr)
        return 2
    except Exception:
        logging.getLogger(__name__).exception("Unexpected CLI failure")
        return 1


if __name__ == "__main__":
    sys.exit(run_cli())

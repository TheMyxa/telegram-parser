import argparse
import asyncio
import sys


EXPORT_FORMATS = ("json", "csv", "postgresql", "parquet")


def build_parser():
    parser = argparse.ArgumentParser(
        prog="tg",
        description="TG comments exporter, analyzer and dashboard.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

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
        default="anonymizer",
        help="Text file with anonymized names, one alias per line. Default: anonymizer.",
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

    dashboard_parser = subparsers.add_parser(
        "dashboard",
        help="Run web dashboard on port 9595.",
        description="Run web dashboard on port 9595.",
    )
    dashboard_parser.set_defaults(handler=run_dashboard)

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


def run_export(args):
    import export_comments

    args.export_format = args.format_flag or args.export_format or "json"
    asyncio.run(export_comments.main(args))


def run_analyze(args):
    import llm_analyzer

    llm_analyzer.main(args)


def run_dashboard(_args):
    import web_server

    web_server.main()


def run_config_check(_args):
    import config

    print("Config OK")
    print(f"CHANNEL={config.CHANNEL}")
    print(f"CHANNELS={', '.join(config.CHANNELS)}")
    print(f"TELEGRAM_SESSION={config.TELEGRAM_SESSION}")
    print(f"POST_LIMIT={config.POST_LIMIT}")
    print(f"INCREMENTAL_LOOKBACK_POSTS={config.INCREMENTAL_LOOKBACK_POSTS}")
    print(f"OUTPUT_FILE={config.OUTPUT_FILE}")
    print(f"LLM_ENDPOINT={config.LLM_ENDPOINT}")
    print(f"LLM_MODEL={config.LLM_MODEL}")
    print(f"POSTGRES_HOST={config.POSTGRES_HOST}")
    print(f"POSTGRES_DB={config.POSTGRES_DB}")
    print(f"POSTGRES_TABLE={config.POSTGRES_TABLE}")


def run_mcp(_args):
    import mcp_server

    mcp_server.main()


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    args.handler(args)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)

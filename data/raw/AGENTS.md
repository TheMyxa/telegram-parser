# data/raw

This directory contains raw export outputs produced by TG.

Expected files:

- timestamped exports, for example `<channel>_YYYYMMDD_HHMMSS.json`;
- incremental datasets, for example `<channel>_dataset.json`;
- optional CSV or Parquet exports.

Most files in this directory are ignored by Git because they may contain private Telegram data.

Do not commit real exported datasets unless they are explicitly synthetic demo data.

Use `examples/example.json` for public demos and documentation.


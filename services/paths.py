"""Stable application paths, independent of the entrypoint location."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "web"
INDEX_FILE = WEB_DIR / "comments_dashboard.html"
DATA_DIR = ROOT / "data"
SCHEDULER_HISTORY_DIR = DATA_DIR / "scheduler"

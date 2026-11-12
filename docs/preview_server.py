"""Isolated read-only dashboard for documentation screenshots; no Telegram."""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=9596)
    args = parser.parse_args()
    original_cwd = Path.cwd()
    with tempfile.TemporaryDirectory(prefix="tg-docs-") as temporary:
        runtime = Path(temporary)
        data = runtime / "data"
        (data / "raw").mkdir(parents=True)
        posts = json.loads((ROOT / "examples/example.json").read_text(encoding="utf-8"))
        # The example references optional media not shipped in the repository.
        # Provide a clearly synthetic attachment in this temporary preview only.
        media = data / "content/demo.svg"
        media.parent.mkdir(parents=True)
        media.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="800" height="180"><rect width="800" height="180" fill="#163b45"/><text x="36" y="90" fill="#ffffff" font-family="sans-serif" font-size="28">TG — synthetic demo attachment</text></svg>', encoding="utf-8")
        for post in posts:
            if post.get("post_media"):
                post["post_media"] = "data/content/demo.svg"
        (data / "raw/demo_dataset.json").write_text(json.dumps(posts, ensure_ascii=False), encoding="utf-8")
        env = runtime / ".env"
        env.write_text("CHANNEL=demo_channel\nPOST_LIMIT=500\nINCREMENTAL_LOOKBACK_POSTS=50\nPOSTS_PAUSE_SECONDS=30\nPOSTS_PAUSE_AFTER_POSTS=500\n", encoding="utf-8")
        os.environ["TG_ENV_FILE"] = str(env)
        from api import web_server
        from services import dashboard_exports, scheduler_history

        web_server.DATA_DIR = dashboard_exports.DATA_DIR = data
        scheduler_history.SCHEDULER_HISTORY_DIR = data / "scheduler"

        class PreviewHandler(web_server.DashboardHandler):
            def do_GET(self):
                if self.path == "/api/docs-preview":
                    self.send_json({"synthetic_preview": True})
                    return
                super().do_GET()

            def do_POST(self):
                self.send_json({"ok": False, "error": "Documentation preview is read-only"}, status=403)

        os.chdir(runtime)
        try:
            with web_server.ThreadingHTTPServer(("0.0.0.0", args.port), PreviewHandler) as server:
                print(f"Documentation preview: http://localhost:{args.port}", flush=True)
                server.serve_forever()
        finally:
            os.chdir(original_cwd)


if __name__ == "__main__":
    main()

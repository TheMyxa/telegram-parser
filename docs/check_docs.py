"""Validate local Markdown links, README versions and screenshot PNG files."""
import ast
from pathlib import Path
import re
import struct
import sys
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent


def main():
    version_tree = ast.parse((ROOT / "version.py").read_text(encoding="utf-8"))
    version = next(ast.literal_eval(n.value) for n in version_tree.body
                   if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "APP_VERSION" for t in n.targets))
    files = [*ROOT.glob("*.md"), *sorted((ROOT / "docs").rglob("*.md"))]
    failures = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        if path.name.startswith("README") and f"`{version}`" not in text:
            failures.append(f"{path.name}: version does not match version.py")
        if text.count("```") % 2:
            failures.append(f"{path.name}: unclosed code fence")
        for target in re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", text):
            target = target.strip().strip("<>")
            if re.match(r"[a-zA-Z][a-zA-Z0-9+.-]*:", target) or target.startswith("#"):
                continue
            filename, _, anchor = unquote(target).partition("#")
            destination = (path.parent / filename).resolve()
            if not destination.exists():
                failures.append(f"{path.relative_to(ROOT)}: missing link {target}")
            elif anchor and destination.suffix == ".md":
                headings = re.findall(r"^#{1,6}\s+(.+)$", destination.read_text(encoding="utf-8"), re.M)
                slugs = {re.sub(r"[^\w\- ]", "", h.lower()).replace(" ", "-") for h in headings}
                if anchor not in slugs:
                    failures.append(f"{path.relative_to(ROOT)}: missing anchor {target}")
    for name in ("dashboard", "posts", "search", "export"):
        path = ROOT / "docs/screenshots" / f"{name}.png"
        if not path.exists():
            failures.append(f"Missing screenshot: {name}")
            continue
        data = path.read_bytes()
        if data[:8] != b"\x89PNG\r\n\x1a\n":
            failures.append(f"Invalid PNG: {name}")
        else:
            width, height = struct.unpack(">II", data[16:24])
            print(f"{name}.png: {width} x {height}")
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print(f"Checked {len(files)} Markdown files, README version {version}, and four screenshots.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

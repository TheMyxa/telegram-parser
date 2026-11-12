# Screenshot workflow

[English README](../README.md) · [Русский](../README_ru.md) · [中文](../README_cn.md)

The checked-in PNGs show the real dashboard at version **3.0.1**, captured with
Microsoft Edge, English UI, UTC timezone and a 1600 × 1100 viewport. Full-page
captures can be taller than the viewport.

| File | Content |
| --- | --- |
| [dashboard.png](screenshots/dashboard.png) | Summary, charts and activity heatmap |
| [posts.png](screenshots/posts.png) | Expanded post and comment tree |
| [search.png](screenshots/search.png) | Global search results for `export` |
| [export.png](screenshots/export.png) | Export, Scheduler and Watch controls, idle |

Only `examples/example.json` is used: three posts, seven comments and five users.
The preview substitutes a simple synthetic SVG for the optional media attachment
that is not shipped with the example. This adaptation exists only in temporary
preview data; the repository's example is unchanged. No real credentials,
sessions, comments or private identity maps are loaded.

## Start the isolated preview

Build the project image, then run a dedicated container. The repository mount is
read-only; configuration, JSON, SQLite and history live in a temporary directory
inside this container. All POST requests are rejected, so no export can start.

```powershell
docker compose build dashboard
docker run --rm -d --name tg-docs-preview --mount "type=bind,source=$PWD,target=/workspace,readonly" --workdir /workspace -p 127.0.0.1:19596:9596 --entrypoint python tg:latest docs/preview_server.py
```

Open `http://127.0.0.1:19596`. Do not use the normal dashboard containing private
runtime data to create public screenshots.

## Capture with an installed browser

The capture script uses `playwright-core` as a temporary documentation tool. It
is not a dashboard or Python dependency. Node.js and Microsoft Edge are needed
for this Windows example; `TG_BROWSER_PATH` can instead point to Google Chrome.

```powershell
npm.cmd install --prefix "$env:TEMP\tg-docs-browser" playwright-core --no-package-lock --no-save
$env:TG_PLAYWRIGHT_MODULE = Join-Path $env:TEMP 'tg-docs-browser\node_modules\playwright-core'
$env:TG_BROWSER_PATH = 'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
node docs/capture_screenshots.cjs
```

`TG_DOCS_URL` optionally selects another preview URL. The script loads the demo
export, waits for data, expands a post, performs a search, and captures four tabs.
It never clicks export/scheduler/watch start buttons. JavaScript errors fail the
capture. Before opening the page, it checks the preview-only
`/api/docs-preview` marker and refuses a normal dashboard server. Inspect all PNGs
before committing them. When done:

```powershell
docker stop tg-docs-preview
```

For local Python, `python docs/preview_server.py --port 9596` creates the same
temporary runtime; use `TG_DOCS_URL=http://127.0.0.1:9596` for the capture process.

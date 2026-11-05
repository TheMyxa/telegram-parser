# TG

[English](README.md) | [Русский](README_ru.md)

TG 是一个本地优先的 Telegram 评论导出和分析工具。它可以导出频道帖子、讨论区评论、反应、链接、可选媒体文件，并支持增量更新已有 dataset。

当前版本：`2.1.0`。

## 功能

- 使用 Telethon 导出 Telegram 频道帖子和评论。
- `CHANNEL` 支持用逗号配置多个频道。
- 导出格式：`JSON`、`CSV`、`Parquet`、`PostgreSQL`。
- 真正的增量导出：导出新帖子，同时回看一部分旧帖子，刷新评论、反应和计数器。
- 可选下载媒体到 `data/content/<dataset_name>/`。
- 可选匿名化 `user_id`、`username`、`first_name`、`last_name`。
- Web UI 运行在 `9595` 端口，包含 dashboard、活动热力图、全局搜索、帖子列表、评论树、过滤器、用户详情、导出启动页、Scheduler mode 和 Watch mode。
- 可直接从 dashboard 打开 `data/raw` 中的本地 JSON 导出，并按日期或频道排序。
- 使用本地 SQLite 索引 `data/state/tg.sqlite` 加速 summary、周期对比以及 MCP/CLI 全文搜索。
- 支持对导出的 JSON 文件进行 LLM 分析，内置中文、英文、俄文 prompt 文件。
- 可通过 `tg compare` 对比两个周期的评论、用户和反应。
- MCP 服务器，用于让 AI 客户端通过标准工具接口读取本地导出和启动分析。
- Docker Compose 本地启动。

## 快速启动

```powershell
docker compose up --build
```

打开：

```text
http://localhost:9595
```

## 配置

Docker 会在首次启动时从 `.env.example` 创建 `.env`，所以新用户只需要一条命令：

```powershell
docker compose up --build
```

然后打开 `http://localhost:9595`，在 Export 页面填写 Telegram 配置。

如果你想先手动编辑文件，也可以自己创建 `.env`：

```powershell
Copy-Item .env.example .env
```

示例：

```env
API_ID=123456
API_HASH=your_api_hash_here
CHANNEL=your_channel,another_channel
TELEGRAM_SESSION=sessions/session
OUTPUT_FILE=data/raw/export.json
POST_LIMIT=500
INCREMENTAL_LOOKBACK_POSTS=50
POSTS_PAUSE_SECONDS=30
POSTS_PAUSE_AFTER_POSTS=500

POSTGRES_HOST=host.docker.internal
POSTGRES_PORT=5432
POSTGRES_DB=telegram_parser
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_postgres_password_here
POSTGRES_TABLE=telegram_comments_export

LLM_ENDPOINT=http://localhost:1234/v1/chat/completions
LLM_MODEL=local-model
```

重要配置：

- `API_ID`、`API_HASH`：Telegram API 凭据。
- `CHANNEL`：一个或多个频道，用逗号分隔，例如 `durov,telegram`。
- `TELEGRAM_SESSION`：Telethon session 文件路径，通常放在 `sessions/` 内。
- `POST_LIMIT`：每次运行扫描的新帖子/latest 帖子数量。
- `INCREMENTAL_LOOKBACK_POSTS`：增量模式下，在 `last_post_id` 及更旧范围内回看多少个已经导出的旧帖子。
- `POSTS_PAUSE_SECONDS`：暂停秒数。
- `POSTS_PAUSE_AFTER_POSTS`：每处理 N 个帖子后暂停。
- `LLM_ENDPOINT`、`LLM_MODEL`：用于 `analyze` 命令。

配置会按命令验证：`export` 需要 Telegram 配置，`analyze` 需要 LLM 配置，PostgreSQL 配置只在 `postgresql` 导出时加载。

## CLI

```powershell
docker compose run --rm cli --help
docker compose run --rm cli config-check
docker compose run --rm cli export json --incremental
docker compose run --rm cli watch --poll-interval 30 --refresh-active-posts 20
docker compose run --rm cli index --file durov_dataset.json
docker compose run --rm cli search "telegram" --file durov_dataset.json
docker compose run --rm cli compare --from 2026-07-01 --to 2026-08-01 --file durov_dataset.json
docker compose run --rm cli export json --incremental --download-media
docker compose run --rm cli analyze example.json --limit 5
```

### 增量导出

```powershell
docker compose run --rm cli export json --incremental
```

增量模式会更新：

```text
data/raw/<channel>_dataset.json
data/state/<channel>_state.json
data/state/tg.sqlite
```

增量导出状态保存在 SQLite 表 `export_states` 中；每个频道的 JSON state 文件仍保留为兼容 fallback 和迁移来源。

导出器会扫描比已保存 `last_post_id` 更新的帖子，并额外回看 `last_post_id` 及更旧范围内的 `INCREMENTAL_LOOKBACK_POSTS` 个旧帖子。这样旧帖子中新增加的评论、反应和计数器也会被刷新。

JSON 导出也会索引到本地 SQLite 数据库 `data/state/tg.sqlite`。这是 runtime 文件，可以从 JSON 导出重新生成。

### SQLite 索引

不运行 Telegram 导出，也可以构建或刷新本地 SQLite 索引：

```powershell
docker compose run --rm cli index
docker compose run --rm cli index --file durov_dataset.json
```

Dashboard 和 MCP 服务器在需要 summary、compare 或搜索时也会按需索引 JSON。

### 索引搜索

搜索单个导出：

```powershell
docker compose run --rm cli search "telegram" --file durov_dataset.json
```

搜索 `data/raw` 中的全部 JSON 导出：

```powershell
docker compose run --rm cli search "telegram" --limit 50
```

搜索会优先使用 SQLite FTS5；如果 FTS5 不可用，或者 FTS 查询语法无效，会自动回退到普通 `LIKE` 匹配。

### LLM 分析

```powershell
docker compose run --rm cli analyze durov_dataset.json --limit 10
```

选择 prompt 语言：

```powershell
docker compose run --rm cli analyze durov_dataset.json --limit 10 --language en
docker compose run --rm cli analyze durov_dataset.json --limit 10 --language zh
```

内置 prompt 文件：

- `prompts/llm_ru.json`
- `prompts/llm_en.json`
- `prompts/llm_zh.json`

也可以传入自定义 prompt 文件：

```powershell
docker compose run --rm cli analyze durov_dataset.json --prompt-file prompts/llm_zh.json
```

Prompt 文件必须是 JSON 对象，包含 `system` 和 `user_template` 字段；`user_template` 必须包含 `{data}` placeholder。

## MCP 服务器

通过 stdio 启动 MCP 服务器：

```powershell
docker compose run --rm -i cli mcp
```

本地 Python：

```powershell
python main.py mcp
```

可用 tools：

- `get_config_safe`：读取非敏感配置，敏感值会被遮蔽。
- `list_exports`、`get_export_summary`、`get_post`、`search_comments`、`search_all_comments`：读取和搜索 `data/raw` 中的 JSON 导出。搜索会优先使用 SQLite FTS5，并带有 `LIKE` fallback。
- `list_analysis_files`、`list_analysis_results`、`read_analysis`、`run_analysis`：处理 LLM 分析文件。分析元数据会索引到 SQLite，便于快速列出和查看错误。
- `start_export`、`get_export_process_status`：启动和监控 Telegram 导出。`start_export` 需要 `confirm=true`。

## Dashboard 本地导出

Dashboard 可以直接打开 `data/raw` 中的本地 JSON 导出，无需手动上传文件。

Scheduler mode 可以每 N 分钟自动更新选中的频道。第一次导出会立即开始；如果到达下一次间隔时上一次导出仍在运行，本次运行会被跳过。

Watch mode 独立于 Scheduler。它是一个长期运行的进程，会保持 Telethon session，监听新帖子和 discussion 活动，并只更新 `data/raw/<channel>_dataset.json` 中发生变化的帖子。周期刷新用于补充计数器、反应、嵌套回复和可能漏掉的事件。

API:

- `GET /api/version`：返回当前应用版本。
- `GET /api/exports?sort=date|channel`：列出 `data/raw` 中的 JSON 导出；可用时包含 SQLite 索引统计。
- `GET /api/search?q=text&channel=name&from=YYYY-MM-DD&to=YYYY-MM-DD&user=username&limit=50`：在全部本地 JSON 导出的索引评论中搜索。
- `GET /api/export/<file>/summary`：返回一个 JSON 导出的计数和元数据。
- `GET /api/export/<file>/filtered-summary?q=text&user=username&from=YYYY-MM-DD&to=YYYY-MM-DD&emoji=👍&media=1&replies=1`：返回筛选后 dashboard 视图的 SQLite 计数。
- `GET /api/export/<file>/charts`：返回单个 JSON 导出的 SQLite dashboard 图表聚合。
- `GET /api/export/<file>/posts?limit=100&offset=0&q=text&user=username&from=YYYY-MM-DD&to=YYYY-MM-DD&emoji=👍&media=1&replies=1`：从 SQLite 返回 dashboard 表格的帖子行。
- `GET /api/export/<file>/post/<post_id>`：从 SQLite 返回一个重建后的帖子及其评论。
- `GET /api/export/<file>/compare?from=YYYY-MM-DD&to=YYYY-MM-DD`：对比两个周期的评论、用户和反应。
- `GET /api/scheduler/status`：返回当前 scheduler 状态。
- `GET /api/scheduler/history?limit=50&offset=0&status=FAILED&channel=durov`：从 SQLite 列出已保存的 scheduler 运行记录，支持分页、过滤和统计。
- `GET /api/scheduler/history/<run_id>`：返回一个 scheduler 运行详情。
- `POST /api/scheduler/history/<run_id>/retry`：用相同频道、格式和导出标志重试一个已保存的 scheduler run。
- `POST /api/scheduler/start`：使用 `channel`、`interval_minutes`、格式和导出标志启动定时导出。
- `POST /api/scheduler/stop`：停止 scheduler。
- `GET /api/watch/status`：返回当前 Watch mode 状态。
- `POST /api/watch/start`：使用 `channel`、`poll_interval`、`refresh_active_posts` 和导出标志启动 Watch mode。
- `POST /api/watch/stop`：停止 Watch mode。

Scheduler 历史保存在本地 SQLite 索引 `data/state/tg.sqlite` 中。旧的 `data/scheduler/` JSON 记录会在读取历史时按需导入。每次运行都有自己的状态：`QUEUED`、`RUNNING`、`SUCCESS`、`PARTIAL`、`FAILED`、`SKIPPED` 或 `CANCELLED`，并保存频道结果、结构化错误和最近日志。

## Demo JSON

无需连接 Telegram，也可以使用 demo 文件测试 dashboard：

- [examples/example.json](examples/example.json)

## 数据与安全

不要提交 runtime 数据：

- `.env`
- `sessions/`
- `data/raw/*`
- `data/content/*`
- `data/analysis/*`
- `data/state/*`

Per-post LLM cache 保存在 SQLite 表 `analysis_cache` 中，键为 `source_file`, `post_id`, `post_hash`, `prompt_hash`, `model`；重新分析时会跳过未变化且已有 successful cached result 的帖子。

密钥、Telegram session、真实评论和下载的媒体文件应只保存在本地。

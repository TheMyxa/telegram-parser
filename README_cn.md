# TG

[English](README.md) | [Русский](README_ru.md)

TG 是一个本地优先的 Telegram 评论导出和分析工具。它可以导出频道帖子、讨论区评论、反应、链接、可选媒体文件，并支持增量更新已有 dataset。

## 功能

- 使用 Telethon 导出 Telegram 频道帖子和评论。
- `CHANNEL` 支持用逗号配置多个频道。
- 导出格式：`JSON`、`CSV`、`Parquet`、`PostgreSQL`。
- 真正的增量导出：导出新帖子，同时回看一部分旧帖子，刷新评论、反应和计数器。
- 可选下载媒体到 `data/content/<dataset_name>/`。
- 可选匿名化 `user_id`、`username`、`first_name`、`last_name`。
- Web UI 运行在 `9595` 端口，包含 dashboard、帖子列表、评论树、过滤器、用户详情和导出启动页。
- 支持对导出的 JSON 文件进行 LLM 分析，内置中文、英文、俄文 prompt 文件。
- MCP 服务器，用于让 AI 客户端通过标准工具接口读取本地导出和启动分析。
- Docker Compose 本地启动。

## 快速启动

```powershell
docker compose up --build dashboard
```

打开：

```text
http://localhost:9595
```

## 配置

从示例创建 `.env`：

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

## CLI

```powershell
docker compose run --rm cli --help
docker compose run --rm cli config-check
docker compose run --rm cli export json --incremental
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
```

导出器会扫描比已保存 `last_post_id` 更新的帖子，并额外回看 `last_post_id` 及更旧范围内的 `INCREMENTAL_LOOKBACK_POSTS` 个旧帖子。这样旧帖子中新增加的评论、反应和计数器也会被刷新。

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
- `list_exports`、`get_export_summary`、`get_post`、`search_comments`：读取和搜索 `data/raw` 中的 JSON 导出。
- `list_analysis_files`、`read_analysis`、`run_analysis`：处理 LLM 分析文件。
- `start_export`、`get_export_process_status`：启动和监控 Telegram 导出。`start_export` 需要 `confirm=true`。

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

密钥、Telegram session、真实评论和下载的媒体文件应只保存在本地。

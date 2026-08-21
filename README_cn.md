# TG

[English](README.md) | [Русский](README_ru.md)

TG 是一个本地优先的 Telegram 评论导出和分析工具。

## 功能

- 导出 Telegram 频道帖子、评论、反应、链接和媒体信息。
- 支持 `JSON`、`CSV`、`Parquet`、`PostgreSQL` 导出格式。
- 增量导出：更新已有 dataset，并避免重复下载媒体文件。
- Web UI 运行在 `9595` 端口，包含 dashboard、图表、帖子列表、评论树、过滤器和用户详情。
- 可以从浏览器启动导出任务。
- 可以在网站中编辑 `.env` 配置。
- 支持用户匿名化。
- 支持对导出的 JSON 文件进行 LLM 分析。

## 快速启动

```powershell
docker compose up --build dashboard
```

打开：

```text
http://localhost:9595
```

## CLI

```powershell
docker compose run --rm cli --help
docker compose run --rm cli config-check
docker compose run --rm cli export json --incremental
docker compose run --rm cli export json --incremental --download-media
docker compose run --rm cli analyze example.json --limit 5
```

## Demo JSON

无需连接 Telegram，也可以使用 demo 文件测试 dashboard：

- [examples/example.json](examples/example.json)
- [examples/example.json](examples/example.json)

## 配置

从示例文件创建 `.env`：

```powershell
Copy-Item .env.example .env
```

主要配置项：

- `API_ID`
- `API_HASH`
- `CHANNEL`
- `POST_LIMIT`
- `OUTPUT_FILE`
- `LLM_ENDPOINT`
- `LLM_MODEL`

不要提交 `.env`、`sessions/`、`data/raw/` 中的真实导出数据或下载的媒体文件。

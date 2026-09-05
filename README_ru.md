# TG

[English](README.md) | [中文](README_cn.md)

TG - локальный инструмент для экспорта комментариев Telegram и аналитики. Он выгружает посты каналов, комментарии из обсуждений, реакции, ссылки, опциональные медиафайлы и умеет инкрементально обновлять уже собранный dataset.

## Возможности

- Экспорт постов и комментариев Telegram через Telethon.
- Несколько каналов в `CHANNEL` через запятую.
- Форматы экспорта: `JSON`, `CSV`, `Parquet`, `PostgreSQL`.
- Настоящий инкрементальный экспорт: новые посты плюс повторная проверка старых постов на новые комментарии, реакции и счетчики.
- Опциональная загрузка медиа в `data/content/<dataset_name>/`.
- Опциональная анонимизация `user_id`, `username`, `first_name`, `last_name`.
- Web UI на порту `9595`: dashboard, список постов, дерево комментариев, фильтры, профили пользователей и запуск экспорта.
- LLM-анализ экспортированных JSON-файлов с prompt-файлами на русском, английском и китайском языках.
- MCP-сервер для локальной автоматизации и работы с экспортами через AI-клиенты.
- Docker Compose для локального запуска.

## Быстрый Старт

```powershell
docker compose up --build dashboard
```

Откройте:

```text
http://localhost:9595
```

## Конфигурация

Создайте `.env` из примера:

```powershell
Copy-Item .env.example .env
```

Пример:

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

Важные поля:

- `API_ID`, `API_HASH`: учетные данные Telegram API.
- `CHANNEL`: один или несколько каналов через запятую, например `durov,telegram`.
- `TELEGRAM_SESSION`: путь к файлу сессии Telethon, обычно внутри `sessions/`.
- `POST_LIMIT`: сколько новых/latest постов просматривать за запуск.
- `INCREMENTAL_LOOKBACK_POSTS`: сколько уже экспортированных старых постов перепроверять на уровне `last_post_id` и ниже.
- `POSTS_PAUSE_SECONDS`: длительность паузы в секундах.
- `POSTS_PAUSE_AFTER_POSTS`: делать паузу после каждого N-го обработанного поста.
- `LLM_ENDPOINT`, `LLM_MODEL`: используются командой `analyze`.

## CLI

```powershell
docker compose run --rm cli --help
docker compose run --rm cli config-check
docker compose run --rm cli export json --incremental
docker compose run --rm cli export json --incremental --download-media
docker compose run --rm cli analyze example.json --limit 5
```

### Инкрементальный Экспорт

```powershell
docker compose run --rm cli export json --incremental
```

Инкрементальный режим обновляет:

```text
data/raw/<channel>_dataset.json
data/state/<channel>_state.json
```

Экспортер просматривает посты новее сохраненного `last_post_id` и дополнительно `INCREMENTAL_LOOKBACK_POSTS` уже известных старых постов с ID на уровне `last_post_id` и ниже. Это обновляет реакции, счетчики и комментарии у старых постов, которые изменились после предыдущего запуска.

### LLM-Анализ

```powershell
docker compose run --rm cli analyze durov_dataset.json --limit 10
```

Выбор языка prompt:

```powershell
docker compose run --rm cli analyze durov_dataset.json --limit 10 --language en
docker compose run --rm cli analyze durov_dataset.json --limit 10 --language zh
```

Prompt-файлы:

- `prompts/llm_ru.json`
- `prompts/llm_en.json`
- `prompts/llm_zh.json`

Можно передать свой файл:

```powershell
docker compose run --rm cli analyze durov_dataset.json --prompt-file prompts/llm_en.json
```

Файл prompt должен быть JSON-объектом с полями `system` и `user_template`; в `user_template` обязателен placeholder `{data}`.

## MCP-Сервер

Запуск MCP-сервера через stdio:

```powershell
docker compose run --rm -i cli mcp
```

Локально:

```powershell
python main.py mcp
```

Доступные tools:

- `get_config_safe`: безопасный просмотр конфигурации с маскированием секретов.
- `list_exports`, `get_export_summary`, `get_post`, `search_comments`: работа с JSON-экспортами из `data/raw`.
- `list_analysis_files`, `read_analysis`, `run_analysis`: работа с LLM-анализом.
- `start_export`, `get_export_process_status`: запуск и мониторинг Telegram-экспорта. `start_export` требует `confirm=true`.

## Demo JSON

Для проверки dashboard без подключения к Telegram используйте:

- [examples/example.json](examples/example.json)

## Данные И Безопасность

Не коммитьте runtime-данные:

- `.env`
- `sessions/`
- `data/raw/*`
- `data/content/*`
- `data/analysis/*`
- `data/state/*`

Секреты, сессии Telegram, реальные комментарии и скачанные медиа должны оставаться локальными.

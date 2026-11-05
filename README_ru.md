# TG

[English](README.md) | [中文](README_cn.md)

TG - локальный инструмент для экспорта комментариев Telegram и аналитики. Он выгружает посты каналов, комментарии из обсуждений, реакции, ссылки, опциональные медиафайлы и умеет инкрементально обновлять уже собранный dataset.

Текущая версия: `2.1.0`.

## Возможности

- Экспорт постов и комментариев Telegram через Telethon.
- Несколько каналов в `CHANNEL` через запятую.
- Форматы экспорта: `JSON`, `CSV`, `Parquet`, `PostgreSQL`.
- Настоящий инкрементальный экспорт: новые посты плюс повторная проверка старых постов на новые комментарии, реакции и счетчики.
- Опциональная загрузка медиа в `data/content/<dataset_name>/`.
- Опциональная анонимизация `user_id`, `username`, `first_name`, `last_name`.
- Web UI на порту `9595`: dashboard, тепловая карта активности, глобальный поиск, список постов, дерево комментариев, фильтры, профили пользователей, запуск экспорта, Scheduler mode и Watch mode.
- Открытие локальных JSON-экспортов из `data/raw` прямо в dashboard с сортировкой по дате или каналу.
- Локальный SQLite-индекс `data/state/tg.sqlite` для быстрых summary, сравнения периодов и полнотекстового MCP/CLI-поиска.
- LLM-анализ экспортированных JSON-файлов с prompt-файлами на русском, английском и китайском языках.
- Сравнение периодов по комментариям, пользователям и реакциям через `tg compare`.
- MCP-сервер для локальной автоматизации и работы с экспортами через AI-клиенты.
- Docker Compose для локального запуска.

## Быстрый Старт

```powershell
docker compose up --build
```

Откройте:

```text
http://localhost:9595
```

## Конфигурация

Docker создает `.env` из `.env.example` при первом запуске, поэтому для старта достаточно одной команды:

```powershell
docker compose up --build
```

Затем откройте `http://localhost:9595` и заполните Telegram-настройки во вкладке экспорта.

Если удобнее отредактировать файл до запуска, создайте `.env` вручную:

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

Конфигурация валидируется по командам: `export` требует Telegram-настройки, `analyze` требует LLM-настройки, а PostgreSQL-настройки загружаются только для экспорта `postgresql`.

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

### Инкрементальный Экспорт

```powershell
docker compose run --rm cli export json --incremental
```

Инкрементальный режим обновляет:

```text
data/raw/<channel>_dataset.json
data/state/<channel>_state.json
data/state/tg.sqlite
```

Состояние инкрементального экспорта хранится в SQLite-таблице `export_states`; JSON-файл состояния по каналу остается fallback и источником миграции.

Экспортер просматривает посты новее сохраненного `last_post_id` и дополнительно `INCREMENTAL_LOOKBACK_POSTS` уже известных старых постов с ID на уровне `last_post_id` и ниже. Это обновляет реакции, счетчики и комментарии у старых постов, которые изменились после предыдущего запуска.

JSON-экспорты также индексируются в локальную SQLite-базу `data/state/tg.sqlite`. Это runtime-файл, его можно пересобрать из JSON.

### Индексация SQLite

Построить или обновить локальный SQLite-индекс без Telegram-экспорта:

```powershell
docker compose run --rm cli index
docker compose run --rm cli index --file durov_dataset.json
```

Dashboard и MCP-сервер также индексируют JSON лениво, когда им нужны summary, compare или поиск.

### Поиск По Индексу

Поиск в одном экспорте:

```powershell
docker compose run --rm cli search "telegram" --file durov_dataset.json
```

Поиск по всем JSON-экспортам из `data/raw`:

```powershell
docker compose run --rm cli search "telegram" --limit 50
```

Поиск использует SQLite FTS5, когда он доступен, и автоматически откатывается на обычный `LIKE`, если FTS5 недоступен или запрос имеет неверный FTS-синтаксис.

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
- `list_exports`, `get_export_summary`, `get_post`, `search_comments`, `search_all_comments`: работа с JSON-экспортами из `data/raw`. Поиск использует SQLite FTS5, когда он доступен, с fallback на `LIKE`.
- `list_analysis_files`, `list_analysis_results`, `read_analysis`, `run_analysis`: работа с LLM-анализом. Метаданные анализа индексируются в SQLite для быстрого списка и просмотра ошибок.
- `start_export`, `get_export_process_status`: запуск и мониторинг Telegram-экспорта. `start_export` требует `confirm=true`.

## Demo JSON

Для проверки dashboard без подключения к Telegram используйте:

- [examples/example.json](examples/example.json)

Dashboard также может открыть локальный JSON-экспорт из `data/raw` без ручного выбора файла.

Во вкладке экспорта есть Scheduler mode: выбранные каналы можно обновлять автоматически каждые N минут. Первый запуск выполняется сразу, затем повторяется по интервалу. Если предыдущий экспорт еще работает, очередной запуск пропускается.

Watch mode работает отдельно от Scheduler: это долгоживущий процесс, который держит Telethon-сессию открытой, следит за новыми постами и активностью discussion-чата, а затем обновляет измененные посты в `data/raw/<channel>_dataset.json`. Периодический refresh нужен для счетчиков, реакций, вложенных ответов и пропущенных событий.

API dashboard:

- `GET /api/version`: текущая версия приложения.
- `GET /api/exports?sort=date|channel`: список JSON-экспортов из `data/raw` со счетчиками из SQLite, когда они доступны.
- `GET /api/search?q=text&channel=name&from=YYYY-MM-DD&to=YYYY-MM-DD&user=username&limit=50`: поиск по проиндексированным комментариям во всех локальных JSON-экспортах.
- `GET /api/export/<file>/summary`: счетчики и метаданные одного JSON-экспорта.
- `GET /api/export/<file>/filtered-summary?q=text&user=username&from=YYYY-MM-DD&to=YYYY-MM-DD&emoji=👍&media=1&replies=1`: счетчики из SQLite для отфильтрованного dashboard.
- `GET /api/export/<file>/charts`: агрегаты для графиков dashboard из SQLite по одному JSON-экспорту.
- `GET /api/export/<file>/posts?limit=100&offset=0&q=text&user=username&from=YYYY-MM-DD&to=YYYY-MM-DD&emoji=👍&media=1&replies=1`: строки постов для таблицы dashboard из SQLite.
- `GET /api/export/<file>/post/<post_id>`: один восстановленный пост с комментариями из SQLite.
- `GET /api/export/<file>/compare?from=YYYY-MM-DD&to=YYYY-MM-DD`: сравнение комментариев, пользователей и реакций между периодами.
- `GET /api/scheduler/status`: текущее состояние scheduler.
- `GET /api/scheduler/history?limit=50&offset=0&status=FAILED&channel=durov`: список сохраненных запусков scheduler из SQLite с пагинацией, фильтрами и статистикой.
- `GET /api/scheduler/history/<run_id>`: подробная карточка одного запуска scheduler.
- `POST /api/scheduler/history/<run_id>/retry`: повторный запуск сохраненного scheduler run с теми же каналами, форматом и флагами экспорта.
- `POST /api/scheduler/start`: запуск scheduler с `channel`, `interval_minutes`, форматом и флагами экспорта.
- `POST /api/scheduler/stop`: остановка scheduler.
- `GET /api/watch/status`: текущее состояние Watch mode.
- `POST /api/watch/start`: запуск Watch mode с `channel`, `poll_interval`, `refresh_active_posts` и флагами экспорта.
- `POST /api/watch/stop`: остановка Watch mode.

История Scheduler хранится в локальном SQLite-индексе `data/state/tg.sqlite`. Старые JSON-записи из `data/scheduler/` импортируются лениво при чтении истории. Каждый запуск получает статус `QUEUED`, `RUNNING`, `SUCCESS`, `PARTIAL`, `FAILED`, `SKIPPED` или `CANCELLED`, результаты по каналам, структурированную ошибку и последние строки лога.

## Данные И Безопасность

Не коммитьте runtime-данные:

- `.env`
- `sessions/`
- `data/raw/*`
- `data/content/*`
- `data/analysis/*`
- `data/state/*`

Per-post LLM cache хранится в SQLite-таблице `analysis_cache` по ключам `source_file`, `post_id`, `post_hash`, `prompt_hash`, `model`; повторный анализ пропускает неизмененные посты с успешным cached result.

Секреты, сессии Telegram, реальные комментарии и скачанные медиа должны оставаться локальными.

# TG

[English](README.md) | [中文](README_cn.md)

TG — локальный инструмент для экспорта и анализа комментариев Telegram.

## Возможности

- Экспорт постов, комментариев, реакций, ссылок и медиа из Telegram-каналов.
- Форматы экспорта: `JSON`, `CSV`, `Parquet`, `PostgreSQL`.
- Инкрементальный экспорт: обновляет существующий dataset и не скачивает одно и то же медиа повторно.
- Web UI на порту `9595` с dashboard, графиками, списком постов, деревом комментариев, фильтрами и карточками пользователей.
- Запуск экспорта из браузера.
- Редактирование `.env` через сайт.
- Анонимизация пользователей.
- LLM-анализ экспортированных JSON-файлов.

## Быстрый запуск

```powershell
docker compose up --build dashboard
```

Откройте:

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

Для проверки dashboard без подключения к Telegram используйте:

- [examples/example.json](examples/example.json)
- [examples/example.json](examples/example.json)

## Конфигурация

Создайте `.env` из примера:

```powershell
Copy-Item .env.example .env
```

Основные параметры:

- `API_ID`
- `API_HASH`
- `CHANNEL`
- `POST_LIMIT`
- `OUTPUT_FILE`
- `LLM_ENDPOINT`
- `LLM_MODEL`

Не коммитьте `.env`, `sessions/`, реальные файлы из `data/raw/` и скачанные медиа.

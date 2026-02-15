# CLAUDE.md — assistant_bot

## Project overview

Telegram bot for the "Fintech DL HSE" deep learning course at HSE University. Serves as a course assistant: Q&A via LLM, homework repo checking, quizzes with LLM-as-a-judge, GitHub/Google Drive integrations, admin tools, automated backups.

## Tech stack

- **Language:** Python 3.10+ (uses PEP 604 union types `X | None`, PEP 585 lowercase generics `list[str]`)
- **No framework** — raw `requests` against Telegram Bot API with long-polling
- **LLM:** OpenAI SDK pointed at Cloud.ru endpoint (`gpt-oss-120b`)
- **State:** local JSON/JSONL files (no database)
- **Dependencies:** `openai`, `requests`, `schedule`, `google-api-python-client`, `google-auth`

## Project structure

```
src/
├── bot.py              # Main bot logic (~3500 lines), command dispatch, all handlers
├── telegram_client.py  # Telegram Bot API HTTP wrapper (TelegramClient class)
├── github_client.py    # GitHub REST API client (module-level functions)
└── drive_client.py     # Google Drive API client (form copying)
```

Config: `bot_config.json` (gitignored, see `bot_config_example.json` for schema).

## Commands

```bash
# Install
pip install -r requirements.txt

# Run
python src/bot.py \
  --config bot_config.json \
  --pm-log-file private_messages.jsonl \
  --quizzes-file quizzes.json \
  --quiz-state-file quiz_state.json \
  --users-file users.json
```

## Environment variables

- `TELEGRAM_BOT_TOKEN` — Telegram bot token (required)
- `API_KEY` — Cloud.ru LLM API key (required for /qa)
- `GITHUB_TOKEN` — GitHub PAT (required for /invit, hw checks)

## Code conventions

- **Architecture:** flat procedural; one large `_handle_message()` with `elif cmd ==` dispatch
- **Naming:** `snake_case` functions/vars, `_leading_underscore` for private helpers, `UPPER_SNAKE_CASE` constants
- **Logging:** `_log = logging.getLogger(__name__)`, INFO level, `exc_info=True` on warnings
- **State writes:** atomic via tmp file + `Path.replace()`
- **Error handling:** `try/except Exception` with graceful fallback messages to users
- **Markdown:** bot sends MarkdownV2, falls back to plain text via `_send_with_formatting_fallback()`
- **Config is re-read on every message** (by design)
- **No tests, no CI, no Docker**

## Key patterns

- `TelegramClient` is the only class; everything else is module-level functions
- Quiz creation uses an in-memory wizard state dict keyed by user ID
- Scheduled weekly backup (Monday 10:00 UTC) runs in a background thread
- GitHub client uses API version `2022-11-28` header

## External integrations

| Service | Auth |
|---|---|
| Telegram Bot API | `TELEGRAM_BOT_TOKEN` env |
| Cloud.ru Foundation Models | `API_KEY` env |
| GitHub REST API | `GITHUB_TOKEN` env |
| Google Drive API | Service account JSON file |

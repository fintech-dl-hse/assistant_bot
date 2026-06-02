import logging
from pathlib import Path

from context import BotContext
from text_format import _send_with_formatting_fallback

_log = logging.getLogger(__name__)

API_KEYS_FILE = "/var/lib/course_assistant/api_keys.txt"

_COURSE_MEMBER_STATUSES = {"creator", "administrator", "member", "restricted"}


def _load_api_keys(path: str) -> list[str]:
    with Path(path).open("r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def handle_agent_api_key(ctx: BotContext) -> None:
    if ctx.chat_type != "private":
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text="Пожалуйста, используйте /agent_api_key в личных сообщениях с ботом.",
        )
        return

    course_chat_id = ctx.settings.get("course_chat_id")
    if not isinstance(course_chat_id, int) or course_chat_id == 0:
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text="Чат курса не настроен. Обратитесь к администратору.",
        )
        return

    try:
        member = ctx.tg.get_chat_member(chat_id=course_chat_id, user_id=ctx.user_id)
        status = str((member.get("result") or {}).get("status") or "")
    except Exception as e:
        _log.warning("Failed to check course chat membership for user %s", ctx.user_id, exc_info=True)
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text=f"Не удалось проверить участие в чате курса: {type(e).__name__}: {e}",
        )
        return

    if status not in _COURSE_MEMBER_STATUSES:
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text="Команда доступна только студентам курса. Сначала вступите в чат курса.",
        )
        return

    try:
        keys = _load_api_keys(API_KEYS_FILE)
    except Exception as e:
        _log.warning("Failed to read API keys file %s", API_KEYS_FILE, exc_info=True)
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text=f"Не удалось прочитать файл с ключами: {type(e).__name__}: {e}",
        )
        return

    if not keys:
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text="Список ключей пуст. Обратитесь к администратору.",
        )
        return

    api_key = keys[ctx.user_id % len(keys)]

    _send_with_formatting_fallback(
        tg=ctx.tg,
        chat_id=ctx.chat_id,
        message_thread_id=ctx.message_thread_id,
        text=f"Ваш персональный API ключ:\n`{api_key}`",
    )

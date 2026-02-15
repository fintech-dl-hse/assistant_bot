from context import BotContext
from data.users import _load_users, _save_users
from text_format import _send_with_formatting_fallback

from github_client import user_exists as github_user_exists


def handle_me(ctx: BotContext) -> None:
    if ctx.chat_type != "private":
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text="Команда доступна только в личных сообщениях с ботом.",
        )
        return

    fio = (ctx.args or "").strip()
    if not fio:
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text="Usage: /me <ФИО>",
        )
        return

    users_data = _load_users(ctx.users_file)
    users = users_data.get("users")
    if not isinstance(users, dict):
        users = {}
        users_data["users"] = users

    user_key = str(ctx.user_id)
    if user_key not in users:
        users[user_key] = {}
    users[user_key]["fio"] = fio
    users[user_key]["username"] = ctx.username

    try:
        _save_users(ctx.users_file, users_data)
    except Exception as e:
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text=f"Не удалось сохранить данные: {type(e).__name__}: {e}",
        )
        return

    _send_with_formatting_fallback(
        tg=ctx.tg,
        chat_id=ctx.chat_id,
        message_thread_id=ctx.message_thread_id,
        text=f"Готово. Сохранено ФИО: {fio}\nUsername: @{ctx.username}" if ctx.username else f"Готово. Сохранено ФИО: {fio}",
    )


def handle_github(ctx: BotContext) -> None:
    if ctx.chat_type != "private":
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text="Команда доступна только в личных сообщениях с ботом.",
        )
        return

    github_nick = (ctx.args or "").strip().lstrip("@")
    users_data = _load_users(ctx.users_file)
    users = users_data.get("users")
    if not isinstance(users, dict):
        users = {}
        users_data["users"] = users

    user_key = str(ctx.user_id)
    if user_key not in users:
        users[user_key] = {}

    if not github_nick:
        linked = str(users[user_key].get("github") or "").strip()
        if linked:
            _send_with_formatting_fallback(
                tg=ctx.tg,
                chat_id=ctx.chat_id,
                message_thread_id=ctx.message_thread_id,
                text=f"Привязанный GitHub: https://github.com/{linked}",
            )
        else:
            _send_with_formatting_fallback(
                tg=ctx.tg,
                chat_id=ctx.chat_id,
                message_thread_id=ctx.message_thread_id,
                text="GitHub не привязан. Используйте: /github <nickname>",
            )
        return

    if not github_user_exists(github_nick):
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text=f"Пользователь GitHub с ником '{github_nick}' не найден. Проверьте правильность написания.",
        )
        return

    users[user_key]["github"] = github_nick
    users[user_key]["github_changes"] = int(users[user_key].get("github_changes") or 0) + 1
    users[user_key]["fio"] = str(users[user_key].get("fio") or "").strip()
    users[user_key]["username"] = str(users[user_key].get("username") or ctx.username).strip()

    try:
        _save_users(ctx.users_file, users_data)
    except Exception as e:
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text=f"Не удалось сохранить данные: {type(e).__name__}: {e}",
        )
        return

    _send_with_formatting_fallback(
        tg=ctx.tg,
        chat_id=ctx.chat_id,
        message_thread_id=ctx.message_thread_id,
        text=f"Готово. GitHub привязан: https://github.com/{github_nick}",
    )

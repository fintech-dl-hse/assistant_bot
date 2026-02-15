import json
import logging
from pathlib import Path
from typing import Any, Dict

from context import BotContext
from config import _save_settings
from backup import _create_backup
from logging_utils import _tokens_stat_from_log
from text_format import _send_with_formatting_fallback


def handle_tokens_stat(ctx: BotContext) -> None:
    if not ctx.is_admin:
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text="Недостаточно прав: команда доступна только администраторам.",
        )
        return
    if ctx.chat_type != "private":
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text="Пожалуйста, используйте /tokens_stat в личных сообщениях с ботом.",
        )
        return

    total, top_users = _tokens_stat_from_log(ctx.pm_log_file)
    lines = [f"Всего токенов потрачено: {total}"]
    if not top_users:
        lines.append("Топ пользователей: нет данных.")
    else:
        lines.append("Топ 5 пользователей по токенам:")
        for i, (uid, uname, t) in enumerate(top_users, start=1):
            who = f"@{uname}" if uname else f"id={uid}"
            lines.append(f"{i}. {who}: {t}")

    _send_with_formatting_fallback(
        tg=ctx.tg,
        chat_id=ctx.chat_id,
        message_thread_id=ctx.message_thread_id,
        text="\n".join(lines),
    )


def handle_add_admin(ctx: BotContext) -> None:
    if not ctx.is_admin:
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text="Недостаточно прав: команда доступна только администраторам.",
        )
        return

    raw_user_id = (ctx.args or "").strip()
    if not raw_user_id:
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text="Usage: /add_admin <user_id>",
        )
        return

    try:
        new_admin_id = int(raw_user_id)
    except ValueError:
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text="Usage: /add_admin <user_id> (user_id должен быть числом)",
        )
        return

    admin_users = ctx.settings.get("admin_users") or []
    if not isinstance(admin_users, list):
        admin_users = []

    already = False
    for entry in admin_users:
        if isinstance(entry, int) and entry == new_admin_id:
            already = True
            break
        if isinstance(entry, str) and entry.strip().isdigit() and int(entry.strip()) == new_admin_id:
            already = True
            break

    if already:
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text=f"Пользователь {new_admin_id} уже является администратором.",
        )
        return

    admin_users.append(new_admin_id)
    ctx.settings["admin_users"] = admin_users
    try:
        _save_settings(config_path=ctx.config_path, settings=ctx.settings)
    except Exception as e:
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text=f"Не удалось сохранить конфиг: {type(e).__name__}: {e}",
        )
        return

    _send_with_formatting_fallback(
        tg=ctx.tg,
        chat_id=ctx.chat_id,
        message_thread_id=ctx.message_thread_id,
        text=f"Готово. Добавил администратора: {new_admin_id}",
    )


def handle_course_chat(ctx: BotContext) -> None:
    if not ctx.is_admin:
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text="Недостаточно прав: команда доступна только администраторам.",
        )
        return

    raw_chat_id = (ctx.args or "").strip()
    if not raw_chat_id:
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text="Usage: /course_chat <chat_id>",
        )
        return

    try:
        course_chat_id = int(raw_chat_id)
    except ValueError:
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text="Usage: /course_chat <chat_id> (chat_id должен быть числом)",
        )
        return

    if ctx.bot_user_id <= 0:
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text="Не удалось определить bot_id через Telegram API. Попробуйте перезапустить бота.",
        )
        return

    try:
        member = ctx.tg.get_chat_member(chat_id=course_chat_id, user_id=ctx.bot_user_id)
        status = str((member.get("result") or {}).get("status") or "")
    except Exception as e:
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text=f"Не удалось проверить права бота в чате: {type(e).__name__}: {e}",
        )
        return

    if status not in {"administrator", "creator"}:
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text=(
                "Бот должен быть администратором (суперпользователем) в этом чате.\n"
                f"Текущий статус: {status or 'unknown'}"
            ),
        )
        return

    ctx.settings["course_chat_id"] = course_chat_id
    try:
        _save_settings(config_path=ctx.config_path, settings=ctx.settings)
    except Exception as e:
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text=f"Не удалось сохранить конфиг: {type(e).__name__}: {e}",
        )
        return

    _send_with_formatting_fallback(
        tg=ctx.tg,
        chat_id=ctx.chat_id,
        message_thread_id=ctx.message_thread_id,
        text=f"Готово. Установил чат курса: {course_chat_id}",
    )


def handle_set_backup_chat_id(ctx: BotContext) -> None:
    if not ctx.is_admin:
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text="Недостаточно прав: команда доступна только администраторам.",
        )
        return

    raw_chat_id = (ctx.args or "").strip()
    if not raw_chat_id:
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text="Usage: /set_backup_chat_id <chat_id>",
        )
        return

    try:
        backup_chat_id = int(raw_chat_id)
    except ValueError:
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text="Usage: /set_backup_chat_id <chat_id> (chat_id должен быть числом)",
        )
        return

    if ctx.bot_user_id <= 0:
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text="Не удалось определить bot_id через Telegram API. Попробуйте перезапустить бота.",
        )
        return

    try:
        member = ctx.tg.get_chat_member(chat_id=backup_chat_id, user_id=ctx.bot_user_id)
        status = str((member.get("result") or {}).get("status") or "")
    except Exception as e:
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text=f"Не удалось проверить права бота в чате: {type(e).__name__}: {e}",
        )
        return

    if status not in {"administrator", "creator", "member"}:
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text=(
                "Бот должен быть участником чата.\n"
                f"Текущий статус: {status or 'unknown'}"
            ),
        )
        return

    ctx.settings["backup_chat_id"] = backup_chat_id
    try:
        _save_settings(config_path=ctx.config_path, settings=ctx.settings)
    except Exception as e:
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text=f"Не удалось сохранить конфиг: {type(e).__name__}: {e}",
        )
        return

    _send_with_formatting_fallback(
        tg=ctx.tg,
        chat_id=ctx.chat_id,
        message_thread_id=ctx.message_thread_id,
        text=f"Готово. Установил чат для бэкапов: {backup_chat_id}",
    )


def handle_backup(ctx: BotContext) -> None:
    if not ctx.is_admin:
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text="Недостаточно прав: команда доступна только администраторам.",
        )
        return

    backup_chat_id = ctx.settings.get("backup_chat_id")
    if not isinstance(backup_chat_id, int) or backup_chat_id == 0:
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text="Чат для бэкапов не настроен. Сначала выполните: /set_backup_chat_id <chat_id>",
        )
        return

    _send_with_formatting_fallback(
        tg=ctx.tg,
        chat_id=ctx.chat_id,
        message_thread_id=ctx.message_thread_id,
        text="Начинаю создание бэкапа...",
    )

    success = _create_backup(
        tg=ctx.tg,
        config_path=ctx.config_path,
        pm_log_file=ctx.pm_log_file,
        quizzes_file=ctx.quizzes_file,
        quiz_state_file=ctx.quiz_state_file,
        users_file=ctx.users_file,
        backup_chat_id=backup_chat_id,
    )

    if success:
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text="Бэкап успешно создан и отправлен в настроенный чат.",
        )
    else:
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text="Ошибка при создании бэкапа. Проверьте логи для подробностей.",
        )


def handle_course_members(ctx: BotContext) -> None:
    if not ctx.is_admin:
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text="Недостаточно прав: команда доступна только администраторам.",
        )
        return

    course_chat_id = ctx.settings.get("course_chat_id")
    if not isinstance(course_chat_id, int) or course_chat_id == 0:
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text="Чат курса не настроен. Сначала выполните: /course_chat <chat_id>",
        )
        return

    path = Path(ctx.pm_log_file)
    if not path.exists():
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text="Файл логов не найден. Пользователей: 0",
        )
        return

    users: set[int] = set()
    total_lines = 0
    bad_lines = 0
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                total_lines += 1
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    uid = int((rec or {}).get("user_id") or 0)
                    if uid > 0:
                        users.add(uid)
                except Exception:
                    bad_lines += 1
    except Exception as e:
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text=f"Не удалось прочитать файл логов: {type(e).__name__}: {e}",
        )
        return

    in_course_users: set[int] = set()
    checked = 0
    check_errors = 0
    for uid in users:
        checked += 1
        try:
            member = ctx.tg.get_chat_member(chat_id=course_chat_id, user_id=uid)
            status = str((member.get("result") or {}).get("status") or "")
            if status in {"creator", "administrator", "member", "restricted"}:
                in_course_users.add(uid)
        except Exception:
            check_errors += 1

    _send_with_formatting_fallback(
        tg=ctx.tg,
        chat_id=ctx.chat_id,
        message_thread_id=ctx.message_thread_id,
        text=(
            "Статистика по личным сообщениям:\n"
            f"- пользователей (всего в логе): {len(users)}\n"
            f"- пользователей (в чате курса): {len(in_course_users)}\n"
            f"- строк в логе: {total_lines}\n"
            f"- битых строк: {bad_lines}\n"
            f"- проверено membership: {checked}\n"
            f"- ошибок проверки membership: {check_errors}"
        ),
    )

import csv
import io
import logging
import random
from typing import Dict

from context import BotContext
from data.quiz import _is_hidden_quiz, _get_user_quiz_state, _load_quiz_state, _load_quizzes
from data.users import _load_users, _save_users
from text_format import _escape_markdown_v2_plain as _escape_md2, _send_with_formatting_fallback

_log = logging.getLogger(__name__)

_MODULE_NAME_GENITIVE = {3: "третьего", 4: "четвертого"}


def _exam_field(module: int) -> str:
    return f"exam_{module}"


def _module_name(module: int) -> str:
    return _MODULE_NAME_GENITIVE.get(module, f"{module}-го")


def _all_quizzes_completed(quizzes_file: str, quiz_state_file: str, user_id: int) -> bool:
    quizzes = _load_quizzes(quizzes_file)
    quizzes = [q for q in quizzes if not _is_hidden_quiz(q)]
    if not quizzes:
        return False

    state = _load_quiz_state(quiz_state_file)
    user_state = _get_user_quiz_state(state, user_id)
    results = user_state.get("results") or {}

    for q in quizzes:
        qid = str(q.get("id") or "").strip()
        if not qid:
            continue
        r = results.get(qid)
        if not isinstance(r, dict) or not bool(r.get("correct")):
            return False
    return True


def _handle_exam_register(ctx: BotContext, module: int) -> None:
    if ctx.chat_type != "private":
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text="Команда доступна только в личных сообщениях с ботом.",
        )
        return

    field = _exam_field(module)
    module_name = _module_name(module)
    cmd = f"/exam_{module}"

    users_data = _load_users(ctx.users_file)
    users = users_data.get("users")
    if not isinstance(users, dict):
        users = {}
        users_data["users"] = users

    user_key = str(ctx.user_id)
    user_record = users.get(user_key)

    # Check that the user has set their name via /me
    fio = ""
    if isinstance(user_record, dict):
        fio = str(user_record.get("fio") or "").strip()
    if not fio:
        msg = (
            _escape_md2("Для регистрации на экзамен необходимо указать ФИО. ")
            + _escape_md2("Используйте команду /me <ФИО>.\n\n")
            + "*"
            + _escape_md2(f"После указания ФИО повторно выполните {cmd}")
            + "*"
        )
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text=msg,
            markdown_v2_raw=True,
        )
        return

    # Check that all quizzes are completed
    if not _all_quizzes_completed(ctx.quizzes_file, ctx.quiz_state_file, ctx.user_id):
        msg = (
            _escape_md2("Для регистрации на экзамен необходимо выполнить все квизы. ")
            + _escape_md2("Используйте /quiz для прохождения квизов.\n\n")
            + "*"
            + _escape_md2(f"После выполнения всех квизов повторно выполните {cmd}")
            + "*"
        )
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text=msg,
            markdown_v2_raw=True,
        )
        return

    # Check if already registered
    if isinstance(user_record, dict) and user_record.get(field):
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text=f"Вы уже зарегистрированы на экзамен {module_name} модуля.",
        )
        return

    # Register
    if user_key not in users:
        users[user_key] = {}
    users[user_key][field] = True
    users[user_key].setdefault("fio", fio)
    users[user_key].setdefault("username", ctx.username)

    try:
        _save_users(ctx.users_file, users_data)
    except Exception as e:
        _log.warning("Failed to save users file %s: %s", ctx.users_file, e, exc_info=True)
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
        text=f"Вы успешно зарегистрированы на экзамен {module_name} модуля.\nФИО: {fio}",
    )


def _handle_exam_cancel(ctx: BotContext, module: int) -> None:
    if ctx.chat_type != "private":
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text="Команда доступна только в личных сообщениях с ботом.",
        )
        return

    field = _exam_field(module)
    module_name = _module_name(module)

    users_data = _load_users(ctx.users_file)
    users = users_data.get("users")
    if not isinstance(users, dict):
        users = {}
        users_data["users"] = users

    user_key = str(ctx.user_id)
    user_record = users.get(user_key)

    if not isinstance(user_record, dict) or not user_record.get(field):
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text=f"Вы не зарегистрированы на экзамен {module_name} модуля.",
        )
        return

    users[user_key][field] = False

    try:
        _save_users(ctx.users_file, users_data)
    except Exception as e:
        _log.warning("Failed to save users file %s: %s", ctx.users_file, e, exc_info=True)
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
        text=f"Регистрация на экзамен {module_name} модуля отменена.",
    )


def _handle_exam_stat(ctx: BotContext, module: int) -> None:
    if not ctx.is_admin:
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text="Недостаточно прав: команда доступна только администраторам.",
        )
        return

    field = _exam_field(module)
    module_name = _module_name(module)

    users_data = _load_users(ctx.users_file)
    users = users_data.get("users") or {}

    registered: list[Dict[str, str]] = []
    for user_key, u in users.items():
        if not isinstance(u, dict):
            continue
        if not u.get(field):
            continue
        fio = str(u.get("fio") or "").strip()
        username = str(u.get("username") or "").strip()
        registered.append({"fio": fio, "telegram_nick": f"@{username}" if username else ""})

    count = len(registered)
    _send_with_formatting_fallback(
        tg=ctx.tg,
        chat_id=ctx.chat_id,
        message_thread_id=ctx.message_thread_id,
        text=f"Зарегистрировано на экзамен {module_name} модуля: {count}",
    )

    if not registered:
        return

    # Build CSV in memory
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["ФИО", "telegram_nick"])
    for row in registered:
        writer.writerow([row["fio"], row["telegram_nick"]])

    csv_bytes = buf.getvalue().encode("utf-8")
    file_obj = io.BytesIO(csv_bytes)

    try:
        ctx.tg._request(
            method="POST",
            endpoint="sendDocument",
            data={
                "chat_id": ctx.chat_id,
                "message_thread_id": ctx.message_thread_id,
                "caption": f"Список зарегистрированных на экзамен {module} модуля ({count} чел.)",
            },
            files={"document": (f"exam_{module}_registered.csv", file_obj, "text/csv")},
            timeout=15,
        )
    except Exception as e:
        _log.warning("Failed to send exam_%d CSV: %s", module, e, exc_info=True)
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text=f"Не удалось отправить CSV файл: {type(e).__name__}: {e}",
        )
        return

    # Build schedule CSV: random distribution across teachers and 10-min slots
    teachers = ["Тарасов Дмитрий", "Денис Деркач"]
    shuffled = list(registered)
    random.shuffle(shuffled)

    students_per_slot = len(teachers)  # one student per teacher per slot
    slots: list[str] = []
    start_hour, start_min = 18, 10
    for i in range(0, len(shuffled), students_per_slot):
        slot_index = i // students_per_slot
        total_minutes = start_hour * 60 + start_min + slot_index * 10
        h, m = divmod(total_minutes, 60)
        slots.extend([f"{h:02d}:{m:02d}"] * students_per_slot)

    schedule_buf = io.StringIO()
    schedule_writer = csv.writer(schedule_buf)
    schedule_writer.writerow(["Время", "Преподаватель", "ФИО", "telegram_nick"])
    for idx, student in enumerate(shuffled):
        teacher = teachers[idx % len(teachers)]
        time_slot = slots[idx]
        schedule_writer.writerow([time_slot, teacher, student["fio"], student["telegram_nick"]])

    schedule_bytes = schedule_buf.getvalue().encode("utf-8")
    schedule_file = io.BytesIO(schedule_bytes)

    try:
        ctx.tg._request(
            method="POST",
            endpoint="sendDocument",
            data={
                "chat_id": ctx.chat_id,
                "message_thread_id": ctx.message_thread_id,
                "caption": f"Расписание экзамена {module} модуля ({count} чел.)",
            },
            files={"document": (f"exam_{module}_schedule.csv", schedule_file, "text/csv")},
            timeout=15,
        )
    except Exception as e:
        _log.warning("Failed to send exam_%d schedule CSV: %s", module, e, exc_info=True)
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text=f"Не удалось отправить CSV с расписанием: {type(e).__name__}: {e}",
        )


def handle_exam_3(ctx: BotContext) -> None:
    _handle_exam_register(ctx, 3)


def handle_exam_3_cancel(ctx: BotContext) -> None:
    _handle_exam_cancel(ctx, 3)


def handle_exam_3_stat(ctx: BotContext) -> None:
    _handle_exam_stat(ctx, 3)


def handle_exam_4(ctx: BotContext) -> None:
    _handle_exam_register(ctx, 4)


def handle_exam_4_cancel(ctx: BotContext) -> None:
    _handle_exam_cancel(ctx, 4)


def handle_exam_4_stat(ctx: BotContext) -> None:
    _handle_exam_stat(ctx, 4)

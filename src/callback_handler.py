import json
import logging
from typing import Any, Dict

from telegram_client import TelegramClient
from config import _load_settings
from command_utils import _is_admin
from data.quiz import (
    _QUIZ_WIZARD_STATE,
    _is_hidden_quiz,
    _load_quizzes,
    _save_quizzes,
    _load_quiz_state,
    _save_quiz_state,
    _get_user_quiz_state,
)
from text_format import _send_with_formatting_fallback


def _handle_callback_query(
    tg: TelegramClient,
    callback_query: Dict[str, Any],
    config_path: str,
    pm_log_file: str,
    quizzes_file: str,
    quiz_state_file: str,
) -> None:
    settings = _load_settings(config_path)
    sender = callback_query.get("from") or {}
    user_id = int((sender.get("id") or 0) if isinstance(sender, dict) else 0)
    username = str((sender.get("username") or "") if isinstance(sender, dict) else "").strip()
    is_admin = _is_admin(settings=settings, user_id=user_id, username=username)

    callback_query_id = str(callback_query.get("id") or "")
    data = str(callback_query.get("data") or "")

    if not is_admin:
        try:
            tg.answer_callback_query(
                callback_query_id=callback_query_id,
                text="Недостаточно прав.",
                show_alert=True,
            )
        except Exception:
            logging.getLogger(__name__).debug("Failed to answer callback_query", exc_info=True)
        return

    action = ""
    quiz_id = ""
    if data.startswith("quiz_send_all:"):
        action = "send_all"
        quiz_id = data.split(":", 1)[1].strip()
    elif data.startswith("quiz_send_admins:"):
        action = "send_admins"
        quiz_id = data.split(":", 1)[1].strip()
    elif data.startswith("quiz_toggle_hidden:"):
        action = "toggle_hidden"
        quiz_id = data.split(":", 1)[1].strip()
    elif data.startswith("quiz_edit:"):
        action = "edit"
        quiz_id = data.split(":", 1)[1].strip()
    else:
        try:
            tg.answer_callback_query(callback_query_id=callback_query_id, text="Неизвестная кнопка.")
        except Exception:
            logging.getLogger(__name__).debug("Failed to answer callback_query", exc_info=True)
        return

    if not quiz_id:
        try:
            tg.answer_callback_query(callback_query_id=callback_query_id, text="Некорректный quiz_id.")
        except Exception:
            logging.getLogger(__name__).debug("Failed to answer callback_query", exc_info=True)
        return

    quizzes = _load_quizzes(quizzes_file)
    quiz: Dict[str, Any] | None = None
    for q in quizzes:
        if str(q.get("id") or "") == quiz_id:
            quiz = q
            break

    if quiz is None:
        try:
            tg.answer_callback_query(callback_query_id=callback_query_id, text="Квиз не найден.", show_alert=True)
        except Exception:
            logging.getLogger(__name__).debug("Failed to answer callback_query", exc_info=True)
        return

    if action == "edit":
        _QUIZ_WIZARD_STATE[user_id] = {"stage": "await_question", "quiz_id": quiz_id, "mode": "edit"}
        try:
            tg.answer_callback_query(callback_query_id=callback_query_id, text="Редактирование запущено.")
        except Exception:
            logging.getLogger(__name__).debug("Failed to answer callback_query", exc_info=True)

        msg = callback_query.get("message") or {}
        if isinstance(msg, dict):
            cb_chat_id = int((msg.get("chat") or {}).get("id") or 0)
            cb_message_thread_id = int(msg.get("message_thread_id") or 0)
            _send_with_formatting_fallback(
                tg=tg,
                chat_id=cb_chat_id,
                message_thread_id=cb_message_thread_id,
                text=f"Редактирование квиза {quiz_id}. Отправьте новый вопрос для квиза.",
            )
        return

    if action == "toggle_hidden":
        quiz["hidden"] = not _is_hidden_quiz(quiz)
        try:
            _save_quizzes(quizzes_file=quizzes_file, quizzes=quizzes)
        except Exception:
            logging.getLogger(__name__).warning("Failed to save quizzes file %s", quizzes_file, exc_info=True)
            try:
                tg.answer_callback_query(
                    callback_query_id=callback_query_id,
                    text="Не удалось сохранить hidden в quizzes.json",
                    show_alert=True,
                )
            except Exception:
                logging.getLogger(__name__).debug("Failed to answer callback_query", exc_info=True)
            return

        hidden_now = _is_hidden_quiz(quiz)
        try:
            tg.answer_callback_query(
                callback_query_id=callback_query_id,
                text=f"hidden: {str(hidden_now).lower()}",
            )
        except Exception:
            logging.getLogger(__name__).debug("Failed to answer callback_query", exc_info=True)

        msg = callback_query.get("message") or {}
        if isinstance(msg, dict):
            cb_chat_id = int((msg.get("chat") or {}).get("id") or 0)
            cb_message_id = int(msg.get("message_id") or 0)
            qid = str(quiz.get("id") or "").strip()
            question = str(quiz.get("question") or "").strip()
            answer = str(quiz.get("answer") or "").strip()
            processed = bool(quiz.get("processed"))
            new_text = (
                f"Квиз: {qid}\n"
                f"processed: {str(processed).lower()}\n"
                f"hidden: {str(hidden_now).lower()}\n"
                f"Вопрос: {question}\n"
                f"Ответ: {answer}"
            )

            toggle_text = "Показать (hidden=false)" if hidden_now else "Скрыть (hidden=true)"
            buttons: list[list[Dict[str, str]]] = [
                [{"text": toggle_text, "callback_data": f"quiz_toggle_hidden:{qid}"}],
                [{"text": "Редактировать", "callback_data": f"quiz_edit:{qid}"}],
            ]
            if not hidden_now:
                buttons.append([{"text": "Отправить администраторам", "callback_data": f"quiz_send_admins:{qid}"}])

            try:
                tg.edit_message_text(
                    chat_id=cb_chat_id,
                    message_id=cb_message_id,
                    text=new_text,
                    parse_mode=None,
                )
            except Exception:
                logging.getLogger(__name__).debug("Failed to edit message text", exc_info=True)
            try:
                tg.edit_message_reply_markup(
                    chat_id=cb_chat_id,
                    message_id=cb_message_id,
                    reply_markup={"inline_keyboard": buttons},
                )
            except Exception:
                logging.getLogger(__name__).debug("Failed to edit reply markup", exc_info=True)
        return

    if _is_hidden_quiz(quiz):
        try:
            tg.answer_callback_query(
                callback_query_id=callback_query_id,
                text="Квиз скрыт (hidden). Его нельзя отправлять пользователям.",
                show_alert=True,
            )
        except Exception:
            logging.getLogger(__name__).debug("Failed to answer callback_query", exc_info=True)
        return

    if action == "send_all" and bool(quiz.get("processed")):
        try:
            tg.answer_callback_query(callback_query_id=callback_query_id, text="Квиз уже помечен как processed.")
        except Exception:
            logging.getLogger(__name__).debug("Failed to answer callback_query", exc_info=True)
        return

    try:
        tg.answer_callback_query(callback_query_id=callback_query_id, text="Начинаю отправку...")
    except Exception:
        logging.getLogger(__name__).debug("Failed to answer callback_query", exc_info=True)

    question = str(quiz.get("question") or "").strip()
    sent_ok = 0
    sent_fail = 0
    total_targets = 0

    if action == "send_admins":
        admin_users = settings.get("admin_users") or []
        admin_ids: set[int] = set()
        if isinstance(admin_users, list):
            for entry in admin_users:
                if isinstance(entry, int) and entry > 0:
                    admin_ids.add(entry)
                elif isinstance(entry, str) and entry.strip().isdigit():
                    admin_ids.add(int(entry.strip()))
        targets = sorted(admin_ids)
        total_targets = len(targets)
        state = _load_quiz_state(quiz_state_file)
        sent_admin_users: list[int] = []
        for uid in targets:
            try:
                ok = _send_with_formatting_fallback(
                    tg=tg,
                    chat_id=uid,
                    message_thread_id=0,
                    text=question,
                )
                if ok:
                    sent_ok += 1
                    sent_admin_users.append(uid)
                else:
                    sent_fail += 1
            except Exception:
                sent_fail += 1
        for uid in sent_admin_users:
            u = _get_user_quiz_state(state, uid)
            u["active_quiz_id"] = str(quiz_id)
        try:
            _save_quiz_state(quiz_state_file, state)
        except Exception:
            logging.getLogger(__name__).warning("Failed to save quiz state file %s", quiz_state_file, exc_info=True)
    else:
        course_chat_id = settings.get("course_chat_id")
        if not isinstance(course_chat_id, int) or course_chat_id == 0:
            try:
                tg.answer_callback_query(
                    callback_query_id=callback_query_id,
                    text="Чат курса не настроен. Сначала: /course_chat <chat_id>",
                    show_alert=True,
                )
            except Exception:
                logging.getLogger(__name__).debug("Failed to answer callback_query", exc_info=True)
            return

        from pathlib import Path as _Path
        path = _Path(pm_log_file)
        users: set[int] = set()
        if path.exists():
            try:
                with path.open("r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            rec = json.loads(line)
                            uid = int((rec or {}).get("user_id") or 0)
                            if uid > 0:
                                users.add(uid)
                        except Exception:
                            continue
            except Exception:
                logging.getLogger(__name__).warning("Failed to read pm log file %s", pm_log_file, exc_info=True)

        in_course_users: list[int] = []
        for uid in sorted(users):
            try:
                member = tg.get_chat_member(chat_id=course_chat_id, user_id=uid)
                status = str((member.get("result") or {}).get("status") or "")
                if status in {"creator", "administrator", "member", "restricted"}:
                    in_course_users.append(uid)
            except Exception:
                continue

        total_targets = len(in_course_users)
        state = _load_quiz_state(quiz_state_file)
        sent_users: list[int] = []
        for uid in in_course_users:
            try:
                ok = _send_with_formatting_fallback(
                    tg=tg,
                    chat_id=uid,
                    message_thread_id=0,
                    text=question,
                )
                if ok:
                    sent_ok += 1
                    sent_users.append(uid)
                else:
                    sent_fail += 1
            except Exception:
                sent_fail += 1

        processed_now = sent_fail == 0
        quiz["processed"] = processed_now
        try:
            _save_quizzes(quizzes_file=quizzes_file, quizzes=quizzes)
        except Exception:
            logging.getLogger(__name__).warning("Failed to save quizzes file %s", quizzes_file, exc_info=True)
        for uid in sent_users:
            u = _get_user_quiz_state(state, uid)
            u["active_quiz_id"] = str(quiz_id)
        try:
            _save_quiz_state(quiz_state_file, state)
        except Exception:
            logging.getLogger(__name__).warning("Failed to save quiz state file %s", quiz_state_file, exc_info=True)

    msg = callback_query.get("message") or {}
    if isinstance(msg, dict):
        cb_chat_id = int((msg.get("chat") or {}).get("id") or 0)
        cb_message_id = int(msg.get("message_id") or 0)
        prev_text = str(msg.get("text") or "").strip()
        status_line = ""
        if action == "send_admins":
            status_line = f"Отправлено администраторам: {sent_ok}/{total_targets}\nОшибок: {sent_fail}"
        else:
            status_line = (
                f"Отправлено: {sent_ok}/{total_targets}\n"
                f"Ошибок: {sent_fail}\n"
                f"processed: {str(bool(quiz.get('processed'))).lower()}"
            )
        new_text = f"{prev_text}\n\n{status_line}".strip()
        try:
            tg.edit_message_text(chat_id=cb_chat_id, message_id=cb_message_id, text=new_text, parse_mode=None)
        except Exception:
            logging.getLogger(__name__).debug("Failed to edit message text", exc_info=True)
        if action == "send_all":
            try:
                tg.edit_message_reply_markup(
                    chat_id=cb_chat_id,
                    message_id=cb_message_id,
                    reply_markup={"inline_keyboard": []},
                )
            except Exception:
                logging.getLogger(__name__).debug("Failed to edit reply markup", exc_info=True)

import logging
import math
from typing import Any, Dict

from context import BotContext
from constants import OPENAI_MODEL
from data.quiz import (
    _QUIZ_WIZARD_STATE,
    _append_user_answer,
    _get_user_quiz_state,
    _is_hidden_quiz,
    _load_quiz_state,
    _load_quizzes,
    _save_quiz_state,
    _save_quizzes,
)
from llm import _judge_quiz_answer
from logging_utils import _log_token_usage
from text_format import _send_with_formatting_fallback


def handle_quiz_wizard(ctx: BotContext) -> None:
    """Handle quiz creation/edit wizard (non-command messages from admin in private)."""
    state = _QUIZ_WIZARD_STATE.get(ctx.user_id) or {}
    stage = str(state.get("stage") or "")
    quiz_id = str(state.get("quiz_id") or "").strip()
    mode = str(state.get("mode") or "create")
    text = (ctx.message.get("text") or "").strip()

    if stage == "await_question":
        question = text.strip()
        if not question:
            _send_with_formatting_fallback(
                tg=ctx.tg,
                chat_id=ctx.chat_id,
                message_thread_id=ctx.message_thread_id,
                text="Пожалуйста, отправьте непустой вопрос для квиза.",
            )
            return
        state["question"] = question
        state["stage"] = "await_answer"
        _QUIZ_WIZARD_STATE[ctx.user_id] = state
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text=f"Квиз {quiz_id}: теперь отправьте правильный ответ.",
        )
        return
    if stage == "await_answer":
        answer = text.strip()
        if not answer:
            _send_with_formatting_fallback(
                tg=ctx.tg,
                chat_id=ctx.chat_id,
                message_thread_id=ctx.message_thread_id,
                text="Пожалуйста, отправьте непустой правильный ответ для квиза.",
            )
            return

        question = str(state.get("question") or "").strip()

        quizzes = _load_quizzes(ctx.quizzes_file)
        if mode == "edit":
            target = None
            for q in quizzes:
                if str(q.get("id") or "") == quiz_id:
                    target = q
                    break
            if target is None:
                _QUIZ_WIZARD_STATE.pop(ctx.user_id, None)
                _send_with_formatting_fallback(
                    tg=ctx.tg,
                    chat_id=ctx.chat_id,
                    message_thread_id=ctx.message_thread_id,
                    text=f"Квиз с id={quiz_id} не найден. Редактирование отменено.",
                )
                return
            target["question"] = question
            target["answer"] = answer
            try:
                _save_quizzes(quizzes_file=ctx.quizzes_file, quizzes=quizzes)
            except Exception as e:
                _send_with_formatting_fallback(
                    tg=ctx.tg,
                    chat_id=ctx.chat_id,
                    message_thread_id=ctx.message_thread_id,
                    text=f"Не удалось сохранить квиз: {type(e).__name__}: {e}",
                )
                return
            _QUIZ_WIZARD_STATE.pop(ctx.user_id, None)
            _send_with_formatting_fallback(
                tg=ctx.tg,
                chat_id=ctx.chat_id,
                message_thread_id=ctx.message_thread_id,
                text=f"Готово. Квиз {quiz_id} обновлён.",
            )
            return

        quiz = {"id": quiz_id, "question": question, "answer": answer, "processed": False}
        if any(str(q.get("id") or "") == quiz_id for q in quizzes):
            _QUIZ_WIZARD_STATE.pop(ctx.user_id, None)
            _send_with_formatting_fallback(
                tg=ctx.tg,
                chat_id=ctx.chat_id,
                message_thread_id=ctx.message_thread_id,
                text=f"Квиз с id={quiz_id} уже существует. Создание отменено.",
            )
            return

        quizzes.append(quiz)
        try:
            _save_quizzes(quizzes_file=ctx.quizzes_file, quizzes=quizzes)
        except Exception as e:
            _send_with_formatting_fallback(
                tg=ctx.tg,
                chat_id=ctx.chat_id,
                message_thread_id=ctx.message_thread_id,
                text=f"Не удалось сохранить квиз: {type(e).__name__}: {e}",
            )
            return
        _QUIZ_WIZARD_STATE.pop(ctx.user_id, None)
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text=f"Готово. Квиз {quiz_id} сохранён.",
        )
        return


def handle_quiz_answer(ctx: BotContext) -> None:
    """Handle user answer processing (non-command private messages)."""
    text = (ctx.message.get("text") or "").strip()
    state = _load_quiz_state(ctx.quiz_state_file)
    user_state = _get_user_quiz_state(state, ctx.user_id)
    active_quiz_id = user_state.get("active_quiz_id")
    if active_quiz_id is None or str(active_quiz_id).strip() == "":
        return
    active_quiz_id = str(active_quiz_id).strip()

    quizzes = _load_quizzes(ctx.quizzes_file)
    quiz: Dict[str, Any] | None = None
    for q in quizzes:
        if str(q.get("id") or "").strip() == active_quiz_id:
            quiz = q
            break
    if quiz is None:
        user_state["active_quiz_id"] = None
        try:
            _save_quiz_state(ctx.quiz_state_file, state)
        except Exception:
            logging.getLogger(__name__).warning("Failed to save quiz state file %s", ctx.quiz_state_file, exc_info=True)
        return
    if _is_hidden_quiz(quiz) and not ctx.is_admin:
        user_state["active_quiz_id"] = None
        try:
            _save_quiz_state(ctx.quiz_state_file, state)
        except Exception:
            logging.getLogger(__name__).warning("Failed to save quiz state file %s", ctx.quiz_state_file, exc_info=True)
        return

    correct_answer = str(quiz.get("answer") or "").strip()
    user_answer = text.strip()
    qkey = str(active_quiz_id)
    results = user_state.get("results")
    if not isinstance(results, dict):
        results = {}
        user_state["results"] = results
    prev = results.get(qkey)
    prev_attempts = int((prev or {}).get("attempts") or 0) if isinstance(prev, dict) else 0
    attempts_now = prev_attempts + 1

    is_correct, usage = _judge_quiz_answer(
        llm=ctx.llm,
        quiz_question=str(quiz.get("question") or "").strip(),
        reference_answer=correct_answer,
        student_answer=user_answer,
    )
    if int(usage.get("total_tokens") or 0) > 0:
        _log_token_usage(
            message=ctx.message,
            pm_log_file=ctx.pm_log_file,
            request_id=ctx.request_id,
            cmd=ctx.cmd,
            purpose="quiz_judge",
            model=OPENAI_MODEL,
            usage=usage,
        )
    _append_user_answer(user_state=user_state, quiz_id=qkey, answer=user_answer, is_correct=is_correct)

    if not is_correct:
        results[qkey] = {"correct": False, "attempts": attempts_now}
        try:
            _save_quiz_state(ctx.quiz_state_file, state)
        except Exception:
            logging.getLogger(__name__).warning("Failed to save quiz state file %s", ctx.quiz_state_file, exc_info=True)
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text=f"Неправильно. Попыток: {attempts_now}. Попробуйте ещё раз.",
        )
        return

    results[qkey] = {"correct": True, "attempts": attempts_now}
    next_quiz_item: Dict[str, Any] | None = None
    for q in quizzes:
        if _is_hidden_quiz(q):
            continue
        qid = str(q.get("id") or "").strip()
        r = results.get(qid)
        if isinstance(r, dict) and bool(r.get("correct")):
            continue
        next_quiz_item = q
        break

    if next_quiz_item is None:
        user_state["active_quiz_id"] = None
        try:
            _save_quiz_state(ctx.quiz_state_file, state)
        except Exception:
            logging.getLogger(__name__).warning("Failed to save quiz state file %s", ctx.quiz_state_file, exc_info=True)
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text="Правильно! Поздравляю.",
        )
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text="Все квизы уже пройдены. Отличная работа!",
        )
        return

    next_qid = str(next_quiz_item.get("id") or "").strip()
    user_state["active_quiz_id"] = next_qid
    try:
        _save_quiz_state(ctx.quiz_state_file, state)
    except Exception:
        logging.getLogger(__name__).warning("Failed to save quiz state file %s", ctx.quiz_state_file, exc_info=True)
    _send_with_formatting_fallback(
        tg=ctx.tg,
        chat_id=ctx.chat_id,
        message_thread_id=ctx.message_thread_id,
        text="Правильно! Поздравляю.",
    )
    question = str(next_quiz_item.get("question") or "").strip()
    _send_with_formatting_fallback(
        tg=ctx.tg,
        chat_id=ctx.chat_id,
        message_thread_id=ctx.message_thread_id,
        text=f"Квиз {next_qid}.\n\n{question}",
    )


def handle_quiz(ctx: BotContext) -> None:
    if ctx.chat_type != "private":
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text="Команда доступна только в личных сообщениях с ботом.",
        )
        return

    quizzes = _load_quizzes(ctx.quizzes_file)
    quizzes = [q for q in quizzes if not _is_hidden_quiz(q)]
    if not quizzes:
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text="Квизов пока нет.",
        )
        return

    state = _load_quiz_state(ctx.quiz_state_file)
    user_state = _get_user_quiz_state(state, ctx.user_id)
    active_quiz_id = user_state.get("active_quiz_id")
    active_quiz_id = str(active_quiz_id).strip() if active_quiz_id is not None else ""

    # If already in progress, resend question
    if active_quiz_id:
        quiz = next((q for q in quizzes if str(q.get("id") or "").strip() == active_quiz_id), None)
        if isinstance(quiz, dict):
            question = str(quiz.get("question") or "").strip()
            _send_with_formatting_fallback(
                tg=ctx.tg,
                chat_id=ctx.chat_id,
                message_thread_id=ctx.message_thread_id,
                text=f"Квиз {active_quiz_id} уже в процессе.\n\n{question}",
            )
            return
        user_state["active_quiz_id"] = None

    results = user_state.get("results")
    if not isinstance(results, dict):
        results = {}
        user_state["results"] = results

    next_quiz: Dict[str, Any] | None = None
    for q in quizzes:
        qid = str(q.get("id") or "").strip()
        r = results.get(qid)
        if isinstance(r, dict) and bool(r.get("correct")):
            continue
        next_quiz = q
        break

    if next_quiz is None:
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text="Все квизы уже пройдены. Отличная работа!",
        )
        return

    qid = str(next_quiz.get("id") or "").strip()
    user_state["active_quiz_id"] = qid
    try:
        _save_quiz_state(ctx.quiz_state_file, state)
    except Exception:
        logging.getLogger(__name__).warning("Failed to save quiz state file %s", ctx.quiz_state_file, exc_info=True)

    question = str(next_quiz.get("question") or "").strip()
    _send_with_formatting_fallback(
        tg=ctx.tg,
        chat_id=ctx.chat_id,
        message_thread_id=ctx.message_thread_id,
        text=f"Квиз {qid}.\n\n{question}",
    )


def handle_skip(ctx: BotContext) -> None:
    if ctx.chat_type != "private":
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text="Команда доступна только в личных сообщениях с ботом.",
        )
        return

    state = _load_quiz_state(ctx.quiz_state_file)
    user_state = _get_user_quiz_state(state, ctx.user_id)
    active_quiz_id = user_state.get("active_quiz_id")
    if active_quiz_id is None or str(active_quiz_id).strip() == "":
        return
    active_quiz_id = str(active_quiz_id).strip()

    quizzes = _load_quizzes(ctx.quizzes_file)
    quizzes = [q for q in quizzes if not _is_hidden_quiz(q)]
    if not quizzes:
        return

    results = user_state.get("results")
    if not isinstance(results, dict):
        results = {}
        user_state["results"] = results

    next_quiz: Dict[str, Any] | None = None
    for q in quizzes:
        qid = str(q.get("id") or "").strip()
        if not qid or qid == active_quiz_id:
            continue
        r = results.get(qid)
        if isinstance(r, dict) and bool(r.get("correct")):
            continue
        next_quiz = q
        break

    if next_quiz is None:
        for q in quizzes:
            qid = str(q.get("id") or "").strip()
            if not qid:
                continue
            r = results.get(qid)
            if isinstance(r, dict) and bool(r.get("correct")):
                continue
            next_quiz = q
            break

    if next_quiz is None:
        return

    qid = str(next_quiz.get("id") or "").strip()
    user_state["active_quiz_id"] = qid
    try:
        _save_quiz_state(ctx.quiz_state_file, state)
    except Exception:
        logging.getLogger(__name__).warning("Failed to save quiz state file %s", ctx.quiz_state_file, exc_info=True)

    question = str(next_quiz.get("question") or "").strip()
    _send_with_formatting_fallback(
        tg=ctx.tg,
        chat_id=ctx.chat_id,
        message_thread_id=ctx.message_thread_id,
        text=f"Квиз {qid}.\n\n{question}",
    )


def handle_quiz_ask(ctx: BotContext) -> None:
    if ctx.chat_type != "private":
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text="Команда доступна только в личных сообщениях с ботом.",
        )
        return
    if not ctx.is_admin:
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text="Недостаточно прав: команда доступна только администраторам.",
        )
        return

    quiz_id = (ctx.args or "").strip()
    if not quiz_id:
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text="Usage: /quiz_ask <quiz_id>",
        )
        return

    quizzes = _load_quizzes(ctx.quizzes_file)
    quiz = next((q for q in quizzes if str(q.get("id") or "").strip() == quiz_id), None)
    if not isinstance(quiz, dict):
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text=f"Квиз с id={quiz_id} не найден.",
        )
        return

    state = _load_quiz_state(ctx.quiz_state_file)
    user_state = _get_user_quiz_state(state, ctx.user_id)
    user_state["active_quiz_id"] = str(quiz_id)
    try:
        _save_quiz_state(ctx.quiz_state_file, state)
    except Exception:
        logging.getLogger(__name__).warning("Failed to save quiz state file %s", ctx.quiz_state_file, exc_info=True)

    question = str(quiz.get("question") or "").strip()
    _send_with_formatting_fallback(
        tg=ctx.tg,
        chat_id=ctx.chat_id,
        message_thread_id=ctx.message_thread_id,
        text=f"Квиз {quiz_id}.\n\n{question}",
    )


def handle_quiz_create(ctx: BotContext) -> None:
    if ctx.chat_type != "private":
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text="Команда доступна только в личных сообщениях с ботом.",
        )
        return
    if not ctx.is_admin:
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text="Недостаточно прав: команда доступна только администраторам.",
        )
        return

    quiz_id = (ctx.args or "").strip()
    if not quiz_id:
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text="Usage: /quiz_create <quiz_id>",
        )
        return

    quizzes = _load_quizzes(ctx.quizzes_file)
    if any(str(q.get("id") or "") == quiz_id for q in quizzes):
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text=f"Квиз с id={quiz_id} уже существует.",
        )
        return

    _QUIZ_WIZARD_STATE[ctx.user_id] = {"stage": "await_question", "quiz_id": quiz_id, "mode": "create"}
    _send_with_formatting_fallback(
        tg=ctx.tg,
        chat_id=ctx.chat_id,
        message_thread_id=ctx.message_thread_id,
        text=f"Создание квиза {quiz_id}. Отправьте вопрос для квиза.",
    )


def handle_quiz_list(ctx: BotContext) -> None:
    if not ctx.is_admin:
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text="Недостаточно прав: команда доступна только администраторам.",
        )
        return

    quizzes = _load_quizzes(ctx.quizzes_file)
    if not quizzes:
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text="Список квизов пуст.",
        )
        return

    for q in quizzes:
        qid = str(q.get("id") or "").strip()
        question = str(q.get("question") or "").strip()
        answer = str(q.get("answer") or "").strip()
        processed = bool(q.get("processed"))
        hidden = _is_hidden_quiz(q)
        toggle_text = "Показать (hidden=false)" if hidden else "Скрыть (hidden=true)"
        buttons: list[list[Dict[str, str]]] = [
            [{"text": toggle_text, "callback_data": f"quiz_toggle_hidden:{qid}"}],
            [{"text": "Редактировать", "callback_data": f"quiz_edit:{qid}"}],
        ]
        if not hidden:
            buttons.append([{"text": "Отправить администраторам", "callback_data": f"quiz_send_admins:{qid}"}])
        reply_markup = {"inline_keyboard": buttons}
        ctx.tg.send_message(
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            parse_mode=None,
            message=(
                f"Квиз: {qid}\n"
                f"processed: {str(processed).lower()}\n"
                f"hidden: {str(hidden).lower()}\n"
                f"Вопрос: {question}\n"
                f"Ответ: {answer}"
            ),
            reply_markup=reply_markup,
        )


def handle_quiz_delete(ctx: BotContext) -> None:
    if not ctx.is_admin:
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text="Недостаточно прав: команда доступна только администраторам.",
        )
        return

    quiz_id = (ctx.args or "").strip()
    if not quiz_id:
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text="Usage: /quiz_delete <quiz_id>",
        )
        return

    quizzes = _load_quizzes(ctx.quizzes_file)
    before = len(quizzes)
    quizzes = [q for q in quizzes if str(q.get("id") or "") != quiz_id]
    after = len(quizzes)

    if after == before:
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text=f"Квиз с id={quiz_id} не найден.",
        )
        return

    try:
        _save_quizzes(quizzes_file=ctx.quizzes_file, quizzes=quizzes)
    except Exception as e:
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text=f"Не удалось сохранить файл квизов: {type(e).__name__}: {e}",
        )
        return

    # If wizard was creating this quiz, cancel it
    state = _QUIZ_WIZARD_STATE.get(ctx.user_id) or {}
    if str(state.get("quiz_id") or "") == quiz_id:
        _QUIZ_WIZARD_STATE.pop(ctx.user_id, None)

    _send_with_formatting_fallback(
        tg=ctx.tg,
        chat_id=ctx.chat_id,
        message_thread_id=ctx.message_thread_id,
        text=f"Готово. Удалил квиз: {quiz_id}",
    )


def handle_quiz_stat(ctx: BotContext) -> None:
    if ctx.chat_type != "private":
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text="Команда доступна только в личных сообщениях с ботом.",
        )
        return

    quizzes = _load_quizzes(ctx.quizzes_file)
    quizzes = [q for q in quizzes if not _is_hidden_quiz(q)]
    if not quizzes:
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text="Квизов пока нет.",
        )
        return

    state = _load_quiz_state(ctx.quiz_state_file)
    user_state = _get_user_quiz_state(state, ctx.user_id)
    results = user_state.get("results")
    if not isinstance(results, dict):
        results = {}

    active_quiz_id = user_state.get("active_quiz_id")
    active_quiz_id = str(active_quiz_id).strip() if active_quiz_id is not None else ""

    lines = ["Статистика по квизам:"]
    for q in quizzes:
        qid = str(q.get("id") or "").strip()
        r = results.get(qid) if isinstance(results, dict) else None
        correct = bool((r or {}).get("correct")) if isinstance(r, dict) else False
        attempts = int((r or {}).get("attempts") or 0) if isinstance(r, dict) else 0

        if correct:
            emoji = "✅"
        elif attempts > 0:
            emoji = "❌"
        else:
            emoji = "⏳" if qid == active_quiz_id and active_quiz_id else "⚪"

        lines.append(f"- {emoji} {qid} (попыток: {attempts})")

    _send_with_formatting_fallback(
        tg=ctx.tg,
        chat_id=ctx.chat_id,
        message_thread_id=ctx.message_thread_id,
        text="\n".join(lines),
    )


def handle_quiz_admin_stat(ctx: BotContext) -> None:
    if not ctx.is_admin:
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text="Недостаточно прав: команда доступна только администраторам.",
        )
        return

    quizzes = _load_quizzes(ctx.quizzes_file)
    if not quizzes:
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text="Квизов пока нет.",
        )
        return

    state = _load_quiz_state(ctx.quiz_state_file)
    users_map = state.get("users")
    if not isinstance(users_map, dict) or not users_map:
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text="Статистика пуста: нет данных по пользователям.",
        )
        return

    course_chat_id_raw = ctx.settings.get("course_chat_id")
    filter_by_course = isinstance(course_chat_id_raw, int) and course_chat_id_raw != 0
    course_chat_id_int: int
    if filter_by_course:
        assert isinstance(course_chat_id_raw, int)
        course_chat_id_int = course_chat_id_raw
    else:
        course_chat_id_int = 0

    student_user_ids: list[int] = []
    membership_errors = 0
    for k, v in users_map.items():
        if not isinstance(v, dict):
            continue
        try:
            uid = int(str(k).strip())
        except ValueError:
            continue
        if uid <= 0:
            continue
        if not filter_by_course:
            student_user_ids.append(uid)
            continue
        try:
            member = ctx.tg.get_chat_member(chat_id=course_chat_id_int, user_id=uid)
            status = str((member.get("result") or {}).get("status") or "")
            if status in {"creator", "administrator", "member", "restricted"}:
                student_user_ids.append(uid)
        except Exception:
            membership_errors += 1

    if not student_user_ids:
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text="Статистика пуста: не найдено студентов (по текущему состоянию).",
        )
        return

    quiz_ids = [str(q.get("id") or "").strip() for q in quizzes]
    quiz_ids = [qid for qid in quiz_ids if qid]
    hidden_by_id: dict[str, bool] = {
        str(q.get("id") or "").strip(): _is_hidden_quiz(q)
        for q in quizzes
        if str(q.get("id") or "").strip()
    }

    passed_any = 0
    passed_all = 0
    attempts_by_quiz: dict[str, list[int]] = {qid: [] for qid in quiz_ids}

    for uid in student_user_ids:
        u = users_map.get(str(uid))
        if not isinstance(u, dict):
            continue
        results = u.get("results")
        if not isinstance(results, dict):
            results = {}

        any_correct = False
        all_correct = True
        for qid in quiz_ids:
            r = results.get(qid)
            correct = bool((r or {}).get("correct")) if isinstance(r, dict) else False
            attempts = int((r or {}).get("attempts") or 0) if isinstance(r, dict) else 0
            if correct:
                any_correct = True
                attempts_by_quiz[qid].append(attempts)
            else:
                all_correct = False
        if any_correct:
            passed_any += 1
        if all_correct and quiz_ids:
            passed_all += 1

    def _mean_std(values: list[int]) -> tuple[float, float]:
        if not values:
            return (0.0, 0.0)
        m = sum(values) / len(values)
        var = sum((x - m) ** 2 for x in values) / len(values)
        return (m, math.sqrt(var))

    lines = [
        "Статистика по квизам (по студентам):",
        f"- студентов учтено: {len(student_user_ids)}",
        f"- прошли ≥1 квиз: {passed_any}",
        f"- прошли все квизы: {passed_all}",
    ]
    if filter_by_course:
        lines.append(f"- membership errors: {membership_errors}")
    else:
        lines.append("- предупреждение: course_chat_id не настроен, считаю всех пользователей из state")

    lines.append("")
    lines.append("По квизам (mean/std attempts среди тех, кто решил):")
    for qid in quiz_ids:
        vals = attempts_by_quiz.get(qid) or []
        m, s = _mean_std(vals)
        prefix = "🙈 " if hidden_by_id.get(qid, False) else ""
        if not vals:
            lines.append(f"- {prefix}{qid}: solved=0, mean/std=N/A")
        else:
            lines.append(f"- {prefix}{qid}: solved={len(vals)}, mean={m:.2f}, std={s:.2f}")

    _send_with_formatting_fallback(
        tg=ctx.tg,
        chat_id=ctx.chat_id,
        message_thread_id=ctx.message_thread_id,
        text="\n".join(lines),
    )

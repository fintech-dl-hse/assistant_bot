import logging

from context import BotContext
from constants import OPENAI_MODEL
from data.quiz import _load_quizzes
from llm import _answer_question, _fetch_readme, _is_quiz_question_paraphrase
from logging_utils import _log_token_usage
from text_format import _send_with_formatting_fallback


def handle_qa(ctx: BotContext) -> None:
    if not ctx.args:
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text="Usage: /qa <вопрос>",
        )
        return

    # Extra OpenAI check: if the question is a paraphrase of a quiz question, refuse to answer.
    quizzes = _load_quizzes(ctx.quizzes_file)
    if quizzes:
        try:
            is_paraphrase, usage = _is_quiz_question_paraphrase(
                llm=ctx.llm,
                user_question=ctx.args,
                quiz_questions=quizzes,
            )
        except Exception as e:
            logging.getLogger(__name__).warning(
                "Unexpected error in quiz paraphrase check: %s: %s",
                type(e).__name__,
                e,
                exc_info=True,
            )
            is_paraphrase, usage = False, {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        if int(usage.get("total_tokens") or 0) > 0:
            _log_token_usage(
                message=ctx.message,
                pm_log_file=ctx.pm_log_file,
                request_id=ctx.request_id,
                cmd=ctx.cmd,
                purpose="qa_quiz_paraphrase_check",
                model=OPENAI_MODEL,
                usage=usage,
            )

        if is_paraphrase:
            _send_with_formatting_fallback(
                tg=ctx.tg,
                chat_id=ctx.chat_id,
                message_thread_id=ctx.message_thread_id,
                text=(
                    "Попытка хорошая, но так просто ответ на вопрос квиза ты не получишь. "
                    "Пройди квиз честно."
                ),
            )
            return

    try:
        readme = _fetch_readme()
    except Exception as e:
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text=f"Failed to fetch README context: {type(e).__name__}: {e}",
        )
        return

    try:
        answer, usage = _answer_question(client=ctx.llm, readme=readme, question=ctx.args)
    except Exception as e:
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text=f"LLM request failed: {type(e).__name__}: {e}",
        )
        return
    if int(usage.get("total_tokens") or 0) > 0:
        _log_token_usage(
            message=ctx.message,
            pm_log_file=ctx.pm_log_file,
            request_id=ctx.request_id,
            cmd=ctx.cmd,
            purpose="qa",
            model=OPENAI_MODEL,
            usage=usage,
        )

    _send_with_formatting_fallback(
        tg=ctx.tg,
        chat_id=ctx.chat_id,
        message_thread_id=ctx.message_thread_id,
        text=answer,
    )

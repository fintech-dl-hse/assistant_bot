import logging
from typing import Callable

from context import BotContext
from data.quiz import _QUIZ_WIZARD_STATE

from handlers.admin import (
    handle_add_admin,
    handle_backup,
    handle_course_chat,
    handle_course_members,
    handle_set_backup_chat_id,
    handle_tokens_stat,
)
from handlers.homework import handle_hw_invite, handle_hw_pin, handle_invit
from handlers.misc import handle_get_chat_id, handle_help
from handlers.qa import handle_qa
from handlers.quiz import (
    handle_quiz,
    handle_quiz_admin_stat,
    handle_quiz_answer,
    handle_quiz_ask,
    handle_quiz_create,
    handle_quiz_delete,
    handle_quiz_list,
    handle_quiz_stat,
    handle_quiz_wizard,
    handle_skip,
)
from handlers.teach import handle_teach
from handlers.user import handle_github, handle_me

COMMAND_HANDLERS: dict[str, Callable[[BotContext], None]] = {
    "/help": handle_help,
    "/get_chat_id": handle_get_chat_id,
    "/qa": handle_qa,
    "/me": handle_me,
    "/github": handle_github,
    "/invit": handle_invit,
    "/hw_pin": handle_hw_pin,
    "/hw_invite": handle_hw_invite,
    "/teach": handle_teach,
    "/quiz": handle_quiz,
    "/skip": handle_skip,
    "/quiz_stat": handle_quiz_stat,
    "/quiz_ask": handle_quiz_ask,
    "/quiz_create": handle_quiz_create,
    "/quiz_list": handle_quiz_list,
    "/quiz_delete": handle_quiz_delete,
    "/quiz_admin_stat": handle_quiz_admin_stat,
    "/add_admin": handle_add_admin,
    "/course_chat": handle_course_chat,
    "/course_members": handle_course_members,
    "/tokens_stat": handle_tokens_stat,
    "/set_backup_chat_id": handle_set_backup_chat_id,
    "/backup": handle_backup,
}


def dispatch(ctx: BotContext) -> None:
    # 1. Quiz wizard (non-command, admin, private)
    if ctx.cmd == "" and ctx.chat_type == "private" and ctx.is_admin and ctx.user_id in _QUIZ_WIZARD_STATE:
        handle_quiz_wizard(ctx)
        return

    # 2. Quiz answer (non-command, private)
    if ctx.cmd == "" and ctx.chat_type == "private":
        handle_quiz_answer(ctx)
        return

    # 3. Lookup in COMMAND_HANDLERS dict
    handler = COMMAND_HANDLERS.get(ctx.cmd)
    if handler is None:
        return

    try:
        ctx.tg.send_message_reaction(chat_id=ctx.chat_id, message_id=ctx.message_id, reaction_emoji="👀")
    except Exception:
        logging.getLogger(__name__).debug("Failed to set reaction", exc_info=True)

    handler(ctx)

from context import BotContext
from text_format import _send_with_formatting_fallback


def handle_help(ctx: BotContext) -> None:
    lines = [
        "Доступные команды:",
        "- /help",
        "- /qa <вопрос> - задать организационный попрос по курсу (в контексте README курса)",
        "- /get_chat_id",
        "- /me <ФИО>",
        "- /github [nickname] — привязать или показать GitHub",
        "- /invit — проверить репозитории ДЗ",
        "- /quiz",
        "- /skip",
        "- /quiz_stat",
    ]
    if ctx.is_admin:
        lines.append("- /add_admin <user_id>")
        lines.append("- /course_chat <chat_id>")
        lines.append("- /course_members")
        lines.append("- /quiz_create <quiz_id>")
        lines.append("- /quiz_list")
        lines.append("- /quiz_delete <quiz_id>")
        lines.append("- /quiz_ask <quiz_id>")
        lines.append("- /quiz_admin_stat")
        lines.append("- /tokens_stat")
        lines.append("- /set_backup_chat_id <chat_id>")
        lines.append("- /backup")
        lines.append("- /hw_pin — список ДЗ со ссылками на приглашения в Classroom")
        lines.append("- /hw_invite <hw-slug> <github_classrooms_invite_link>")
        lines.append("- /teach — последний семинар (Colab) и последняя лекция")
    _send_with_formatting_fallback(
        tg=ctx.tg,
        chat_id=ctx.chat_id,
        message_thread_id=ctx.message_thread_id,
        text="\n".join(lines),
    )


def handle_get_chat_id(ctx: BotContext) -> None:
    _send_with_formatting_fallback(
        tg=ctx.tg,
        chat_id=ctx.chat_id,
        message_thread_id=ctx.message_thread_id,
        text=(
            "chat_id: "
            f"{ctx.chat_id}\n"
            "message_thread_id: "
            f"{ctx.message_thread_id}\n"
        ),
    )

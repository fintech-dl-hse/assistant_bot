import logging
from datetime import datetime, timezone

from context import BotContext
from constants import (
    COURSE_REPO_BRANCH,
    COURSE_REPO_NAME,
    COURSE_REPO_OWNER,
    DEFAULT_DRIVE_FEEDBACK_FOLDER_ID,
    SEMINARS_PATH,
)
from text_format import _escape_markdown_v2_plain, _md2_link, _send_with_formatting_fallback

from drive_client import (
    DriveStorageQuotaExceeded,
    copy_feedback_form as drive_copy_feedback_form,
    _get_credentials_path as drive_get_credentials_path,
)
from github_client import (
    get_latest_seminar_notebook_path as github_get_latest_seminar_notebook_path,
)


def _seminar_week_from_notebook_path(notebook_path: str) -> int | None:
    """
    Извлекает номер недели из пути к ноутбуку семинара.

    Например: seminars/04_cnn/04_seminar_cnn.ipynb -> 4.

    Returns:
        Номер недели (1, 2, 3, ...) или None.
    """
    if not notebook_path or "/" not in notebook_path:
        return None
    filename = notebook_path.split("/")[-1]
    if not filename.endswith(".ipynb"):
        return None
    prefix = filename.split("_")[0]
    if not prefix.isdigit():
        return None
    return int(prefix)


def handle_teach(ctx: BotContext) -> None:
    if not ctx.is_admin:
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text="Недостаточно прав: команда доступна только администраторам.",
        )
        return
    path = github_get_latest_seminar_notebook_path(
        owner=COURSE_REPO_OWNER,
        repo=COURSE_REPO_NAME,
        branch=COURSE_REPO_BRANCH,
        seminars_path=SEMINARS_PATH,
    )
    colab_url: str | None = None
    if path:
        colab_url = (
            f"https://colab.research.google.com/github/{COURSE_REPO_OWNER}/{COURSE_REPO_NAME}/"
            f"blob/{COURSE_REPO_BRANCH}/{path}"
        )
    # lecture_url = github_get_latest_lecture_url(
    #     owner=COURSE_REPO_OWNER,
    #     repo=COURSE_REPO_NAME,
    #     branch=COURSE_REPO_BRANCH,
    #     lectures_path=LECTURES_PATH,
    # )
    folder_id = (
        (ctx.settings.get("drive_feedback_folder_id") or "").strip()
        or DEFAULT_DRIVE_FEEDBACK_FOLDER_ID
    )
    creds_path = drive_get_credentials_path(ctx.settings)
    form_result: tuple[str, str] | None = None
    _form_quota_msg = False
    if False and folder_id and creds_path and path:
        week = _seminar_week_from_notebook_path(path)
        year_short = datetime.now(timezone.utc).year % 100
        form_title = f"[DL{year_short:02d}] {week} неделя" if week is not None else f"[DL{year_short:02d}] неделя"
        try:
            form_result = drive_copy_feedback_form(
                folder_id=folder_id,
                new_title=form_title,
                credentials_path=creds_path,
            )
            if not form_result:
                logging.getLogger(__name__).warning(
                    "teach/form: создание формы не удалось (folder_id=%s, title=%s)",
                    folder_id,
                    form_title,
                )
        except DriveStorageQuotaExceeded:
            form_result = None
            _form_quota_msg = True
        else:
            _form_quota_msg = False

    # Собираем сообщение в MarkdownV2 с эмодзи и кликабельными ссылками
    md_lines: list[str] = []
    # if lecture_url:
    #     md_lines.append(
    #         "📖 " + _escape_markdown_v2_plain("Лекция: ") + _md2_link("открыть PDF", lecture_url)
    #     )
    if colab_url:
        md_lines.append(
            "📓 " + _escape_markdown_v2_plain("Семинар (Colab): ") + _md2_link("открыть в Colab", colab_url)
        )
    # if form_result:
    #     edit_url, view_url = form_result
    #     md_lines.append(
    #         "📋 " + _escape_markdown_v2_plain("Форма (раздача): ") + _md2_link("заполнить", view_url)
    #     )
    #     md_lines.append(
    #         "✏️ " + _escape_markdown_v2_plain("Форма (редактировать): ") + _md2_link("редактировать", edit_url)
    #     )
    # elif _form_quota_msg:
    #     md_lines.append(
    #         "⚠️ "
    #         + _escape_markdown_v2_plain(
    #             "Форма: квота хранилища Drive сервисного аккаунта исчерпана. "
    #             "Удалите старые копии форм в Drive или перенесите папку в Shared Drive."
    #         )
    #     )
    # elif folder_id and creds_path and path:
    #     md_lines.append(
    #         "⚠️ " + _escape_markdown_v2_plain(
    #             "Форма обратной связи: не удалось создать копию (проверьте Drive и права)."
    #         )
    #     )
    # elif (folder_id or creds_path) and not (folder_id and creds_path):
    #     md_lines.append(
    #         "⚠️ " + _escape_markdown_v2_plain(
    #             "Форма обратной связи: укажите drive_credentials_path и drive_feedback_folder_id в конфиге."
    #         )
    #     )

    if not md_lines:
        _teach_log = logging.getLogger(__name__)
        _teach_log.warning(
            "teach: ничего не удалось получить: path=%s, colab_url=%s, lecture_url=%s, form_result=%s, "
            "folder_id=%s, creds_path=%s",
            path,
            "ok" if colab_url else None,
            None,  # lecture_url (disabled)
            "ok" if form_result else None,
            folder_id or None,
            "set" if creds_path else None,
        )
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text="Не удалось получить данные из репозитория курса.",
        )
        return

    md_lines.append("⏰ Начнем в 19:50")

    teach_text = "\n".join(md_lines)
    _send_with_formatting_fallback(
        tg=ctx.tg,
        chat_id=ctx.chat_id,
        message_thread_id=ctx.message_thread_id,
        text=teach_text,
        markdown_v2_raw=True,
    )

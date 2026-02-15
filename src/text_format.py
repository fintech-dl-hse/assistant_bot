import re

from telegram_client import TelegramClient


def _escape_markdown_v2_plain(chunk: str) -> str:
    """
    Экранирует произвольный текст для использования в Telegram MarkdownV2
    (вне ссылок и блоков кода). Для ссылок используйте _md2_link.
    """
    if not chunk:
        return chunk
    chunk = chunk.replace("\\", "\\\\")
    return re.sub(r"([_*\[\]()~`>#+\-=|{}.!])", r"\\\1", chunk)


def _md2_link(label: str, url: str) -> str:
    """
    Формирует кликабельную ссылку в формате MarkdownV2.
    В URL экранируется только ')'.
    """
    label_escaped = _escape_markdown_v2_plain(label)
    url_escaped = url.replace("\\", "\\\\").replace(")", "\\)")
    return f"[{label_escaped}]({url_escaped})"


def _hw_display_name(template_str: str) -> str:
    """
    Из шаблона вида owner/repo-{github_nickname} возвращает название домашки без ника:
    например, "fintech-dl-hse/hw-mlp-{github_nickname}" -> "hw-mlp".
    """
    base = (template_str or "").replace("{github_nickname}", "").rstrip("-")
    if "/" in base:
        base = base.split("/", 1)[1]
    return base or template_str or ""


def _hw_id_to_short_name(hw_id: str) -> str:
    """Короткое отображаемое имя для секции /invit (hw-mlp -> MLP, hw-weight-init -> Weight Init)."""
    _MAP = {
        "hw-mlp": "MLP",
        "hw-activations": "Activations",
        "hw-weight-init": "Weight Init",
        "hw-optimization": "Optimization",
        "hw-dropout": "Dropout",
        "hw-batchnorm": "BatchNorm",
        "hw-pytorch-basics": "Basics",
        "hw-autograd-mlp": "hw-autograd-mlp",
        "hw-muon": "hw-muon",
    }
    if hw_id in _MAP:
        return _MAP[hw_id]
    return hw_id.replace("hw-", "").replace("-", " ").title() or hw_id


def _points_russian(max_points: int) -> str:
    """Склонение баллов: 1 балл, 2 балла, 5 баллов. n = max_points // 100."""
    n = max(0, int(max_points) // 100)
    if n % 10 == 1 and n % 100 != 11:
        return f"{n} балл"
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return f"{n} балла"
    return f"{n} баллов"


def _format_deadline_ru(deadline_iso: str) -> str:
    """Формат дедлайна для /invit: '2026-01-28T23:59:59' -> '28 января 23:59'."""
    months_ru = (
        "января", "февраля", "марта", "апреля", "мая", "июня",
        "июля", "августа", "сентября", "октября", "ноября", "декабря",
    )
    s = (deadline_iso or "").strip()
    if not s or "T" not in s:
        return s
    try:
        date_part, time_part = s.split("T", 1)[:2]
        y, m, d = date_part.split("-")[:3]
        day = int(d)
        month_idx = int(m)
        if 1 <= month_idx <= 12:
            month = months_ru[month_idx - 1]
        else:
            month = m
        time_short = time_part[:5] if len(time_part) >= 5 else time_part  # HH:MM
        return f"{day} {month} {time_short}"
    except (ValueError, IndexError):
        return s


def _escape_markdown_v2(text: str) -> str:
    """
    Escapes text for Telegram MarkdownV2.
    Docs: https://core.telegram.org/bots/api#markdownv2-style
    """
    if text is None:
        return ""

    def _escape_plain(chunk: str) -> str:
        chunk = chunk.replace("\\", "\\\\")
        # Telegram MarkdownV2 requires escaping these chars in plain text:
        # _ * [ ] ( ) ~ ` > # + - = | { } . !
        return re.sub(r"([_*\[\]()~`>#+\-=|{}.!])", r"\\\1", chunk)

    s = str(text)

    # Preserve fenced and inline code blocks; escape only outside of them.
    # - Fenced: ```...```
    # - Inline: `...` (single-line)
    code_re = re.compile(r"```[\s\S]*?```|`[^`\n]+`")

    out: list[str] = []
    last = 0
    for m in code_re.finditer(s):
        if m.start() > last:
            out.append(_escape_plain(s[last : m.start()]))
        out.append(m.group(0))
        last = m.end()
    if last < len(s):
        out.append(_escape_plain(s[last:]))

    return "".join(out)



def _send_with_formatting_fallback(
    tg: TelegramClient,
    chat_id: int,
    message_thread_id: int,
    text: str,
    *,
    markdown_v2_raw: bool = False,
) -> bool:
    """
    Отправляет сообщение. По умолчанию экранирует текст и шлёт как MarkdownV2.
    Если markdown_v2_raw=True, текст считается уже готовым MarkdownV2 (со ссылками и т.д.).
    """
    if markdown_v2_raw:
        resp = tg.send_message(
            chat_id=chat_id,
            message_thread_id=message_thread_id,
            parse_mode="MarkdownV2",
            message=text,
        )
        if getattr(resp, "status_code", 500) == 200:
            return True
        tg.send_message(
            chat_id=chat_id,
            message_thread_id=message_thread_id,
            parse_mode=None,
            message=text,
        )
        return True

    escaped = _escape_markdown_v2(text)
    resp2 = tg.send_message(
        chat_id=chat_id,
        message_thread_id=message_thread_id,
        parse_mode="MarkdownV2",
        message=escaped,
    )
    if getattr(resp2, "status_code", 500) == 200:
        return True

    resp_plain = tg.send_message(
        chat_id=chat_id,
        message_thread_id=message_thread_id,
        parse_mode=None,
        message=text,
    )
    return getattr(resp_plain, "status_code", 500) == 200

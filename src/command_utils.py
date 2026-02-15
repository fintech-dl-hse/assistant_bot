import os
from typing import Any, Dict, Tuple


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        raise RuntimeError(f"Required env var is not set: {name}")
    return value


def _extract_command(text: str) -> Tuple[str, str]:
    """
    Returns (command, args).

    Handles /cmd and /cmd@botname forms.
    """
    text = (text or "").strip()
    if not text.startswith("/"):
        return "", ""

    parts = text.split(maxsplit=1)
    raw_cmd = parts[0]
    args = parts[1] if len(parts) > 1 else ""

    cmd = raw_cmd.split("@", maxsplit=1)[0]
    return cmd, args.strip()


def _get_message_basics(message: Dict[str, Any]) -> Tuple[int, int, int]:
    chat_id = int(message["chat"]["id"])
    message_id = int(message["message_id"])
    message_thread_id = int(message.get("message_thread_id") or 0)
    return chat_id, message_id, message_thread_id


def _get_sender(message: Dict[str, Any]) -> Tuple[int, str]:
    sender = message.get("from") or {}
    user_id = int(sender.get("id") or 0)
    username = str(sender.get("username") or "").strip()
    return user_id, username


def _is_admin(settings: Dict[str, Any], user_id: int, username: str) -> bool:
    admins = settings.get("admin_users") or []
    username_norm = username.lstrip("@").lower()
    for entry in admins:
        if isinstance(entry, int) and entry == user_id:
            return True
        if isinstance(entry, str) and entry.strip().lstrip("@").lower() == username_norm and username_norm:
            return True
    return False


def _is_command_for_this_bot(text: str, bot_username: str) -> bool:
    """
    True if `text` looks like a bot command that is intended for THIS bot.

    - /cmd ...              -> True
    - /cmd@ThisBot ...      -> True (case-insensitive)
    - /cmd@OtherBot ...     -> False
    """
    text = (text or "").strip()
    if not text.startswith("/"):
        return False
    first = text.split(maxsplit=1)[0]
    if "@" not in first:
        return True
    if not bot_username:
        return False
    _, mentioned = first.split("@", maxsplit=1)
    mentioned = mentioned.strip().lstrip("@").lower()
    return mentioned == bot_username.strip().lstrip("@").lower()

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Tuple

from command_utils import _is_command_for_this_bot


def _append_jsonl_record(path_str: str, record: Dict[str, Any]) -> None:
    path = Path(path_str)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False) + "\n"
    with path.open("a", encoding="utf-8") as f:
        f.write(line)


def _get_user_fields(message: Dict[str, Any]) -> Dict[str, Any]:
    sender = message.get("from") or {}
    if not isinstance(sender, dict):
        sender = {}
    return {
        "user_id": int(sender.get("id") or 0),
        "username": str(sender.get("username") or ""),
        "first_name": str(sender.get("first_name") or ""),
        "last_name": str(sender.get("last_name") or ""),
    }


def _log_private_message(
    message: Dict[str, Any],
    pm_log_file: str,
    bot_username: str,
    request_id: str,
    cmd: str,
) -> bool:
    chat = message.get("chat") or {}
    if not isinstance(chat, dict):
        return False

    chat_type = str(chat.get("type") or "")
    text = str(message.get("text") or "")

    # Keep existing behavior: log ALL private messages.
    # Additionally: log group/supergroup messages ONLY if they are commands for this bot.
    if chat_type == "private":
        pass
    elif chat_type in {"group", "supergroup"}:
        if not _is_command_for_this_bot(text=text, bot_username=bot_username):
            return False
    else:
        return False

    record = {
        "record_type": "message",
        "request_id": request_id,
        "ts": datetime.now(timezone.utc).isoformat(),
        "message_date": int(message.get("date") or 0),
        "chat_id": int(chat.get("id") or 0),
        "chat_type": chat_type,
        **_get_user_fields(message),
        "message_id": int(message.get("message_id") or 0),
        "text": str(message.get("text") or ""),
        "cmd": str(cmd or ""),
    }

    try:
        _append_jsonl_record(pm_log_file, record)
    except Exception:
        logging.getLogger(__name__).warning(
            "Failed to write private message log to %s",
            pm_log_file,
            exc_info=True,
        )
        return False
    return True


def _extract_openai_usage(resp: Any) -> Dict[str, int]:
    """
    Best-effort extraction of usage fields from OpenAI SDK response.
    Returns dict with: prompt_tokens, completion_tokens, total_tokens (all ints >= 0).
    """
    usage = getattr(resp, "usage", None)
    prompt = int(getattr(usage, "prompt_tokens", 0) or 0) if usage is not None else 0
    completion = int(getattr(usage, "completion_tokens", 0) or 0) if usage is not None else 0
    total = int(getattr(usage, "total_tokens", 0) or 0) if usage is not None else 0
    return {
        "prompt_tokens": max(0, prompt),
        "completion_tokens": max(0, completion),
        "total_tokens": max(0, total),
    }


def _log_token_usage(
    *,
    message: Dict[str, Any],
    pm_log_file: str,
    request_id: str,
    cmd: str,
    purpose: str,
    model: str,
    usage: Dict[str, int],
) -> None:
    chat = message.get("chat") or {}
    if not isinstance(chat, dict):
        return
    record = {
        "record_type": "tokens",
        "request_id": request_id,
        "ts": datetime.now(timezone.utc).isoformat(),
        "message_date": int(message.get("date") or 0),
        "chat_id": int(chat.get("id") or 0),
        "chat_type": str(chat.get("type") or ""),
        **_get_user_fields(message),
        "message_id": int(message.get("message_id") or 0),
        "cmd": str(cmd or ""),
        "purpose": str(purpose or ""),
        "model": str(model or ""),
        "prompt_tokens": int(usage.get("prompt_tokens") or 0),
        "completion_tokens": int(usage.get("completion_tokens") or 0),
        "total_tokens": int(usage.get("total_tokens") or 0),
    }
    try:
        _append_jsonl_record(pm_log_file, record)
    except Exception:
        logging.getLogger(__name__).warning(
            "Failed to write token usage log to %s",
            pm_log_file,
            exc_info=True,
        )


def _tokens_stat_from_log(pm_log_file: str) -> Tuple[int, list[Tuple[int, str, int]]]:
    """
    Returns: (total_tokens, top_users) where top_users is list of (user_id, username, total_tokens).
    """
    path = Path(pm_log_file)
    if not path.exists():
        return 0, []

    total = 0
    per_user: dict[int, int] = {}
    usernames: dict[int, str] = {}

    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                if not isinstance(rec, dict):
                    continue
                if rec.get("record_type") != "tokens":
                    continue
                t = int(rec.get("total_tokens") or 0)
                if t <= 0:
                    continue
                uid = int(rec.get("user_id") or 0)
                if uid <= 0:
                    continue
                total += t
                per_user[uid] = per_user.get(uid, 0) + t
                uname = str(rec.get("username") or "")
                if uname:
                    usernames[uid] = uname
    except Exception:
        logging.getLogger(__name__).warning("Failed to read tokens stats from %s", pm_log_file, exc_info=True)
        return 0, []

    top = sorted(per_user.items(), key=lambda kv: kv[1], reverse=True)[:5]
    top_users: list[Tuple[int, str, int]] = []
    for uid, t in top:
        top_users.append((uid, usernames.get(uid, ""), t))
    return total, top_users

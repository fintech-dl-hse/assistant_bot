import argparse
import json
import logging
from pathlib import Path
from typing import Any, Dict


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fintech DL HSE assistant Telegram bot")
    parser.add_argument(
        "--config",
        type=str,
        default="bot_config.json",
        help="Path to JSON config file (default: assistant_bot/bot_config.json)",
    )
    parser.add_argument(
        "--pm-log-file",
        type=str,
        default="private_messages.jsonl",
        help="Path to JSONL log file for private chats (default: assistant_bot/private_messages.jsonl)",
    )
    parser.add_argument(
        "--quizzes-file",
        type=str,
        default="quizzes.json",
        help="Path to JSON file with quizzes (default: assistant_bot/quizzes.json)",
    )
    parser.add_argument(
        "--quiz-state-file",
        type=str,
        default="quiz_state.json",
        help="Path to JSON file with per-user quiz state (default: assistant_bot/quiz_state.json)",
    )
    parser.add_argument(
        "--users-file",
        type=str,
        default="users.json",
        help="Path to JSON file with user data (default: assistant_bot/users.json)",
    )
    return parser.parse_args(argv)


def _load_settings(config_path: str) -> Dict[str, Any]:
    """
    Load bot settings from JSON file.

    Expected schema:
      - admin_users: list[int|str] (Telegram user IDs and/or usernames)
      - course_chat_id: int|null (Telegram chat ID for the course)
      - backup_chat_id: int|null (Telegram chat ID for backups)
      - drive_credentials_path: str|null (путь к JSON ключу service account для Drive)
      - drive_feedback_folder_id: str|null (ID папки Drive с шаблоном формы обратной связи)

    The file is intentionally read on every request.
    """
    fallback: Dict[str, Any] = {
        "admin_users": [],
        "course_chat_id": None,
        "backup_chat_id": None,
        "drive_credentials_path": None,
        "drive_feedback_folder_id": None,
    }
    try:
        path = Path(config_path)
        if not path.exists():
            example_path = Path(__file__).with_name("bot_config_example.json")
            if example_path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(example_path.read_text(encoding="utf-8"), encoding="utf-8")
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        if not isinstance(data, dict):
            return fallback
        admin_users = data.get("admin_users", [])
        if not isinstance(admin_users, list):
            admin_users = []
        course_chat_id_raw = data.get("course_chat_id", None)
        course_chat_id: int | None
        if isinstance(course_chat_id_raw, int):
            course_chat_id = course_chat_id_raw
        elif isinstance(course_chat_id_raw, str):
            try:
                course_chat_id = int(course_chat_id_raw.strip())
            except ValueError:
                course_chat_id = None
        else:
            course_chat_id = None
        backup_chat_id_raw = data.get("backup_chat_id", None)
        backup_chat_id: int | None
        if isinstance(backup_chat_id_raw, int):
            backup_chat_id = backup_chat_id_raw
        elif isinstance(backup_chat_id_raw, str):
            try:
                backup_chat_id = int(backup_chat_id_raw.strip())
            except ValueError:
                backup_chat_id = None
        else:
            backup_chat_id = None
        drive_credentials_path = data.get("drive_credentials_path")
        if not isinstance(drive_credentials_path, str) or not drive_credentials_path.strip():
            drive_credentials_path = None
        else:
            drive_credentials_path = drive_credentials_path.strip()
        drive_feedback_folder_id = data.get("drive_feedback_folder_id")
        if not isinstance(drive_feedback_folder_id, str) or not drive_feedback_folder_id.strip():
            drive_feedback_folder_id = None
        else:
            drive_feedback_folder_id = drive_feedback_folder_id.strip()
        return {
            "admin_users": admin_users,
            "course_chat_id": course_chat_id,
            "backup_chat_id": backup_chat_id,
            "drive_credentials_path": drive_credentials_path,
            "drive_feedback_folder_id": drive_feedback_folder_id,
        }
    except Exception:
        logging.getLogger(__name__).warning(
            "Failed to load config %s; using defaults",
            config_path,
            exc_info=True,
        )
        return fallback


def _save_settings(config_path: str, settings: Dict[str, Any]) -> None:
    """
    Save bot settings to JSON file.

    Uses atomic write (tmp file + replace) to reduce risk of corruption.
    """
    path = Path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    payload = {
        "admin_users": settings.get("admin_users") or [],
        "course_chat_id": settings.get("course_chat_id", None),
        "backup_chat_id": settings.get("backup_chat_id", None),
        "drive_credentials_path": settings.get("drive_credentials_path"),
        "drive_feedback_folder_id": settings.get("drive_feedback_folder_id"),
    }
    raw = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    tmp_path.write_text(raw, encoding="utf-8")
    tmp_path.replace(path)

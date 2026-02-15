from dataclasses import dataclass
from typing import Any, Dict

from openai import OpenAI

from telegram_client import TelegramClient


@dataclass
class BotContext:
    tg: TelegramClient
    llm: OpenAI
    message: Dict[str, Any]
    settings: Dict[str, Any]
    chat_id: int
    message_id: int
    message_thread_id: int
    user_id: int
    username: str
    is_admin: bool
    chat_type: str
    cmd: str
    args: str
    request_id: str
    config_path: str
    pm_log_file: str
    quizzes_file: str
    quiz_state_file: str
    users_file: str
    bot_user_id: int
    bot_username: str

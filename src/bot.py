import logging
import time
import uuid
import threading

import requests
from openai import OpenAI
import schedule

from telegram_client import TelegramClient
from config import _parse_args, _load_settings
from constants import OPENAI_BASE_URL
from command_utils import (
    _require_env,
    _extract_command,
    _get_message_basics,
    _get_sender,
    _is_admin,
)
from context import BotContext
from logging_utils import _log_private_message
from backup import _create_backup
from callback_handler import _handle_callback_query
from handlers import dispatch


def _build_context(
    tg: TelegramClient,
    llm: OpenAI,
    message: dict,
    config_path: str,
    pm_log_file: str,
    quizzes_file: str,
    quiz_state_file: str,
    users_file: str,
    bot_user_id: int,
    bot_username: str,
) -> BotContext:
    settings = _load_settings(config_path)
    text = (message.get("text") or "").strip()
    cmd, args = _extract_command(text)
    chat_id, message_id, message_thread_id = _get_message_basics(message)
    user_id, username = _get_sender(message)
    is_admin_flag = _is_admin(settings=settings, user_id=user_id, username=username)
    chat_type = str((message.get("chat") or {}).get("type") or "")
    request_id = uuid.uuid4().hex

    return BotContext(
        tg=tg,
        llm=llm,
        message=message,
        settings=settings,
        chat_id=chat_id,
        message_id=message_id,
        message_thread_id=message_thread_id,
        user_id=user_id,
        username=username,
        is_admin=is_admin_flag,
        chat_type=chat_type,
        cmd=cmd,
        args=args,
        request_id=request_id,
        config_path=config_path,
        pm_log_file=pm_log_file,
        quizzes_file=quizzes_file,
        quiz_state_file=quiz_state_file,
        users_file=users_file,
        bot_user_id=bot_user_id,
        bot_username=bot_username,
    )


def _handle_message(
    tg: TelegramClient,
    llm: OpenAI,
    message: dict,
    config_path: str,
    pm_log_file: str,
    quizzes_file: str,
    quiz_state_file: str,
    users_file: str,
    bot_user_id: int,
    bot_username: str,
) -> None:
    ctx = _build_context(
        tg=tg,
        llm=llm,
        message=message,
        config_path=config_path,
        pm_log_file=pm_log_file,
        quizzes_file=quizzes_file,
        quiz_state_file=quiz_state_file,
        users_file=users_file,
        bot_user_id=bot_user_id,
        bot_username=bot_username,
    )

    _log_private_message(
        message=message,
        pm_log_file=pm_log_file,
        bot_username=bot_username,
        request_id=ctx.request_id,
        cmd=ctx.cmd,
    )

    dispatch(ctx)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logger = logging.getLogger(__name__)

    _require_env("TELEGRAM_BOT_TOKEN")
    api_key = _require_env("API_KEY")

    tg = TelegramClient()
    llm = OpenAI(
        api_key=api_key,
        base_url=OPENAI_BASE_URL,
    )

    bot_user_id = 0
    bot_username = ""
    try:
        me = tg.get_me()
        bot_user_id = int((me.get("result") or {}).get("id") or 0)
        bot_username = str((me.get("result") or {}).get("username") or "").strip()
        logger.info("Bot started: %s", bot_username or None)
    except Exception:
        logger.info("Bot started")

    # Setup backup scheduler
    def scheduled_backup():
        """Wrapper function for scheduled backups."""
        settings = _load_settings(args.config)
        backup_chat_id = settings.get("backup_chat_id")
        if isinstance(backup_chat_id, int) and backup_chat_id != 0:
            logger.info("Running scheduled backup...")
            success = _create_backup(
                tg=tg,
                config_path=args.config,
                pm_log_file=args.pm_log_file,
                quizzes_file=args.quizzes_file,
                quiz_state_file=args.quiz_state_file,
                users_file=args.users_file,
                backup_chat_id=backup_chat_id,
            )
            if success:
                logger.info("Scheduled backup completed successfully")
            else:
                logger.error("Scheduled backup failed")
        else:
            logger.warning("Backup chat not configured, skipping scheduled backup")

    # Schedule backup every Monday at 10:00 AM
    schedule.every().monday.at("10:00").do(scheduled_backup)
    logger.info("Backup scheduler configured: every Monday at 10:00 AM")

    # Run scheduler in a separate thread
    def run_scheduler():
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute

    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    logger.info("Backup scheduler thread started")

    offset = 0
    while True:
        try:
            data = tg.get_updates(offset=offset)
            results = data.get("result") or []

            for update in results:
                update_id = update.get("update_id")
                if isinstance(update_id, int):
                    offset = max(offset, update_id + 1)

                message = update.get("message")
                if isinstance(message, dict):
                    _handle_message(
                        tg=tg,
                        llm=llm,
                        message=message,
                        config_path=args.config,
                        pm_log_file=args.pm_log_file,
                        quizzes_file=args.quizzes_file,
                        quiz_state_file=args.quiz_state_file,
                        users_file=args.users_file,
                        bot_user_id=bot_user_id,
                        bot_username=bot_username,
                    )

                callback_query = update.get("callback_query")
                if isinstance(callback_query, dict):
                    _handle_callback_query(
                        tg=tg,
                        callback_query=callback_query,
                        config_path=args.config,
                        pm_log_file=args.pm_log_file,
                        quizzes_file=args.quizzes_file,
                        quiz_state_file=args.quiz_state_file,
                    )

        except requests.exceptions.RequestException as e:
            logger.warning("Polling error: %s", e)
            time.sleep(2)
        except Exception:
            logger.exception("Unexpected error in polling loop")
            time.sleep(2)


if __name__ == "__main__":
    main()

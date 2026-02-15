import logging
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from telegram_client import TelegramClient


def _create_backup(
    tg: TelegramClient,
    config_path: str,
    pm_log_file: str,
    quizzes_file: str,
    quiz_state_file: str,
    users_file: str,
    backup_chat_id: int,
) -> bool:
    """
    Create a backup of all bot settings and state files, and send it to the backup chat.

    Returns True if backup was created and sent successfully, False otherwise.
    """
    logger = logging.getLogger(__name__)

    try:
        # Create backup directory
        backup_dir = Path("backups")
        backup_dir.mkdir(exist_ok=True)

        # Create backup filename with timestamp
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_filename = f"bot_backup_{timestamp}.zip"
        backup_path = backup_dir / backup_filename

        # List of files to backup
        files_to_backup = [
            (Path(config_path), "bot_config.json"),
            (Path(quizzes_file), "quizzes.json"),
            (Path(quiz_state_file), "quiz_state.json"),
            (Path(users_file), "users.json"),
            (Path(pm_log_file), "private_messages.jsonl"),
        ]

        # Create zip archive
        with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path, archive_name in files_to_backup:
                if file_path.exists():
                    zipf.write(file_path, archive_name)
                    logger.info(f"Added {file_path} to backup as {archive_name}")
                else:
                    logger.warning(f"File {file_path} does not exist, skipping")

        # Send backup to Telegram
        with open(backup_path, 'rb') as backup_file:
            resp = tg._request(
                method="POST",
                endpoint="sendDocument",
                data={
                    "chat_id": backup_chat_id,
                    "caption": f"Еженедельный бэкап бота от {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
                },
                files={"document": (backup_filename, backup_file, "application/zip")},
                timeout=30,
            )

        if resp.status_code == 200:
            logger.info(f"Backup sent successfully to chat {backup_chat_id}")
            # Clean up old backups (keep only last 5)
            backup_files = sorted(backup_dir.glob("bot_backup_*.zip"))
            if len(backup_files) > 5:
                for old_backup in backup_files[:-5]:
                    old_backup.unlink()
                    logger.info(f"Deleted old backup: {old_backup}")
            return True
        else:
            logger.error(f"Failed to send backup: status code {resp.status_code}")
            return False

    except Exception as e:
        logger.error(f"Failed to create backup: {type(e).__name__}: {e}", exc_info=True)
        return False

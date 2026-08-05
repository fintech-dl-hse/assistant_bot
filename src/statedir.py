"""Resolution of the assistant_bot state directory.

Runtime state (quiz progress, users, private-message log, bot config) used to
live right in the git working tree, which is also the directory the auto-update
timer runs `git pull` in. It now lives in a single directory outside the
checkout so it can be backed up and carried over to another server as one unit.

Resolution order:
    1. $ASSISTANT_BOT_STATE_DIR
    2. $XDG_STATE_HOME/assistant_bot
    3. ~/.local/state/assistant_bot

Files left over from the old layout are moved into the state directory on first
use, so an upgrade needs no manual migration.
"""

import os
import shutil
from pathlib import Path

SERVICE = "assistant_bot"

# Files that used to sit next to the code and now belong to the state directory.
LEGACY_FILES = (
    "bot_config.json",
    "quizzes.json",
    "quiz_state.json",
    "users.json",
    "private_messages.jsonl",
)


def state_dir() -> Path:
    """Return the state directory, creating it if needed."""
    override = os.getenv("ASSISTANT_BOT_STATE_DIR")
    if override:
        path = Path(override).expanduser()
    else:
        base = os.getenv("XDG_STATE_HOME") or Path.home() / ".local" / "state"
        path = Path(base).expanduser() / SERVICE
    path.mkdir(parents=True, exist_ok=True)
    return path


def state_path(name: str, legacy_dir: Path | None = None) -> str:
    """Return the path to a state file, migrating it from the old location once.

    Args:
        name: File name inside the state directory.
        legacy_dir: Where the file used to live; defaults to the process cwd,
            which for the systemd unit is the repository checkout.
    """
    target = state_dir() / name
    if target.exists():
        return str(target)

    legacy = (legacy_dir or Path.cwd()) / name
    if legacy.is_file() and legacy.resolve() != target.resolve():
        shutil.move(str(legacy), str(target))
    return str(target)

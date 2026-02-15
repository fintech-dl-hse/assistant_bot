import json
import logging
from pathlib import Path
from typing import Any, Dict


def _load_users(users_file: str) -> Dict[str, Any]:
    path = Path(users_file)
    if not path.exists():
        return {"users": {}}
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        if not isinstance(data, dict):
            return {"users": {}}
        users = data.get("users")
        if not isinstance(users, dict):
            users = {}
        return {"users": users}
    except Exception:
        logging.getLogger(__name__).warning(
            "Failed to load users file %s; using empty state",
            users_file,
            exc_info=True,
        )
        return {"users": {}}


def _save_users(users_file: str, data: Dict[str, Any]) -> None:
    path = Path(users_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")

    users = data.get("users")
    if not isinstance(users, dict):
        users = {}

    def _user_key_sort(k: str) -> tuple[int, int | str]:
        s = str(k)
        if s.lstrip("-").isdigit():
            return (0, int(s))
        return (1, s)

    normalized_users: Dict[str, Any] = {}
    for user_key in sorted(users.keys(), key=_user_key_sort):
        u = users.get(user_key)
        if not isinstance(u, dict):
            continue
        github_changes = u.get("github_changes")
        if not isinstance(github_changes, int) or github_changes < 0:
            github_changes = 0
        normalized_users[str(user_key)] = {
            "fio": str(u.get("fio") or "").strip(),
            "username": str(u.get("username") or "").strip(),
            "github": str(u.get("github") or "").strip(),
            "github_changes": github_changes,
        }

    payload = {"users": normalized_users}
    raw = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    tmp_path.write_text(raw, encoding="utf-8")
    tmp_path.replace(path)

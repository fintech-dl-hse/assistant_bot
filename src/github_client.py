"""
GitHub API client for repository existence, collaborators, and invitations.

Uses personal access token from environment:
  - GITHUB_TOKEN or GITHUB_ACCESS_TOKEN
"""
import logging
import os
import base64
from typing import Any, Dict, List, Optional, Tuple

import requests

GITHUB_API_BASE = "https://api.github.com"
API_VERSION = "2022-11-28"

_log = logging.getLogger(__name__)
_log.setLevel(logging.DEBUG)


def _get_token() -> Optional[str]:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GITHUB_ACCESS_TOKEN")
    if token and token.strip():
        return token.strip()
    return None


def _headers(token_override: Optional[str] = None) -> Dict[str, str]:
    h: Dict[str, str] = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": API_VERSION,
    }
    token = (token_override or "").strip() or _get_token()
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def user_exists(username: str) -> bool:
    """
    Check if a GitHub user exists.

    Args:
        username: GitHub username to check.

    Returns:
        True if GET /users/{username} returns 200, False for 404 or on error.
    """
    username = (username or "").strip().lstrip("@")
    if not username:
        return False

    url = f"{GITHUB_API_BASE}/users/{username}"
    _log.debug("Checking user exists: %s", username)
    try:
        resp = requests.get(url, headers=_headers(), timeout=10)
        _log.debug("GitHub API %s -> %s for user %s", url, resp.status_code, username)
        if resp.status_code == 200:
            return True
        if resp.status_code == 404:
            return False
        _log.warning(
            "GitHub API %s returned %s for user %s",
            url,
            resp.status_code,
            username,
        )
        return False
    except Exception:
        _log.warning(
            "Failed to check user %s",
            username,
            exc_info=True,
        )
        return False


def repo_exists(owner: str, repo: str) -> bool:
    """
    Check if a GitHub repository exists (and is accessible with the configured token).

    Args:
        owner: Repository owner (organization or user).
        repo: Repository name.

    Returns:
        True if GET /repos/{owner}/{repo} returns 200, False for 404 or on error.
    """
    owner = (owner or "").strip()
    repo = (repo or "").strip()
    if not owner or not repo:
        return False

    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}"
    _log.debug("Checking repo exists: %s/%s", owner, repo)
    try:
        resp = requests.get(url, headers=_headers(), timeout=10)
        _log.debug("GitHub API %s -> %s for %s/%s", url, resp.status_code, owner, repo)
        if resp.status_code == 200:
            return True
        if resp.status_code == 404:
            return False
        _log.warning(
            "GitHub API %s returned %s for %s/%s",
            url,
            resp.status_code,
            owner,
            repo,
        )
        return False
    except Exception:
        _log.warning(
            "Failed to check repo %s/%s",
            owner,
            repo,
            exc_info=True,
        )
        return False


def get_repo_contents(owner: str, repo: str, path: str, token_override: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
    """
    GET /repos/{owner}/{repo}/contents/{path}. Returns list of items (files/dirs) or None on error.
    """
    owner = (owner or "").strip()
    repo = (repo or "").strip()
    path = (path or "").strip().strip("/")
    if not owner or not repo:
        return None
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{path}"
    try:
        resp = requests.get(url, headers=_headers(token_override), timeout=10)
        if resp.status_code != 200:
            _log.warning("GitHub API %s -> %s, body=%s", url, resp.status_code, (resp.text[:500] if resp.text else ""))
            return None
        data = resp.json()
        return data if isinstance(data, list) else None
    except Exception:
        _log.warning("Failed to get repo contents %s/%s/%s", owner, repo, path, exc_info=True)
        return None


def get_file(owner: str, repo: str, path: str, token_override: Optional[str] = None) -> Optional[Tuple[str, str]]:
    """
    GET /repos/{owner}/{repo}/contents/{path} for a single file.
    Returns (decoded_content, sha) or None on error.
    """
    owner = (owner or "").strip()
    repo = (repo or "").strip()
    path = (path or "").strip().strip("/")
    if not owner or not repo or not path:
        return None
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{path}"
    try:
        resp = requests.get(url, headers=_headers(token_override), timeout=10)
        if resp.status_code != 200:
            _log.warning("GitHub API %s -> %s, body=%s", url, resp.status_code, (resp.text[:500] if resp.text else ""))
            return None
        data = resp.json()
        if not isinstance(data, dict):
            return None
        content_b64 = data.get("content")
        sha = (data.get("sha") or "").strip()
        if not sha or not content_b64:
            return None
        content_b64_clean = "".join(c for c in content_b64 if c not in "\n\r ")
        try:
            decoded = base64.b64decode(content_b64_clean).decode("utf-8")
        except Exception:
            _log.warning("Failed to decode file content %s/%s/%s", owner, repo, path, exc_info=True)
            return None
        return (decoded, sha)
    except Exception:
        _log.warning("Failed to get file %s/%s/%s", owner, repo, path, exc_info=True)
        return None


def update_file(
    owner: str,
    repo: str,
    path: str,
    content: str,
    sha: str,
    message: str,
    token_override: Optional[str] = None,
) -> bool:
    """
    PUT /repos/{owner}/{repo}/contents/{path} to update a file.
    Returns True on 200.
    """
    owner = (owner or "").strip()
    repo = (repo or "").strip()
    path = (path or "").strip().strip("/")
    if not owner or not repo or not path or not sha or not message:
        return False
    try:
        content_b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")
    except Exception:
        _log.warning("Failed to encode content for %s/%s/%s", owner, repo, path, exc_info=True)
        return False
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{path}"
    try:
        resp = requests.put(
            url,
            headers=_headers(token_override),
            json={"message": message, "content": content_b64, "sha": sha},
            timeout=15,
        )
        _log.debug("GitHub API PUT %s -> %s", url, resp.status_code)
        if resp.status_code != 200:
            _log.warning("GitHub API PUT %s -> %s, body=%s", url, resp.status_code, (resp.text[:500] if resp.text else ""))
            return False
        return True
    except Exception:
        _log.warning("Failed to update file %s/%s/%s", owner, repo, path, exc_info=True)
        return False


def get_latest_seminar_notebook_path(
    owner: str,
    repo: str,
    branch: str,
    seminars_path: str,
    token_override: Optional[str] = None,
) -> Optional[str]:
    """
    Список ноутбуков в seminars и путь к последнему по имени (например seminars/04_cnn/04_seminar_cnn.ipynb).
    """
    items = get_repo_contents(owner, repo, seminars_path, token_override)
    if not isinstance(items, list):
        return None
    notebook_paths: List[str] = []
    for item in items:
        if not isinstance(item, dict) or item.get("type") != "dir":
            continue
        name = (item.get("name") or "").strip()
        if not name or name.startswith(".") or name.startswith("_"):
            continue
        sub = get_repo_contents(owner, repo, f"{seminars_path}/{name}", token_override)
        if not isinstance(sub, list):
            _log.debug("teach/seminars: подпапка %s пуста или ошибка", name)
            continue
        for f in sub:
            if not isinstance(f, dict) or f.get("type") != "file":
                continue
            fn = (f.get("name") or "").strip()
            if fn.endswith(".ipynb"):
                notebook_paths.append(f"{seminars_path}/{name}/{fn}")
    if not notebook_paths:
        _log.warning("teach/seminars: в %s не найдено .ipynb", seminars_path)
        return None
    notebook_paths.sort()
    return notebook_paths[-1]


def get_latest_lecture_url(
    owner: str,
    repo: str,
    branch: str,
    lectures_path: str,
    token_override: Optional[str] = None,
) -> Optional[str]:
    """
    Список файлов в lectures, последний .pdf по имени; возвращает URL blob на GitHub.
    """
    items = get_repo_contents(owner, repo, lectures_path, token_override)
    if not isinstance(items, list):
        return None
    files: List[str] = []
    for item in items:
        if not isinstance(item, dict) or item.get("type") != "file":
            continue
        name = (item.get("name") or "").strip()
        if not name or name == "README.md" or not name.endswith(".pdf"):
            continue
        files.append(name)
    if not files:
        _log.warning("teach/lectures: в %s не найдено .pdf", lectures_path)
        return None
    files.sort()
    path = f"{lectures_path}/{files[-1]}"
    return f"https://github.com/{owner}/{repo}/blob/{branch}/{path}"


def is_collaborator(owner: str, repo: str, username: str) -> bool:
    """
    Check if a user is a repository collaborator.

    Args:
        owner: Repository owner.
        repo: Repository name.
        username: GitHub username to check.

    Returns:
        True if GET /repos/{owner}/{repo}/collaborators/{username} returns 204.
    """
    owner = (owner or "").strip()
    repo = (repo or "").strip()
    username = (username or "").strip().lstrip("@")
    if not owner or not repo or not username:
        return False

    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/collaborators/{username}"
    _log.debug("Checking collaborator %s on %s/%s", username, owner, repo)
    try:
        resp = requests.get(url, headers=_headers(), timeout=10)
        _log.debug("GitHub API %s -> %s", url, resp.status_code)
        return resp.status_code == 204
    except Exception:
        _log.warning(
            "Failed to check collaborator %s on %s/%s",
            username,
            owner,
            repo,
            exc_info=True,
        )
        return False


def list_repo_invitations(owner: str, repo: str) -> List[Dict[str, Any]]:
    """
    List repository invitations (pending collaborator invites).

    Args:
        owner: Repository owner.
        repo: Repository name.

    Returns:
        List of invitation objects (each has invitee.login, html_url, etc.).
    """
    owner = (owner or "").strip()
    repo = (repo or "").strip()
    if not owner or not repo:
        return []

    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/invitations"
    _log.debug("Listing invitations for %s/%s", owner, repo)
    try:
        resp = requests.get(url, headers=_headers(), timeout=10)
        _log.debug("GitHub API %s -> %s", url, resp.status_code)
        if resp.status_code != 200:
            return []
        data = resp.json()
        return data if isinstance(data, list) else []
    except Exception:
        _log.warning(
            "Failed to list invitations for %s/%s",
            owner,
            repo,
            exc_info=True,
        )
        return []


def add_collaborator(
    owner: str,
    repo: str,
    username: str,
    permission: str = "push",
) -> bool:
    """
    Add a repository collaborator (sends an invitation if not already a collaborator).

    Args:
        owner: Repository owner.
        repo: Repository name.
        username: GitHub username to invite.
        permission: push, pull, admin, maintain, triage.

    Returns:
        True if invitation was sent (201) or user already collaborator (204).
    """
    owner = (owner or "").strip()
    repo = (repo or "").strip()
    username = (username or "").strip().lstrip("@")
    if not owner or not repo or not username:
        return False

    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/collaborators/{username}"
    _log.debug("Adding collaborator %s to %s/%s", username, owner, repo)
    try:
        resp = requests.put(
            url,
            headers=_headers(),
            json={"permission": permission},
            timeout=10,
        )
        _log.debug("GitHub API PUT %s -> %s", url, resp.status_code)
        return resp.status_code in (201, 204)
    except Exception:
        _log.warning(
            "Failed to add collaborator %s to %s/%s",
            username,
            owner,
            repo,
            exc_info=True,
        )
        return False

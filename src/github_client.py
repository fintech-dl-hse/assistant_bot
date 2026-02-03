"""
GitHub API client for repository existence, collaborators, and invitations.

Uses personal access token from environment:
  - GITHUB_TOKEN or GITHUB_ACCESS_TOKEN
"""
import logging
import os
from typing import Any, Dict, List, Optional

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


def _headers() -> Dict[str, str]:
    h: Dict[str, str] = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": API_VERSION,
    }
    token = _get_token()
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


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

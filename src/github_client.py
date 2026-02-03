"""
GitHub API client for checking repository existence.

Uses personal access token from environment:
  - GITHUB_TOKEN or GITHUB_ACCESS_TOKEN
"""
import logging
import os
from typing import Optional

import requests

GITHUB_API_BASE = "https://api.github.com"

_log = logging.getLogger(__name__)
_log.setLevel(logging.DEBUG)


def _get_token() -> Optional[str]:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GITHUB_ACCESS_TOKEN")
    if token and token.strip():
        return token.strip()
    return None


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

    token = _get_token()
    headers: dict[str, str] = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}"
    _log.debug("Checking repo exists: %s/%s", owner, repo)
    try:
        resp = requests.get(url, headers=headers, timeout=10)
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

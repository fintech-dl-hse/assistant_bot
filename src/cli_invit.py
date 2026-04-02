"""
CLI tool to run /invit logic for a given GitHub nickname.

Usage:
    python src/cli_invit.py --github MariaTolkacheva
    python src/cli_invit.py --github MariaTolkacheva --hw hw-batchnorm
    python src/cli_invit.py --github MariaTolkacheva --dry-run
"""

import argparse
import json
import logging
import sys
from pathlib import Path

# Allow running from repo root or src/
sys.path.insert(0, str(Path(__file__).parent))

from github_client import (
    delete_repo_invitation as github_delete_repo_invitation,
    get_file as github_get_file,
    invite_collaborator as github_invite_collaborator,
    is_collaborator as github_is_collaborator,
    list_repo_invitations as github_list_repo_invitations,
    repo_exists as github_repo_exists,
)

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stderr,
)
_log = logging.getLogger("cli_invit")


def run(github_nick: str, hw_filter: str | None, dry_run: bool) -> None:
    hw_meta_path = "terraform/functions/grades/hw-meta.json"
    result = github_get_file(owner="fintech-dl-hse", repo="checkhw", path=hw_meta_path)
    if not result:
        print("ERROR: Could not load hw-meta.json from fintech-dl-hse/checkhw", file=sys.stderr)
        sys.exit(1)

    content, _ = result
    meta = json.loads(content)
    if not isinstance(meta, list):
        print("ERROR: hw-meta.json is not a list", file=sys.stderr)
        sys.exit(1)

    for entry in meta:
        if not isinstance(entry, dict):
            continue
        hw_id = str(entry.get("id") or "").strip()
        if not hw_id:
            continue
        if hw_filter and hw_id != hw_filter:
            continue

        stored_invite_link = (entry.get("classroom_invite_link") or "").strip() or None
        if not stored_invite_link:
            _log.debug("skip %s: no classroom_invite_link", hw_id)
            continue

        repo_template = (entry.get("repo_name_template") or "").strip() or (hw_id + "-{github_nickname}")
        full_name = repo_template.replace("{github_nickname}", github_nick)
        if "/" not in full_name:
            full_name = "fintech-dl-hse/" + full_name
        owner, repo = full_name.split("/", 1)

        print(f"\n=== {hw_id} ({owner}/{repo}) ===")

        exists = github_repo_exists(owner=owner, repo=repo)
        print(f"  repo exists:   {exists}")
        if not exists:
            print(f"  → classroom invite: {stored_invite_link}")
            continue

        is_collab = github_is_collaborator(owner=owner, repo=repo, username=github_nick)
        print(f"  is_collaborator: {is_collab}")
        if is_collab:
            print(f"  → already collaborator: https://github.com/{owner}/{repo}")
            continue

        invitations = github_list_repo_invitations(owner=owner, repo=repo)
        invite_for_user = next(
            (inv for inv in invitations if (inv.get("invitee") or {}).get("login", "").lower() == github_nick.lower()),
            None,
        )

        if invite_for_user:
            expired = invite_for_user.get("expired", False)
            inv_id = invite_for_user.get("id")
            html_url = invite_for_user.get("html_url", "")
            print(f"  invitation found: id={inv_id} expired={expired} html_url={html_url}")

            if not expired:
                print(f"  → pending invitation link: {html_url}")
                continue

            # Expired: delete and recreate
            print(f"  invitation is EXPIRED — {'(dry-run, skip)' if dry_run else 'deleting...'}")
            if not dry_run:
                deleted = github_delete_repo_invitation(owner=owner, repo=repo, invitation_id=inv_id)
                print(f"  delete result: {deleted}")
        else:
            print(f"  no invitation found for {github_nick}")

        if dry_run:
            print("  → (dry-run) would call invite_collaborator")
            continue

        fresh_url = github_invite_collaborator(owner=owner, repo=repo, username=github_nick)
        print(f"  invite_collaborator result: {fresh_url!r}")
        if fresh_url is None:
            print("  ERROR: failed to send invitation")
        elif fresh_url == "":
            print("  → user became collaborator (204)")
        else:
            print(f"  → new invitation link: {fresh_url}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run /invit logic for a GitHub user")
    parser.add_argument("--github", required=True, help="GitHub username")
    parser.add_argument("--hw", default=None, help="Filter to a specific hw-id (e.g. hw-batchnorm)")
    parser.add_argument("--dry-run", action="store_true", help="Do not delete or recreate invitations")
    args = parser.parse_args()

    github_nick = args.github.strip().lstrip("@")
    if not github_nick:
        print("ERROR: --github must be non-empty", file=sys.stderr)
        sys.exit(1)

    run(github_nick=github_nick, hw_filter=args.hw, dry_run=args.dry_run)


if __name__ == "__main__":
    main()

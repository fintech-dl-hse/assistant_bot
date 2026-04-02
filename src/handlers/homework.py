import json
import logging
from typing import Any, Dict

_log = logging.getLogger(__name__)

from context import BotContext
from data.users import _load_users
from text_format import (
    _escape_markdown_v2_plain,
    _format_deadline_ru,
    _hw_id_to_short_name,
    _md2_link,
    _points_russian,
    _send_with_formatting_fallback,
)

from github_client import (
    delete_repo_invitation as github_delete_repo_invitation,
    get_file as github_get_file,
    invite_collaborator as github_invite_collaborator,
    is_collaborator as github_is_collaborator,
    list_repo_invitations as github_list_repo_invitations,
    repo_exists as github_repo_exists,
    update_file as github_update_file,
)


def handle_invit(ctx: BotContext) -> None:
    users_data = _load_users(ctx.users_file)
    users = users_data.get("users")
    if not isinstance(users, dict):
        users = {}
    user_key = str(ctx.user_id)
    github_nick = (users.get(user_key) or {}).get("github") or ""
    github_nick = str(github_nick).strip().lstrip("@")
    if not github_nick:
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text="GitHub не привязан. Сначала привяжите: /github <nickname>",
        )
        return

    hw_meta_path = "terraform/functions/grades/hw-meta.json"
    result = github_get_file(owner="fintech-dl-hse", repo="checkhw", path=hw_meta_path)
    if not result:
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text="Не удалось загрузить список ДЗ (hw-meta.json из fintech-dl-hse/checkhw).",
        )
        return

    content, _ = result
    try:
        meta = json.loads(content)
    except Exception as e:
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text=f"Ошибка разбора hw-meta.json: {type(e).__name__}: {e}",
        )
        return

    if not isinstance(meta, list):
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text="hw-meta.json должен быть массивом.",
        )
        return

    rows: list[Dict[str, Any]] = []
    for entry in meta:
        if not isinstance(entry, dict):
            continue
        hw_id = str(entry.get("id") or "").strip()
        if not hw_id:
            continue
        stored_invite_link = (entry.get("classroom_invite_link") or "").strip() or None
        if not stored_invite_link:
            continue

        repo_template = (entry.get("repo_name_template") or "").strip() or (hw_id + "-{github_nickname}")
        full_name = repo_template.replace("{github_nickname}", github_nick)
        if "/" not in full_name:
            full_name = "fintech-dl-hse/" + full_name

        owner, repo = full_name.split("/", 1)
        owner = owner.strip()
        repo = repo.strip()
        if not owner or not repo:
            continue

        repo_url = f"https://github.com/{owner}/{repo}"
        exists = github_repo_exists(owner=owner, repo=repo)
        is_collab = github_is_collaborator(owner=owner, repo=repo, username=github_nick)

        link_url = repo_url
        if exists and is_collab:
            link_url = repo_url
        else:
            inv_link: str | None = None
            if not exists:
                inv_link = stored_invite_link
            else:
                invitations = github_list_repo_invitations(owner=owner, repo=repo)
                invite_for_user = next(
                    (
                        inv
                        for inv in invitations
                        if (inv.get("invitee") or {}).get("login", "").lower() == github_nick.lower()
                    ),
                    None,
                )
                if invite_for_user and not invite_for_user.get("expired"):
                    _log.debug(
                        "handle_invit: pending invitation found for %s on %s/%s: %s",
                        github_nick, owner, repo, invite_for_user.get("html_url"),
                    )
                    inv_link = repo_url + "/invitations"
                else:
                    if invite_for_user and invite_for_user.get("expired"):
                        inv_id = invite_for_user.get("id")
                        _log.debug(
                            "handle_invit: expired invitation id=%s for %s on %s/%s, deleting",
                            inv_id, github_nick, owner, repo,
                        )
                        github_delete_repo_invitation(owner=owner, repo=repo, invitation_id=inv_id)
                    fresh_url = github_invite_collaborator(owner=owner, repo=repo, username=github_nick)
                    _log.debug(
                        "handle_invit: recreated invitation for %s on %s/%s -> %s",
                        github_nick, owner, repo, fresh_url,
                    )
                    if fresh_url is None:
                        continue
                    inv_link = fresh_url or f"https://github.com/{owner}/{repo}/invitations"
            if inv_link:
                link_url = inv_link

        deadline_iso = str(entry.get("deadline") or "").strip()
        max_points = int(entry.get("max_points") or 0)
        is_bonus = bool(entry.get("bonus", False))
        rows.append({
            "hw_id": hw_id,
            "deadline": deadline_iso,
            "max_points": max_points,
            "bonus": is_bonus,
            "short_name": _hw_id_to_short_name(hw_id),
            "link_url": link_url,
        })

    rows.sort(key=lambda r: (r["bonus"], r["deadline"]))

    groups: list[tuple[bool, str, list[Dict[str, Any]]]] = []
    i = 0
    while i < len(rows):
        r0 = rows[i]
        bonus = r0["bonus"]
        deadline = r0["deadline"]
        group_rows = [r0]
        j = i + 1
        while j < len(rows) and rows[j]["bonus"] == bonus and rows[j]["deadline"] == deadline:
            group_rows.append(rows[j])
            j += 1
        groups.append((bonus, deadline, group_rows))
        i = j

    md_parts: list[str] = []
    for bonus, _deadline, group_rows in groups:
        if bonus:
            md_parts.append("*" + _escape_markdown_v2_plain("🎁 Бонусные домашки") + "*")
        else:
            section_title = " + ".join(r["short_name"] for r in group_rows)
            md_parts.append("*" + _escape_markdown_v2_plain("🟢 " + section_title) + "*")

        for r in group_rows:
            points_str = _points_russian(r["max_points"])
            deadline_str = _format_deadline_ru(r["deadline"])
            line_rest = _escape_markdown_v2_plain(f" [{points_str}] Дедлайн {deadline_str}")
            bold_link = "*" + _md2_link(r["hw_id"], r["link_url"]) + "*"
            if bonus:
                md_parts.append(_escape_markdown_v2_plain("🟢 ") + bold_link + line_rest)
            else:
                md_parts.append(bold_link + line_rest)

        md_parts.append("")

    header = _escape_markdown_v2_plain(f"GitHub: {github_nick}") + "\n\n"
    body = "\n".join(md_parts).rstrip()
    _send_with_formatting_fallback(
        tg=ctx.tg,
        chat_id=ctx.chat_id,
        message_thread_id=ctx.message_thread_id,
        text=header + body,
        markdown_v2_raw=True,
    )


def handle_hw_pin(ctx: BotContext) -> None:
    if not ctx.is_admin:
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text="Недостаточно прав: команда доступна только администраторам.",
        )
        return

    hw_meta_path = "terraform/functions/grades/hw-meta.json"
    result = github_get_file(owner="fintech-dl-hse", repo="checkhw", path=hw_meta_path)
    if not result:
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text="Не удалось загрузить список ДЗ (hw-meta.json из fintech-dl-hse/checkhw).",
        )
        return

    content, _ = result
    try:
        meta = json.loads(content)
    except Exception as e:
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text=f"Ошибка разбора hw-meta.json: {type(e).__name__}: {e}",
        )
        return

    if not isinstance(meta, list):
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text="hw-meta.json должен быть массивом.",
        )
        return

    rows_pin: list[Dict[str, Any]] = []
    for entry in meta:
        if not isinstance(entry, dict):
            continue
        hw_id = str(entry.get("id") or "").strip()
        if not hw_id:
            continue
        stored_invite_link = (entry.get("classroom_invite_link") or "").strip() or None
        if not stored_invite_link:
            continue

        deadline_iso = str(entry.get("deadline") or "").strip()
        max_points = int(entry.get("max_points") or 0)
        is_bonus = bool(entry.get("bonus", False))
        rows_pin.append({
            "hw_id": hw_id,
            "deadline": deadline_iso,
            "max_points": max_points,
            "bonus": is_bonus,
            "short_name": _hw_id_to_short_name(hw_id),
            "link_url": stored_invite_link,
        })

    rows_pin.sort(key=lambda r: (r["bonus"], r["deadline"]))

    groups_pin: list[tuple[bool, str, list[Dict[str, Any]]]] = []
    i = 0
    while i < len(rows_pin):
        r0 = rows_pin[i]
        bonus = r0["bonus"]
        deadline = r0["deadline"]
        group_rows = [r0]
        j = i + 1
        while j < len(rows_pin) and rows_pin[j]["bonus"] == bonus and rows_pin[j]["deadline"] == deadline:
            group_rows.append(rows_pin[j])
            j += 1
        groups_pin.append((bonus, deadline, group_rows))
        i = j

    md_parts_pin: list[str] = []
    for bonus, _deadline, group_rows in groups_pin:
        if bonus:
            md_parts_pin.append("*" + _escape_markdown_v2_plain("🎁 Бонусные домашки") + "*")
        else:
            section_title = " + ".join(r["short_name"] for r in group_rows)
            md_parts_pin.append("*" + _escape_markdown_v2_plain("🟢 " + section_title) + "*")

        for r in group_rows:
            points_str = _points_russian(r["max_points"])
            deadline_str = _format_deadline_ru(r["deadline"])
            line_rest = _escape_markdown_v2_plain(f" [{points_str}] Дедлайн {deadline_str}")
            bold_link = "*" + _md2_link(r["hw_id"], r["link_url"]) + "*"
            if bonus:
                md_parts_pin.append(_escape_markdown_v2_plain("🟢 ") + bold_link + line_rest)
            else:
                md_parts_pin.append(bold_link + line_rest)

        md_parts_pin.append("")

    body_pin = "\n".join(md_parts_pin).rstrip()
    _send_with_formatting_fallback(
        tg=ctx.tg,
        chat_id=ctx.chat_id,
        message_thread_id=ctx.message_thread_id,
        text=body_pin,
        markdown_v2_raw=True,
    )


def handle_hw_invite(ctx: BotContext) -> None:
    if not ctx.is_admin:
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text="Недостаточно прав: команда доступна только администраторам.",
        )
        return

    parts = (ctx.args or "").strip().split(maxsplit=1)
    if len(parts) < 2:
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text="Usage: /hw_invite <hw-slug> <github_classrooms_invite_link>",
        )
        return

    hw_slug = (parts[0] or "").strip()
    invite_link = (parts[1] or "").strip()
    if not hw_slug or not invite_link:
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text="Usage: /hw_invite <hw-slug> <github_classrooms_invite_link>",
        )
        return

    hw_meta_path = "terraform/functions/grades/hw-meta.json"
    result = github_get_file(owner="fintech-dl-hse", repo="checkhw", path=hw_meta_path)
    if not result:
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text="Не удалось прочитать hw-meta.json из репозитория fintech-dl-hse/checkhw.",
        )
        return

    content, sha = result
    try:
        meta = json.loads(content)
    except Exception as e:
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text=f"Ошибка разбора JSON: {type(e).__name__}: {e}",
        )
        return

    if not isinstance(meta, list):
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text="hw-meta.json должен быть массивом объектов.",
        )
        return

    found = False
    for entry in meta:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("id") or "").strip() == hw_slug:
            entry["classroom_invite_link"] = invite_link
            found = True
            break

    if not found:
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text=f"Домашнее задание с id '{hw_slug}' не найдено в hw-meta.json.",
        )
        return

    new_content = json.dumps(meta, ensure_ascii=False, indent=2) + "\n"
    commit_ok = github_update_file(
        owner="fintech-dl-hse",
        repo="checkhw",
        path=hw_meta_path,
        content=new_content,
        sha=sha,
        message=f"hw_invite: set classroom_invite_link for {hw_slug}",
    )
    if not commit_ok:
        _send_with_formatting_fallback(
            tg=ctx.tg,
            chat_id=ctx.chat_id,
            message_thread_id=ctx.message_thread_id,
            text="Не удалось записать изменения в репозиторий fintech-dl-hse/checkhw.",
        )
        return

    _send_with_formatting_fallback(
        tg=ctx.tg,
        chat_id=ctx.chat_id,
        message_thread_id=ctx.message_thread_id,
        text=f"Готово. Для {hw_slug} записан classroom_invite_link в hw-meta.json.",
    )

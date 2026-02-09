"""
Google Drive API client: копирование формы обратной связи из папки-шаблона
с сохранением прав доступа.

Требует: service account JSON (конфиг или GOOGLE_APPLICATION_CREDENTIALS).

Важно: копия создаётся в Drive сервисного аккаунта и учитывается в его квоте (~15 GB).
При 403 storageQuotaExceeded нужно удалить старые файлы в Drive аккаунта или
использовать Shared Drive (копии в нём не тратят квоту сервисного аккаунта).
"""
import json
import logging
import os
from typing import Any, Optional

_log = logging.getLogger(__name__)


class DriveStorageQuotaExceeded(Exception):
    """Квота хранилища Drive сервисного аккаунта исчерпана (403 storageQuotaExceeded)."""

# MIME type Google Form
GOOGLE_FORM_MIME = "application/vnd.google-apps.form"


def _get_credentials_path(settings: dict[str, Any]) -> Optional[str]:
    path = (settings.get("drive_credentials_path") or "").strip()
    if path and os.path.isfile(path):
        return path
    path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    if path and os.path.isfile(path):
        return path
    return None


def copy_feedback_form(
    folder_id: str,
    new_title: str,
    credentials_path: str,
) -> Optional[tuple[str, str]]:
    """
    Клонирует первый найденный Google Form из папки Drive с новым названием.
    Копирует права доступа с шаблона на новую форму.

    Args:
        folder_id: ID папки в Google Drive (из URL папки).
        new_title: Название копии (например "[DL26] 4 неделя").
        credentials_path: Путь к JSON ключу service account.

    Returns:
        (edit_url, view_url) или None при ошибке.
        edit_url: ссылка на редактирование формы.
        view_url: ссылка для респондентов.
    """
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError
    except ImportError:
        _log.warning("Google Drive API not installed; install google-api-python-client google-auth")
        return None

    scopes = ["https://www.googleapis.com/auth/drive", "https://www.googleapis.com/auth/drive.file"]
    try:
        creds = service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=scopes,
        )
    except Exception as e:
        _log.warning("Failed to load Drive credentials from %s: %s", credentials_path, e)
        return None

    service = build("drive", "v3", credentials=creds, cache_discovery=False)

    # Найти первый Form в папке
    try:
        list_result = (
            service.files()
            .list(
                q=f"'{folder_id}' in parents and mimeType='{GOOGLE_FORM_MIME}' and trashed=false",
                pageSize=1,
                fields="files(id, name)",
                supportsAllDrives=True,
            )
            .execute()
        )
    except HttpError as e:
        _log.warning("Drive list failed: %s", e)
        return None

    files = list_result.get("files", [])
    if not files:
        _log.warning("No form template found in folder %s", folder_id)
        return None

    template_id = files[0]["id"]

    # Копировать файл в ту же папку (копия учитывается в квоте сервисного аккаунта)
    try:
        copy_result = (
            service.files()
            .copy(
                fileId=template_id,
                body={
                    "name": new_title,
                },
            )
            .execute()
        )
    except HttpError as e:
        if e.resp.status == 403 and getattr(e, "content", None):
            try:
                err_body = json.loads(e.content.decode("utf-8"))
                reason = (err_body.get("error") or {}).get("errors") or []
                if reason and (reason[0].get("reason") == "storageQuotaExceeded"):
                    _log.warning(
                        "Drive copy failed: storage quota exceeded. "
                        "The service account's Drive is full. Delete old files or use a Shared Drive."
                    )
                    raise DriveStorageQuotaExceeded from e
            except (ValueError, KeyError, IndexError):
                pass
        _log.warning("Drive copy failed: %s", e)
        return None

    new_id = copy_result.get("id")
    if not new_id:
        return None

    # Скопировать права с шаблона на копию (кроме owner)
    try:
        perm_list = (
            service.permissions()
            .list(
                fileId=template_id,
                fields="permissions(id, type, role, emailAddress, domain)",
                supportsAllDrives=True,
            )
            .execute()
        )
    except HttpError as e:
        _log.debug("Could not list template permissions: %s; copy is still created", e)
        return _form_urls(new_id)

    for p in perm_list.get("permissions", []):
        role = (p.get("role") or "").strip().lower()
        if role == "owner":
            continue
        ptype = (p.get("type") or "").strip().lower()
        body: dict[str, Any] = {"role": p.get("role"), "type": ptype}
        if ptype in ("user", "group") and p.get("emailAddress"):
            body["emailAddress"] = p.get("emailAddress")
        elif ptype == "domain" and p.get("domain"):
            body["domain"] = p.get("domain")
        try:
            service.permissions().create(
                fileId=new_id,
                body=body,
                supportsAllDrives=True,
            ).execute()
        except HttpError as e:
            _log.debug("Could not copy permission %s to new form: %s", p.get("id"), e)

    return _form_urls(new_id)


def _form_urls(file_id: str) -> tuple[str, str]:
    edit_url = f"https://docs.google.com/forms/d/{file_id}/edit"
    view_url = f"https://docs.google.com/forms/d/{file_id}/viewform"
    return (edit_url, view_url)

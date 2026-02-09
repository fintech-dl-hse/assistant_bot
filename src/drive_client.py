"""
Google Drive/Forms API: создание новой формы обратной связи и настройка доступа.

Создаёт новую пустую форму через Forms API (без копирования), при необходимости
переносит её в папку и копирует права доступа с шаблона из этой папки.

Требует: service account JSON (конфиг или GOOGLE_APPLICATION_CREDENTIALS).
"""
import logging
import os
from typing import Any, Optional

_log = logging.getLogger(__name__)

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
    Создаёт новую пустую Google Form с заданным названием через Forms API.
    При необходимости переносит форму в папку и копирует права с шаблона из папки.

    Args:
        folder_id: ID папки в Google Drive (для копирования прав с шаблона и опционально для переноса).
        new_title: Название формы (например "[DL26] 4 неделя").
        credentials_path: Путь к JSON ключу service account.

    Returns:
        (edit_url, view_url) или None при ошибке.
    """
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError
    except ImportError:
        _log.warning("Google API not installed; install google-api-python-client google-auth")
        return None

    scopes = [
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/forms.body",
    ]
    try:
        creds = service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=scopes,
        )
    except Exception as e:
        _log.warning("Failed to load credentials from %s: %s", credentials_path, e)
        return None

    # Создать новую пустую форму через Forms API
    try:
        form_service = build("forms", "v1", credentials=creds, cache_discovery=False)
        new_form = {"info": {"title": new_title}}
        created = form_service.forms().create(body=new_form).execute()
        new_id = created.get("formId")
    except HttpError as e:
        _log.warning("Forms API create failed: %s", e)
        return None
    if not new_id:
        return None

    drive_service = build("drive", "v3", credentials=creds, cache_discovery=False)

    # Опционально: перенести форму в папку (addParents)
    try:
        drive_service.files().update(
            fileId=new_id,
            addParents=folder_id,
            supportsAllDrives=True,
        ).execute()
    except HttpError as e:
        _log.debug("Could not add form to folder %s: %s", folder_id, e)

    # Найти шаблон в папке и скопировать с него права доступа
    try:
        list_result = (
            drive_service.files()
            .list(
                q=f"'{folder_id}' in parents and mimeType='{GOOGLE_FORM_MIME}' and trashed=false",
                pageSize=1,
                fields="files(id)",
                supportsAllDrives=True,
            )
            .execute()
        )
        files = list_result.get("files", [])
        template_id = files[0]["id"] if files else None
    except HttpError as e:
        _log.debug("Could not list folder for template: %s", e)
        template_id = None

    if template_id and template_id != new_id:
        try:
            perm_list = (
                drive_service.permissions()
                .list(
                    fileId=template_id,
                    fields="permissions(id, type, role, emailAddress, domain)",
                    supportsAllDrives=True,
                )
                .execute()
            )
        except HttpError as e:
            _log.debug("Could not list template permissions: %s", e)
            perm_list = None
        if perm_list:
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
                    drive_service.permissions().create(
                        fileId=new_id,
                        body=body,
                        supportsAllDrives=True,
                    ).execute()
                except HttpError as e:
                    _log.debug("Could not copy permission to new form: %s", e)

    return _form_urls(new_id)


def _form_urls(file_id: str) -> tuple[str, str]:
    edit_url = f"https://docs.google.com/forms/d/{file_id}/edit"
    view_url = f"https://docs.google.com/forms/d/{file_id}/viewform"
    return (edit_url, view_url)

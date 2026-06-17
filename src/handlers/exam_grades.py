import csv
import io
import logging
import os
from typing import List, Tuple

import requests

from context import BotContext
from fio import normalize_fio
from text_format import _send_with_formatting_fallback

_log = logging.getLogger(__name__)

FIO_COLUMN = "ФИО"
SUM_COLUMN = "Сумма баллов за экзамены"


def _send(ctx: BotContext, text: str) -> None:
    _send_with_formatting_fallback(
        tg=ctx.tg,
        chat_id=ctx.chat_id,
        message_thread_id=ctx.message_thread_id,
        text=text,
    )


def _parse_rows(text: str) -> Tuple[List[dict], int]:
    """Parse the exam CSV into [{fio: normalized, exam_sum: float}], returning skipped count."""
    sample = text[:4096]
    delimiter = ";" if sample.count(";") > sample.count(",") else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)

    rows: List[dict] = []
    skipped = 0
    for raw in reader:
        record = {(k or "").replace("﻿", "").strip(): (v or "").strip() for k, v in raw.items()}
        fio_raw = record.get(FIO_COLUMN)
        sum_raw = record.get(SUM_COLUMN)
        if not fio_raw or sum_raw in (None, ""):
            skipped += 1
            continue
        fio = normalize_fio(fio_raw)
        if not fio:
            skipped += 1
            continue
        try:
            exam_sum = float(sum_raw.replace(",", ".").replace(" ", ""))
        except ValueError:
            skipped += 1
            continue
        rows.append({"fio": fio, "exam_sum": exam_sum})

    return rows, skipped


def handle_upload_exam_grades(ctx: BotContext) -> None:
    if not ctx.is_admin:
        _send(ctx, "Недостаточно прав: команда доступна только администраторам.")
        return
    if ctx.chat_type != "private":
        _send(ctx, "Пожалуйста, используйте /upload_exam_grades в личных сообщениях с ботом.")
        return

    document = ctx.message.get("document") or {}
    file_id = document.get("file_id")
    if not file_id:
        _send(
            ctx,
            "Прикрепите CSV-файл с колонками 'ФИО' и 'Сумма баллов за экзамены' "
            "и добавьте к нему подпись /upload_exam_grades.",
        )
        return

    fn_url = ctx.settings.get("exam_grades_fn_url")
    token = os.environ.get("EXAM_GRADES_SECRET_TOKEN")
    if not fn_url or not token:
        _send(
            ctx,
            "Загрузка не настроена: нужны exam_grades_fn_url в конфиге и "
            "переменная окружения EXAM_GRADES_SECRET_TOKEN.",
        )
        return

    # Download the document from Telegram.
    try:
        meta = ctx.tg.get_file(file_id)
        file_path = (meta.get("result") or {}).get("file_path")
        if not file_path:
            raise ValueError("no file_path in getFile response")
        raw = ctx.tg.download_file(file_path)
    except Exception as e:
        _log.warning("exam grades download failed", exc_info=True)
        _send(ctx, f"Не удалось скачать файл: {e}")
        return

    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1251", errors="replace")

    rows, skipped = _parse_rows(text)
    if not rows:
        _send(
            ctx,
            "Не удалось разобрать ни одной строки. Проверьте, что в файле есть "
            "колонки 'ФИО' и 'Сумма баллов за экзамены'.",
        )
        return

    # Hand off to the YC writer function (truncate + replace) over HTTP with the token.
    try:
        resp = requests.post(fn_url, params={"token": token}, json={"rows": rows}, timeout=30)
    except Exception as e:
        _log.warning("exam grades function call failed", exc_info=True)
        _send(ctx, f"Ошибка вызова функции сохранения: {e}")
        return

    if resp.status_code != 200:
        _send(ctx, f"Функция сохранения вернула ошибку {resp.status_code}: {resp.text[:200]}")
        return

    try:
        written = int((resp.json() or {}).get("written", len(rows)))
    except Exception:
        written = len(rows)

    _send(
        ctx,
        "Оценки за экзамен обновлены.\n"
        f"Разобрано строк: {len(rows)}\n"
        f"Записано в таблицу: {written}\n"
        f"Пропущено (некорректные строки): {skipped}",
    )

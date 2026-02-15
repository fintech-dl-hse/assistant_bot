import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


# In-memory wizard state for quiz creation (keyed by admin user_id)
_QUIZ_WIZARD_STATE: dict[int, Dict[str, Any]] = {}


def _quiz_sort_key(q: Dict[str, Any]) -> tuple[int, int | str]:
    qid = q.get("id")
    if isinstance(qid, int):
        return (0, qid)
    if isinstance(qid, str):
        s = qid.strip()
        if s.lstrip("-").isdigit():
            return (0, int(s))
        return (1, s)
    return (1, str(qid))


def _load_quizzes(quizzes_file: str) -> list[Dict[str, Any]]:
    path = Path(quizzes_file)
    if not path.exists():
        return []
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        if not isinstance(data, list):
            return []
        quizzes: list[Dict[str, Any]] = []
        for item in data:
            if isinstance(item, dict) and "id" in item:
                quiz = dict(item)
                if "processed" not in quiz:
                    quiz["processed"] = False
                quiz["processed"] = bool(quiz.get("processed"))
                if "hidden" not in quiz:
                    quiz["hidden"] = False
                quiz["hidden"] = bool(quiz.get("hidden"))
                quizzes.append(quiz)
        return quizzes
    except Exception:
        logging.getLogger(__name__).warning(
            "Failed to load quizzes file %s; using empty list",
            quizzes_file,
            exc_info=True,
        )
        return []


def _save_quizzes(quizzes_file: str, quizzes: list[Dict[str, Any]]) -> None:
    path = Path(quizzes_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    normalized: list[Dict[str, Any]] = []
    for q in list(quizzes):
        if not isinstance(q, dict):
            continue
        normalized.append(
            {
                "id": q.get("id"),
                "question": q.get("question"),
                "answer": q.get("answer"),
                "processed": bool(q.get("processed")),
                "hidden": bool(q.get("hidden")),
            }
        )
    raw = json.dumps(normalized, ensure_ascii=False, indent=2) + "\n"
    tmp_path.write_text(raw, encoding="utf-8")
    tmp_path.replace(path)


def _is_hidden_quiz(q: Dict[str, Any]) -> bool:
    return bool((q or {}).get("hidden"))

def _load_quiz_state(quiz_state_file: str) -> Dict[str, Any]:
    path = Path(quiz_state_file)
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
            "Failed to load quiz state file %s; using empty state",
            quiz_state_file,
            exc_info=True,
        )
        return {"users": {}}


def _save_quiz_state(quiz_state_file: str, state: Dict[str, Any]) -> None:
    path = Path(quiz_state_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")

    users = state.get("users")
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
        active_quiz_id = u.get("active_quiz_id")
        if active_quiz_id is not None:
            active_quiz_id = str(active_quiz_id)

        results = u.get("results")
        if not isinstance(results, dict):
            results = {}
        norm_results: Dict[str, Any] = {}
        for qid in sorted(results.keys(), key=_user_key_sort):
            r = results.get(qid)
            if not isinstance(r, dict):
                continue
            norm_results[str(qid)] = {
                "correct": bool(r.get("correct")),
                "attempts": int(r.get("attempts") or 0),
            }

        answers = u.get("answers")
        if not isinstance(answers, dict):
            answers = {}
        norm_answers: Dict[str, Any] = {}
        for qid in sorted(answers.keys(), key=_user_key_sort):
            arr = answers.get(qid)
            if not isinstance(arr, list):
                continue
            norm_answers[str(qid)] = [
                {
                    "answer": str(a.get("answer") or "") if isinstance(a, dict) else str(a),
                    "ts": str(a.get("ts") or "") if isinstance(a, dict) else "",
                    "correct": bool(a.get("correct")) if isinstance(a, dict) else False,
                }
                for a in arr
                if isinstance(a, (dict, str))
            ]

        normalized_users[str(user_key)] = {
            "active_quiz_id": active_quiz_id,
            "results": norm_results,
            "answers": norm_answers,
        }

    payload = {"users": normalized_users}
    raw = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    tmp_path.write_text(raw, encoding="utf-8")
    tmp_path.replace(path)


def _get_user_quiz_state(state: Dict[str, Any], user_id: int) -> Dict[str, Any]:
    users = state.get("users")
    if not isinstance(users, dict):
        users = {}
        state["users"] = users
    key = str(int(user_id))
    u = users.get(key)
    if not isinstance(u, dict):
        u = {"active_quiz_id": None, "results": {}, "answers": {}}
        users[key] = u
    if "results" not in u or not isinstance(u.get("results"), dict):
        u["results"] = {}
    if "answers" not in u or not isinstance(u.get("answers"), dict):
        u["answers"] = {}
    if "active_quiz_id" not in u:
        u["active_quiz_id"] = None
    return u


def _append_user_answer(
    user_state: Dict[str, Any],
    quiz_id: str,
    answer: str,
    is_correct: bool,
) -> None:
    answers = user_state.get("answers")
    if not isinstance(answers, dict):
        answers = {}
        user_state["answers"] = answers
    qkey = str(quiz_id)
    arr = answers.get(qkey)
    if not isinstance(arr, list):
        arr = []
        answers[qkey] = arr
    arr.append(
        {
            "answer": answer,
            "ts": datetime.now(timezone.utc).isoformat(),
            "correct": bool(is_correct),
        }
    )

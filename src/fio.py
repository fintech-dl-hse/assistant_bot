def normalize_fio(value: str | None) -> str:
    """Canonical FIO form for exam-grade matching.

    Must stay byte-for-byte identical to the grades cloud function's
    normalize_fio (checkhw terraform/functions/grades/index.py), because the
    bot stores this form and the grades function matches against it by exact
    equality. Steps (order matters): drop '<'/'>' -> lowercase -> ё→е ->
    collapse whitespace. Word order is preserved.
    """
    if not value:
        return ""
    s = str(value)
    s = s.replace("<", "").replace(">", "")
    s = s.lower().replace("ё", "е")
    s = " ".join(s.split())
    return s

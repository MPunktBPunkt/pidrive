"""web/shared/errors.py — einmalige WARN-Protokollierung für stumme excepts (W1)."""
from __future__ import annotations

_seen: set = set()


def warn_once(key: str, message: str) -> None:
    """Loggt eine Warnung höchstens einmal pro Prozesslauf."""
    if key in _seen:
        return
    _seen.add(key)
    try:
        import log
        log.warn(message)
    except Exception:
        # Fallback ohne log-Modul (z. B. Selftest ohne Core-Pfad)
        import sys
        print(f"[WARN] {message}", file=sys.stderr)

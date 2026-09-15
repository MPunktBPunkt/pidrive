"""modules/degraded_imports.py — sichtbare Import-Ausfälle (W1)."""
from __future__ import annotations

_DEGRADED: list = []


def report(module: str, detail: str) -> None:
    entry = f"{module}: {detail}"
    if entry not in _DEGRADED:
        _DEGRADED.append(entry)
        try:
            import log
            log.warn(f"degraded_import: {entry}")
        except Exception:
            pass


def list_degraded() -> list:
    return list(_DEGRADED)

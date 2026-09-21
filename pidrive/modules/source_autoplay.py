"""
modules/source_autoplay.py — Quellenordner-Enter startet letzten Sender (Q-A…Q-C)
Aufrufer: trigger/td_nav.py (nur bei enter/right, nicht bei activate/goto/walk)
"""

from __future__ import annotations

from typing import Any, Optional

import log
from modules import source_state


def resolve_station(source: str, settings: dict, store) -> Optional[dict]:
    """Erste Wahl / Rückfall laut Auftrag §2.3. None = nicht starten."""
    src = (source or "").lower().strip()
    if src == "fm":
        st = settings.get("last_fm_station") if settings else None
        if isinstance(st, dict) and st.get("freq"):
            return dict(st)
        freq = (settings or {}).get("fm_freq") or "98.5"
        return {"name": f"{freq} MHz", "freq": str(freq)}
    if src == "dab":
        st = settings.get("last_dab_station") if settings else None
        if isinstance(st, dict) and st.get("name"):
            return dict(st)
        return None
    if src in ("webradio", "web"):
        st = settings.get("last_web_station") if settings else None
        if isinstance(st, dict) and st.get("url"):
            return dict(st)
        stations = getattr(store, "web", None) or []
        if stations:
            first = stations[0]
            if isinstance(first, dict) and first.get("url"):
                return dict(first)
        return None
    return None


def should_autoplay(source: str) -> bool:
    """Nur starten, wenn diese Quelle nicht schon läuft (§2.2)."""
    cur = (source_state.current_source() or "idle").lower()
    want = (source or "").lower().strip()
    if want == "web":
        want = "webradio"
    if want == "webradio" and cur == "web":
        return False
    return cur != want


def run_autoplay(source: str, S: dict, settings: dict, store,
                 stop_all, begin_guard=None, end_guard=None) -> bool:
    """
    Normaler Quellenwechsel: stop → play → commit nur bei Erfolg (§2.4).
    Gibt True zurück wenn Wiedergabe gestartet wurde.
    """
    src = (source or "").lower().strip()
    if src == "web":
        src = "webradio"
    if src not in ("fm", "dab", "webradio"):
        return False
    if not should_autoplay(src):
        log.info(f"autoplay skip: already {source_state.current_source()}")
        return False

    station = resolve_station(src, settings, store)
    if not station:
        log.info(f"autoplay skip: no station for {src}")
        return False

    owner = "menu_autoplay"
    if begin_guard is not None:
        try:
            allowed = begin_guard(owner=owner, blocking=False)
        except TypeError:
            allowed = begin_guard(owner)
        if not allowed:
            log.warn(f"autoplay blocked by switch guard source={src}")
            return False
    if not source_state.begin_transition(owner, src):
        if end_guard:
            end_guard()
        return False

    ok = False
    try:
        stop_all()
        if src == "fm":
            from modules.radio import fm
            ok = fm.play_station(station, S, settings) is not False
            if ok:
                source_state.commit_source("fm")
        elif src == "dab":
            from modules.radio import dab
            name = station.get("name", "")
            sid = station.get("service_id", "")
            result = dab.play_by_name(name, S, settings=settings, service_id=sid)
            if result is not None:
                source_state.commit_source("dab")
                ok = True
        elif src == "webradio":
            from modules import webradio
            ok = webradio.play_station(station, S, settings) is not False
            if ok:
                source_state.commit_source("webradio")
    except Exception as e:
        log.error(f"autoplay {src} error: {e}")
        ok = False
    finally:
        if end_guard:
            end_guard()
        source_state.end_transition()
    return ok

#!/usr/bin/env python3
"""idrive_sim.py — AVRCP-Event-Ebene simulieren (M6), inkl. Skript-Runner."""

from __future__ import annotations

import os
import sys
import time
import json
from typing import List, Optional, Tuple

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

_EVENT_ALIASES = {
    "next": "next",
    "previous": "previous",
    "prev": "previous",
    "play": "play",
    "pause": "pause",
    "play_pause": "play_pause",
    "stop": "stop",
    "vol_up": "volumeup",
    "volume_up": "volumeup",
    "volumeup": "volumeup",
    "vol_down": "volumedown",
    "volume_down": "volumedown",
    "volumedown": "volumedown",
    "fast_forward": "fast_forward",
    "rewind": "rewind",
}

VALID_EVENTS = sorted(set(_EVENT_ALIASES) | set(_EVENT_ALIASES.values()))

_offline_state = None  # MenuState
_offline_last_enter = 0.0
# Q-G: simuliert D3 — fm_manual klaut Tastendrücke (freq_input_screen)
_offline_modal = False


def normalize_event(name: str) -> str:
    key = name.strip().lower()
    if key not in _EVENT_ALIASES:
        raise ValueError(f"Unbekanntes Event: {name!r}. Gültig: {', '.join(VALID_EVENTS)}")
    return _EVENT_ALIASES[key]


def reset_offline_state():
    global _offline_state, _offline_last_enter, _offline_modal
    _offline_state = None
    _offline_last_enter = 0.0
    _offline_modal = False


def _get_offline_state():
    global _offline_state
    if _offline_state is None:
        from menu.menu_golden import build_reference_tree
        from menu.menu_state import MenuState
        _offline_state = MenuState(build_reference_tree())
    return _offline_state


def inject_event(event: str, source: str = "idrive_sim", require_ready: bool = True) -> dict:
    """Event-Ebene wie avrcp_trigger.handle_avrcp (live → /tmp/pidrive_cmd)."""
    from integration import avrcp_trigger as av

    canon = normalize_event(event)
    ready = os.path.exists(av.READY_FILE)
    if require_ready and not ready:
        return {"ok": False, "event": canon, "error": f"PiDrive nicht bereit (kein {av.READY_FILE})"}

    before = time.time()
    av.handle_avrcp(canon, source=source, raw_line=f"idrive {canon}")
    ctx = av.get_context()
    return {
        "ok": True,
        "event": canon,
        "context": ctx.get("context"),
        "trigger": av.map_event(canon, ctx),
        "menu_path": ctx.get("menu", {}).get("path", []),
        "ms": int((time.time() - before) * 1000),
    }


def offline_apply(event: str, source: str = "idrive_offline") -> dict:
    """Ohne Core: map_event im Menü-Kontext + lokales MenuState."""
    global _offline_last_enter, _offline_modal
    from integration.avrcp_trigger import map_event

    state = _get_offline_state()
    ctx = {"context": "menu", "status": {}, "menu": state.export(), "list": {}, "band": ""}
    canon = normalize_event(event)

    # D3-Nachbildung: modale FM-Frequenzeingabe schluckt Events (kein Menü-Cursor)
    if _offline_modal:
        sel = state.selected
        return {
            "ok": True,
            "offline": True,
            "event": canon,
            "context": "menu",
            "trigger": "modal_swallowed",
            "applied": "modal_swallowed",
            "menu_path": list(state.path),
            "selected": sel.label if sel else None,
            "selected_path_id": sel.path_id if sel else None,
            "selected_type": sel.type if sel else None,
            "activated_id": None,
            "activated_label": None,
            "source": source,
        }

    now = time.time()
    trigger = None
    if canon in ("play", "pause", "play_pause"):
        if now - _offline_last_enter < 1.2:
            trigger = "cat:0"
            _offline_last_enter = 0.0
        else:
            _offline_last_enter = now
            trigger = map_event(canon, ctx)
    else:
        trigger = map_event(canon, ctx)

    applied = None
    activated = None
    if trigger == "down":
        state.key_down(); applied = "down"
    elif trigger == "up":
        state.key_up(); applied = "up"
    elif trigger == "enter":
        node = state.key_enter()
        applied = "enter"
        if node and node.type in ("station", "action", "toggle"):
            activated = node
            applied = f"activate:{node.id}"
            # Q-G: fm_manual startet freq_input_screen → Events gehen verloren
            if getattr(node, "id", "") == "fm_manual" or getattr(node, "action", "") == "fm_manual":
                _offline_modal = True
    elif trigger == "back":
        state.key_back(); applied = "back"
    elif trigger == "cat:0":
        state.navigate_to("0"); applied = "cat:0"
    elif trigger:
        applied = f"unhandled:{trigger}"

    sel = state.selected
    return {
        "ok": True,
        "offline": True,
        "event": canon,
        "context": "menu",
        "trigger": trigger,
        "applied": applied,
        "menu_path": list(state.path),
        "selected": sel.label if sel else None,
        "selected_path_id": sel.path_id if sel else None,
        "selected_type": sel.type if sel else None,
        "activated_id": activated.id if activated else None,
        "activated_label": activated.label if activated else None,
        "source": source,
    }


def parse_script(path: str) -> List[Tuple[str, Optional[str]]]:
    steps = []
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("sleep "):
                steps.append(("sleep", line.split(None, 1)[1].strip()))
            elif line.startswith("expect "):
                steps.append(("expect", line.split(None, 1)[1].strip()))
            elif line == "reset":
                steps.append(("reset", None))
            else:
                normalize_event(line.split()[0])
                steps.append(("event", line.split()[0]))
    return steps


def _read_status() -> dict:
    try:
        with open("/tmp/pidrive_status.json", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _read_menu() -> dict:
    try:
        with open("/tmp/pidrive_menu.json", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def check_expect(expr: str, offline_result: Optional[dict] = None) -> Tuple[bool, str]:
    if "=" not in expr:
        return False, f"expect braucht key=value: {expr}"
    key, val = expr.split("=", 1)
    key, val = key.strip(), val.strip()
    status = _read_status()
    menu = _read_menu()

    if offline_result and offline_result.get("offline"):
        if key == "selected":
            got = offline_result.get("selected") or ""
            return val.lower() in got.lower(), f"got={got!r}"
        if key in ("station", "activated"):
            got = offline_result.get("activated_label") or offline_result.get("selected") or ""
            return val.lower() in got.lower(), f"got={got!r}"
        if key == "path_contains":
            path = " / ".join(offline_result.get("menu_path") or [])
            return val in path, f"path={path!r}"
        if key == "selected_path_id":
            return (offline_result.get("selected_path_id") or "") == val, str(offline_result.get("selected_path_id"))
        if key == "selected_type":
            return (offline_result.get("selected_type") or "") == val, str(offline_result.get("selected_type"))
        if key == "radio_type":
            # Offline kann nicht spielen — als Hinweis markieren
            return False, "offline: radio_type nicht prüfbar (Core nötig)"

    if key == "radio_type":
        got = (status.get("radio_type") or "").upper()
        return got == val.upper(), f"radio_type={got!r}"
    if key in ("station", "radio_name", "radio_station"):
        got = status.get("radio_name") or status.get("radio_station") or ""
        return val.lower() in got.lower(), f"station={got!r}"
    if key == "path_contains":
        path = " / ".join(str(p) for p in menu.get("path", []))
        return val in path, f"path={path!r}"
    if key == "selected":
        got = menu.get("item_label") or ""
        return val.lower() in got.lower(), f"selected={got!r}"
    return False, f"unbekannter expect-Key: {key}"


def run_script(path: str, offline: bool = False, settle: float = 0.35) -> int:
    steps = parse_script(path)
    if offline:
        reset_offline_state()
    print(f"iDrive-Skript: {path} ({'offline' if offline else 'live'}) — {len(steps)} Schritte")
    last_offline = None
    failed = 0
    for i, (kind, arg) in enumerate(steps, 1):
        if kind == "sleep":
            print(f"  [{i}] sleep {arg}s")
            time.sleep(float(arg))
            continue
        if kind == "reset":
            print(f"  [{i}] reset")
            reset_offline_state()
            continue
        if kind == "expect":
            ok, detail = check_expect(arg, last_offline)
            print(f"  [{i}] expect {arg} → {'OK' if ok else 'FAIL'} ({detail})")
            if not ok:
                failed += 1
            continue
        if offline:
            last_offline = offline_apply(arg)
            print(f"  [{i}] {arg} → {last_offline.get('trigger')} | "
                  f"{' › '.join(last_offline.get('menu_path') or [])} | "
                  f"sel={last_offline.get('selected')!r}")
        else:
            res = inject_event(arg, source="idrive_script", require_ready=True)
            if not res.get("ok"):
                print(f"  [{i}] {arg} → FEHLER: {res.get('error')}")
                failed += 1
                continue
            time.sleep(settle)
            menu = _read_menu()
            path_l = " › ".join(str(p) for p in menu.get("path", []))
            print(f"  [{i}] {arg} → {res.get('trigger')} ctx={res.get('context')} | "
                  f"{path_l} | sel={menu.get('item_label')!r}")
            last_offline = None
    if failed:
        print(f"--- {failed} Fehler")
        return 1
    print("OK: Skript durchgelaufen")
    return 0


def cmd_event(event: str, offline: bool = False) -> int:
    res = offline_apply(event) if offline else inject_event(event, require_ready=True)
    if not res.get("ok"):
        print(f"FEHLER: {res.get('error')}")
        return 1
    print(f"Event:   {res.get('event')}")
    print(f"Kontext: {res.get('context')}")
    print(f"Trigger: {res.get('trigger')}")
    if res.get("offline"):
        print(f"Pfad:    {' › '.join(res.get('menu_path') or [])}")
        print(f"Markiert:{res.get('selected')!r}")
    else:
        menu = _read_menu()
        print(f"Pfad:    {' › '.join(str(p) for p in menu.get('path', []))}")
        print(f"Markiert:{menu.get('item_label')!r}")
    return 0

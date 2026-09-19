#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""webui_smoke_runner.py — Startet tools/webui_live_smoke.py asynchron für den Diagnose-Tab."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

STATUS_FILE = "/tmp/pidrive_webui_smoke_status.json"
LOG_FILE = "/tmp/pidrive_webui_smoke.log"
JSON_OUT = "/tmp/pidrive_webui_smoke.json"

_lock = threading.Lock()
_proc: Optional[subprocess.Popen] = None


def _pkg_root() -> Path:
    # …/pidrive/web/shared/this.py → pidrive/
    return Path(__file__).resolve().parents[2]


def _find_script() -> Optional[Path]:
    pkg = _pkg_root()
    candidates = [
        pkg.parent / "tools" / "webui_live_smoke.py",  # repo/tools
        pkg / "tools" / "webui_live_smoke.py",
        Path("/home/pidrive/pidrive/tools/webui_live_smoke.py"),
    ]
    for c in candidates:
        if c.is_file():
            return c
    return None


def _read_status() -> Dict[str, Any]:
    try:
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"running": False, "ok": False, "error": "kein Status"}


def _write_status(data: Dict[str, Any]) -> None:
    tmp = STATUS_FILE + ".tmp"
    data = dict(data)
    data["ts"] = time.time()
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, STATUS_FILE)


def get_status() -> Dict[str, Any]:
    """Aktueller Lauf + letztes Ergebnis (für Polling im Diagnose-Tab)."""
    with _lock:
        st = _read_status()
        alive = _proc is not None and _proc.poll() is None
        st["running"] = bool(alive or st.get("running"))
        if _proc is not None and _proc.poll() is not None and st.get("running"):
            # Race: Monitor-Thread noch nicht fertig
            st["running"] = False
    # Log-Tail
    log_tail = ""
    try:
        with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
            log_tail = "".join(lines[-80:])
    except Exception:
        pass
    st["log_tail"] = log_tail
    # Report wenn fertig
    report = None
    try:
        with open(JSON_OUT, "r", encoding="utf-8") as f:
            report = json.load(f)
    except Exception:
        report = None
    st["report"] = report
    return st


def start(mode: str = "flows", base: str = "http://127.0.0.1:8080") -> Dict[str, Any]:
    """
    mode:
      quick  — Seiten + Lists + kurze CMDs (~3s)
      flows  — + kritische Flows / State-Machine (~1–2 min)  [Default für UI]
      full   — inkl. riskanter CMDs (ohne reboot)
    """
    global _proc
    mode = (mode or "flows").lower().strip()
    if mode not in ("quick", "flows", "full"):
        mode = "flows"

    with _lock:
        if _proc is not None and _proc.poll() is None:
            return {"ok": False, "error": "Test läuft bereits", "running": True}

        script = _find_script()
        if not script:
            return {"ok": False, "error": "webui_live_smoke.py nicht gefunden"}

        # Alte Outputs leeren
        for p in (LOG_FILE, JSON_OUT):
            try:
                open(p, "w").close()
            except Exception:
                pass

        cmd = [
            "python3", "-u", str(script),
            "--base", base,
            "--json-out", JSON_OUT,
        ]
        if mode == "quick":
            cmd.append("--quick")
        elif mode == "full":
            cmd.append("--full")
        # flows = default (weder quick noch full)

        env = dict(os.environ)
        env["PYTHONUNBUFFERED"] = "1"

        log_f = open(LOG_FILE, "w", encoding="utf-8")
        try:
            _proc = subprocess.Popen(
                cmd,
                stdout=log_f,
                stderr=subprocess.STDOUT,
                env=env,
                cwd=str(script.parent.parent),
            )
        except Exception as e:
            log_f.close()
            return {"ok": False, "error": str(e)}

        _write_status({
            "ok": True,
            "running": True,
            "mode": mode,
            "pid": _proc.pid,
            "started_ts": time.time(),
            "script": str(script),
            "cmd": cmd,
            "exit_code": None,
            "summary": None,
            "error": "",
        })

        def _watch(p: subprocess.Popen, lf):
            global _proc
            try:
                rc = p.wait(timeout=600)
            except subprocess.TimeoutExpired:
                try:
                    p.kill()
                except Exception:
                    pass
                rc = -9
            try:
                lf.close()
            except Exception:
                pass
            summary = None
            try:
                with open(JSON_OUT, "r", encoding="utf-8") as f:
                    report = json.load(f)
                    summary = report.get("summary") if isinstance(report, dict) else None
            except Exception:
                summary = None
            with _lock:
                _write_status({
                    "ok": rc == 0,
                    "running": False,
                    "mode": mode,
                    "pid": p.pid,
                    "started_ts": _read_status().get("started_ts"),
                    "finished_ts": time.time(),
                    "exit_code": rc,
                    "summary": summary,
                    "error": "" if rc == 0 else f"exit {rc}",
                    "script": str(script),
                })
                if _proc is p:
                    _proc = None

        threading.Thread(target=_watch, args=(_proc, log_f), daemon=True, name="webui-smoke").start()
        return {"ok": True, "running": True, "mode": mode, "pid": _proc.pid}


def stop() -> Dict[str, Any]:
    global _proc
    with _lock:
        if _proc is None or _proc.poll() is not None:
            st = _read_status()
            st["running"] = False
            return {"ok": True, "stopped": False, "detail": "kein laufender Test", **st}
        try:
            os.kill(_proc.pid, signal.SIGTERM)
        except Exception as e:
            return {"ok": False, "error": str(e)}
        return {"ok": True, "stopped": True, "pid": _proc.pid}

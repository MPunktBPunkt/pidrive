#!/usr/bin/env python3
"""service.py — Hauptschleife von pidrive-fmtx.service (root).

- liest Kommandos zeilenweise aus /tmp/pidrive_fmtx_cmd
- schreibt Zustand nach /tmp/pidrive_fmtx_state.json (Heartbeat ts)
- Watchdog, Laufzeitlimit, RDS-Auto über TxManager.tick()
- sendet beim Dienststart nicht; einzige Ausnahme ist die Boot-Ansage:
  einmal pro Boot, wenn pidrive_core boot_phase=steady meldet (BootWatch),
  fm_tx.autostart != off ist und enabled/Consent den Start erlauben
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from settings import load_settings, save_settings  # noqa: E402
from modules.tx import tx_manager as tm  # noqa: E402

try:
    import log as _log  # noqa: E402
except Exception:  # pragma: no cover
    _log = None

POLL_S = 0.25
TICK_S = 1.0
PUBLISH_S = 2.0
THROTTLE_S = 15.0

SOURCE_STATE_FILE = "/tmp/pidrive_source_state.json"
BOOT_MARKER = "/run/pidrive_fmtx_boot_done"
BOOT_SETTLE_S = 3.0

_running = True


def _info(msg: str) -> None:
    if _log is not None:
        try:
            _log.info("[FMTX] " + msg)
            return
        except Exception:
            pass
    print("[FMTX] " + msg, flush=True)


def _on_signal(signum, _frame):
    global _running
    _running = False


def _prepare_cmd_file() -> None:
    fd = os.open(tm.CMD_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o666)
    os.close(fd)
    try:
        os.chmod(tm.CMD_FILE, 0o666)
    except Exception:
        pass


def _read_throttled() -> str:
    try:
        r = subprocess.run(["vcgencmd", "get_throttled"], capture_output=True,
                           text=True, timeout=2)
        return (r.stdout or "").strip().replace("throttled=", "")
    except Exception:
        return ""


def _boot_ts() -> float:
    try:
        with open("/proc/uptime", "r", encoding="ascii") as f:
            return time.time() - float(f.read().split()[0])
    except Exception:
        return 0.0


def read_boot_phase(path: str | None = None, boot_ts: float = 0.0) -> str:
    """boot_phase aus dem Source-State; Dateien aus einem früheren Boot zählen nicht."""
    path = path or SOURCE_STATE_FILE
    try:
        if os.path.getmtime(path) < boot_ts:
            return ""
        with open(path, "r", encoding="utf-8") as f:
            return str((json.load(f) or {}).get("boot_phase") or "")
    except Exception:
        return ""


class BootWatch:
    """Löst nach boot_phase=steady + BOOT_SETTLE_S einmal pro Boot die Ansage aus."""

    def __init__(self, clock=time.time, boot_ts: float | None = None):
        self._clock = clock
        self._boot_ts = _boot_ts() if boot_ts is None else boot_ts
        self.steady_since = 0.0
        self.done = os.path.exists(BOOT_MARKER)

    def poll(self, mgr) -> str | None:
        """Gibt eine Log-Meldung zurück, sobald entschieden wurde (genau einmal)."""
        if self.done:
            return None
        if read_boot_phase(boot_ts=self._boot_ts) != "steady":
            self.steady_since = 0.0
            return None
        now = self._clock()
        if not self.steady_since:
            self.steady_since = now
            return None
        if now - self.steady_since < BOOT_SETTLE_S:
            return None
        self.done = True
        self._write_marker()
        return self._run(mgr)

    def _run(self, mgr) -> str:
        _errs, cfg = tm.validate_cfg(tm.get_cfg(mgr._load() or {}))
        mode = cfg.get("autostart") or "off"
        if mode == "off":
            return "Boot-Ansage aus (autostart=off)"
        if not cfg.get("enabled"):
            return "Boot-Ansage übersprungen: fm_tx.enabled ist aus"
        if mgr.state in ("starting", "on"):
            return "Boot-Ansage übersprungen: Sender läuft bereits"
        if mgr.announce(then=mode):
            return f"Boot-Ansage gestartet (autostart={mode})"
        reason = mgr.error or "unbekannt"
        mgr.state = "off"
        mgr.error = ""
        mgr.warnings = list(mgr.warnings) + [f"Boot-Ansage übersprungen: {reason}"]
        mgr.publish()
        return f"Boot-Ansage übersprungen: {reason}"

    @staticmethod
    def _write_marker() -> None:
        try:
            with open(BOOT_MARKER, "w", encoding="ascii") as f:
                f.write(str(int(time.time())))
        except Exception:
            pass


def main() -> int:
    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)
    _prepare_cmd_file()
    mgr = tm.TxManager(load_settings, save_settings)
    mgr.publish()
    boot = BootWatch()
    _info("Dienst bereit (sendet nur auf 'start' oder einmalig zur Boot-Ansage)")

    offset = 0
    t_tick = t_pub = t_thr = 0.0
    while _running:
        try:
            size = os.path.getsize(tm.CMD_FILE)
            if size < offset:
                offset = 0
            if size > offset:
                with open(tm.CMD_FILE, "r", encoding="utf-8", errors="replace") as f:
                    f.seek(offset)
                    data = f.read()
                    offset = f.tell()
                for line in data.splitlines():
                    _info(f"cmd: {line.strip()[:80]}")
                    mgr.handle(line)
                    if mgr.state == "error":
                        _info(f"Fehler: {mgr.error}")
        except FileNotFoundError:
            _prepare_cmd_file()
            offset = 0
        except Exception as e:
            _info(f"cmd-Lesefehler: {e}")

        now = time.time()
        if now - t_tick >= TICK_S:
            t_tick = now
            prev = mgr.state
            try:
                mgr.tick()
            except Exception as e:
                _info(f"tick: {e}")
            if prev != mgr.state:
                _info(f"Zustand {prev} → {mgr.state} {mgr.error}")
            try:
                msg = boot.poll(mgr)
                if msg:
                    _info(msg)
            except Exception as e:
                _info(f"Boot-Ansage: {e}")
        if now - t_thr >= THROTTLE_S:
            t_thr = now
            mgr.throttled = _read_throttled()
        if now - t_pub >= PUBLISH_S:
            t_pub = now
            mgr.publish()
        time.sleep(POLL_S)

    _info("Dienst-Ende — Sender stoppen")
    mgr.stop("Dienst beendet")
    st = mgr.snapshot()
    st["service"] = False
    tm.write_state(st)
    return 0


if __name__ == "__main__":
    sys.exit(main())

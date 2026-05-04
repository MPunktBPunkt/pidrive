#!/usr/bin/env python3
"""bt_agent.py — BT-Agent, Pairing  v0.10.23
Ausgelagert aus bluetooth.py."""

from modules.bt_helpers import (
    _btctl, _run, _bg, _normalize_mac, _valid_mac,
    _write_json_atomic, _read_json, _now, _sleep_s,
    _bt_adapter_up, _ensure_bt_on,
    _parse_bool_from_info, _extract_name_from_info, _extract_alias_from_info,
    _is_public_or_bredr, _is_audio_device_info,
    AGENT_STATE_FILE, PAIRING_BACKUP_FILE, PAIR_TIMEOUT_SECONDS,
)
import threading
import select
import subprocess
import time
import log

# Agent-Prozess und Lock (lokal in diesem Modul)
_AGENT_PROC = None
_AGENT_LOCK = threading.Lock()

def _write_agent_state(running=False, ready=False, pid=0, last_error="",
                       started_ts=0, health_ok=False):
    if running and not started_ts:
        started_ts = _now()
    _write_json_atomic(AGENT_STATE_FILE, {
        "running": running,
        "ready": ready,
        "pid": pid,
        "started_ts": started_ts,
        "last_error": last_error,
        "health_ok": health_ok,
        "ts": _now(),
    })


def read_agent_state():
    return _read_json(AGENT_STATE_FILE, {})


def agent_is_alive():
    global _AGENT_PROC
    try:
        return _AGENT_PROC is not None and _AGENT_PROC.poll() is None
    except Exception:
        return False


def start_agent_session():
    """
    Persistente bluetoothctl-Agent-Session.
    """
    global _AGENT_PROC
    with _AGENT_LOCK:
        if agent_is_alive():
            st = read_agent_state()
            _write_agent_state(
                running=True,
                ready=st.get("ready", True),
                pid=_AGENT_PROC.pid,
                last_error=st.get("last_error", ""),
                started_ts=st.get("started_ts", _now()),
                health_ok=True
            )
            return True

        try:
            _AGENT_PROC = subprocess.Popen(
                ["bluetoothctl"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            # Agent initialisieren
            _AGENT_PROC.stdin.write("agent NoInputNoOutput\n")
            _AGENT_PROC.stdin.write("default-agent\n")
            _AGENT_PROC.stdin.flush()
            _sleep_s(1.0)

            _write_agent_state(
                running=True,
                ready=True,
                pid=_AGENT_PROC.pid,
                last_error="",
                started_ts=_now(),
                health_ok=True
            )
            log.info(f"BT agent: persistent session ready pid={_AGENT_PROC.pid}")
            return True

        except Exception as e:
            _AGENT_PROC = None
            _write_agent_state(
                running=False,
                ready=False,
                pid=0,
                last_error=str(e),
                started_ts=0,
                health_ok=False
            )
            log.warn("BT agent start: " + str(e))
            return False


def stop_agent_session():
    global _AGENT_PROC
    with _AGENT_LOCK:
        if _AGENT_PROC:
            try:
                _AGENT_PROC.terminate()
                _AGENT_PROC.wait(timeout=3)
            except Exception:
                try:
                    _AGENT_PROC.kill()
                except Exception:
                    pass
            _AGENT_PROC = None

        _write_agent_state(
            running=False,
            ready=False,
            pid=0,
            last_error="",
            started_ts=0,
            health_ok=False
        )
        log.info("BT agent: session stopped")


def agent_healthcheck():
    alive = agent_is_alive()
    st = read_agent_state()

    if alive:
        _write_agent_state(
            running=True,
            ready=st.get("ready", True),
            pid=_AGENT_PROC.pid if _AGENT_PROC else st.get("pid", 0),
            last_error=st.get("last_error", ""),
            started_ts=st.get("started_ts", _now()),
            health_ok=True
        )
        return True

    _write_agent_state(
        running=False,
        ready=False,
        pid=0,
        last_error=st.get("last_error", "agent_dead"),
        started_ts=0,
        health_ok=False
    )
    return False


def start_agent_health_thread():
    import threading as _th

    def _loop():
        while True:
            try:
                if not agent_healthcheck():
                    log.warn("BT agent health: dead — restart")
                    start_agent_session()
            except Exception as e:
                log.warn("BT agent health: " + str(e))
            time.sleep(20)

    _th.Thread(target=_loop, daemon=True, name="bt_agent_health").start()


def _ensure_agent():
    return start_agent_session()


def _drain_agent_stdout(max_lines=80):
    """
    Alte Agent-Ausgaben abräumen, damit pair_with_agent()
    nicht auf stale stdout-Zeilen reinfällt.

    v0.10.23: select.select() für echtes non-blocking I/O statt
    blindem readline(), das bei stale stdout dauerhaft blockieren kann.
    """
    global _AGENT_PROC
    if not agent_is_alive():
        return
    try:
        if _AGENT_PROC.stdout is None:
            return
        drained = 0
        start = time.time()
        fd = _AGENT_PROC.stdout.fileno()
        while drained < max_lines and (time.time() - start) < 0.8:
            if _AGENT_PROC.poll() is not None:
                break
            # select mit 50 ms Timeout → kein Blockieren
            ready, _, _ = select.select([fd], [], [], 0.05)
            if not ready:
                break  # nichts mehr verfügbar
            try:
                line = _AGENT_PROC.stdout.readline()
            except Exception:
                break
            if not line:
                break
            drained += 1
        if drained:
            log.info(f"BT agent: stdout drained lines={drained} (non-blocking)")
    except Exception:
        pass


def pair_with_agent(mac, timeout=PAIR_TIMEOUT_SECONDS):
    """
    Pairing über persistente Agent-Session.
    """
    global _AGENT_PROC

    mac = _normalize_mac(mac)
    if not _valid_mac(mac):
        return False, "invalid_mac"

    if not start_agent_session():
        return False, "agent_start_failed"

    _drain_agent_stdout()

    lines = []
    try:
        _AGENT_PROC.stdin.write(f"pair {mac}\n")
        _AGENT_PROC.stdin.flush()

        end = time.time() + timeout
        while time.time() < end:
            line = _AGENT_PROC.stdout.readline()
            if not line:
                _sleep_s(0.2)
                continue

            s = line.strip()
            lines.append(s)
            low = s.lower()

            if (
                "pairing successful" in low or
                "device has been paired" in low or
                "already paired" in low or
                "already exists" in low or
                ("paired" in low and "successful" in low)
            ):
                _write_agent_state(
                    running=True,
                    ready=True,
                    pid=_AGENT_PROC.pid,
                    last_error="",
                    started_ts=read_agent_state().get("started_ts", _now()),
                    health_ok=True
                )
                _write_json_atomic(PAIRING_BACKUP_FILE, {
                    "mac": mac,
                    "ok": True,
                    "lines": lines[-30:],
                    "ts": _now(),
                })
                return True, "\n".join(lines[-30:])

            if (
                "authenticationfailed" in low or
                "authentication failed" in low or
                "failed" in low or
                "not available" in low or
                "canceled" in low
            ):
                _write_agent_state(
                    running=True,
                    ready=False,
                    pid=_AGENT_PROC.pid,
                    last_error=s,
                    started_ts=read_agent_state().get("started_ts", _now()),
                    health_ok=False
                )
                _write_json_atomic(PAIRING_BACKUP_FILE, {
                    "mac": mac,
                    "ok": False,
                    "lines": lines[-30:],
                    "ts": _now(),
                })
                return False, "\n".join(lines[-30:])

        _write_agent_state(
            running=True,
            ready=False,
            pid=_AGENT_PROC.pid,
            last_error="pair_timeout",
            started_ts=read_agent_state().get("started_ts", _now()),
            health_ok=False
        )
        _write_json_atomic(PAIRING_BACKUP_FILE, {
            "mac": mac,
            "ok": False,
            "timeout": True,
            "lines": lines[-30:],
            "ts": _now(),
        })
        return False, "\n".join(lines[-30:])

    except Exception as e:
        _write_agent_state(
            running=False,
            ready=False,
            pid=0,
            last_error=str(e),
            started_ts=0,
            health_ok=False
        )
        return False, str(e)




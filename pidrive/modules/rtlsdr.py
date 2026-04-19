# -*- coding: utf-8 -*-
"""
pidrive/modules/rtlsdr.py  —  PiDrive v0.8.1

Zentrale RTL-SDR Verwaltung:
  - Passive USB-Erkennung (kein Öffnen des Device!)
  - Tool-Check (rtl_test, rtl_fm, welle-cli)
  - DVB-Treiber-Check (lsmod)
  - Unterspannungs-Check (vcgencmd)
  - Prozess/Lock-Check
  - Exklusives Locking via flock()
  - Optionale aktive Smoke-Tests (nur auf Anfrage)
  - Debug-JSON: /tmp/pidrive_rtlsdr.json

Verwendung:
    # Passiv (kein Device-Zugriff):
    from modules import rtlsdr
    rtlsdr.log_startup_check(log)

    # Exklusiver Zugriff:
    with rtlsdr.acquire_lock(owner="fm"):
        subprocess.Popen(["rtl_fm", ...])

    # Diagnose-CLI:
    python3 modules/rtlsdr.py
    python3 modules/rtlsdr.py --active
"""

import argparse
import fcntl
import json
import os
import re
import shutil
import subprocess
import time
from contextlib import contextmanager

DEBUG_FILE  = "/tmp/pidrive_rtlsdr.json"
LOCK_FILE   = "/tmp/pidrive_rtlsdr.lock"
STATE_FILE  = "/tmp/pidrive_rtlsdr_state.json"

RTL_USB_MATCHES  = ("0bda:2838", "RTL2838", "RTL2832", "RTL2838UHIDIR")
RTL_PROC_NAMES   = ("rtl_test", "rtl_fm", "welle-cli")
DVB_MOD_PATTERN  = r"dvb_usb_rtl28xxu|dvb_core|rtl2832|rtl2830|r820t"


class RTLSDRError(RuntimeError):
    pass

class RTLBusyError(RTLSDRError):
    pass


# ── interne Helpers ────────────────────────────────────────────────────────

def _run(args, timeout=5):
    try:
        cp = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return {"ok": cp.returncode == 0, "rc": cp.returncode,
                "out": cp.stdout or "", "err": cp.stderr or "", "timeout": False}
    except subprocess.TimeoutExpired as e:
        return {"ok": False, "rc": 124,
                "out": e.stdout or "", "err": e.stderr or "", "timeout": True}
    except Exception as e:
        return {"ok": False, "rc": 1, "out": "", "err": str(e), "timeout": False}

def _sh(cmd, timeout=5):
    return _run(["bash", "-c", cmd], timeout=timeout)

def _atomic_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


# ── Passive Checks (öffnen das Device NICHT) ──────────────────────────────

def detect_usb():
    """USB-Stick per lsusb erkennen — kein Öffnen."""
    r = _run(["lsusb"], timeout=3)
    text = r["out"] + r["err"]
    lines = [ln.strip() for ln in text.splitlines()
             if any(m in ln for m in RTL_USB_MATCHES)]
    return {"present": bool(lines), "matches": lines, "raw": text.strip()}

def which_tools():
    """Tool-Verfügbarkeit (shutil.which — kein Device-Zugriff)."""
    return {t: (shutil.which(t) or None) for t in
            ("rtl_test", "rtl_fm", "welle-cli", "vcgencmd", "lsusb")}

def loaded_dvb_modules():
    """Geladene DVB/RTL Kernelmodule (lsmod — kein Device-Zugriff)."""
    r = _sh(f"lsmod 2>/dev/null | grep -E '{DVB_MOD_PATTERN}' || true", timeout=3)
    return [ln.strip() for ln in r["out"].splitlines() if ln.strip()]

def find_rtl_processes():
    """Laufende RTL-Prozesse (ps — kein Device-Zugriff)."""
    r = _sh(r"ps ax -o pid=,cmd= | grep -E 'rtl_test|rtl_fm|welle-cli' "
            r"| grep -v grep || true", timeout=3)
    procs = []
    for ln in r["out"].splitlines():
        ln = ln.strip()
        m = re.match(r"^(\d+)\s+(.+)$", ln)
        if m:
            procs.append({"pid": int(m.group(1)), "cmd": m.group(2)})
    return procs

def get_throttled():
    """vcgencmd get_throttled — Unterspannungs-Flags dekodieren."""
    if not shutil.which("vcgencmd"):
        return {"ok": False, "raw": "", "value": 0,
                "undervoltage_now": False, "undervoltage_seen": False,
                "throttled_now": False, "throttled_seen": False}
    r = _run(["vcgencmd", "get_throttled"], timeout=3)
    raw = (r["out"] + r["err"]).strip()
    m = re.search(r"0x([0-9a-fA-F]+)", raw)
    val = int(m.group(1), 16) if m else 0
    return {
        "ok": bool(m), "raw": raw, "value": val,
        "undervoltage_now":  bool(val & 0x00001),
        "freq_capped_now":   bool(val & 0x00002),
        "throttled_now":     bool(val & 0x00004),
        "undervoltage_seen": bool(val & 0x10000),
        "freq_capped_seen":  bool(val & 0x20000),
        "throttled_seen":    bool(val & 0x40000),
    }

def dmesg_voltage():
    """Letzte Spannung/Throttling-Meldungen aus dmesg."""
    r = _sh(r"dmesg -T 2>/dev/null | grep -iE 'under-voltage|voltage|thrott' "
            r"| tail -10 || true", timeout=4)
    return [ln.strip() for ln in r["out"].splitlines() if ln.strip()]

def lsof_usb():
    """Offene USB-Dateien (wer hält den Stick?)."""
    r = _sh("lsof /dev/bus/usb/* 2>/dev/null || true", timeout=4)
    return [ln.strip() for ln in r["out"].splitlines() if ln.strip()]

def is_busy():
    """Schneller Busy-Check: laufende Prozesse oder Lock aktiv?"""
    procs = find_rtl_processes()
    state = _read_state()
    return bool(procs) or bool(state.get("locked"))


# ── Lock- und Prozessverwaltung ───────────────────────────────────────────
#
# Design: Lock bleibt aktiv solange der RTL-Prozess läuft.
#   start_process() → Lock holen + Prozess starten
#   stop_process()  → Prozess beenden + Lock freigeben
#   reap_process()  → aufräumen wenn Prozess von selbst endet
#
# acquire_lock() / contextmanager bleibt für kurze atomare Aktionen (Scans).

_LOCK_REGISTRY = {
    "fd":         None,
    "owner":      None,
    "proc":       None,
    "proc_name":  None,
    "started_ts": 0,
}


def _read_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _write_state(data):
    _atomic_json(STATE_FILE, data)

def _clear_state():
    try:
        os.remove(STATE_FILE)
    except FileNotFoundError:
        pass

def _pid_alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False

def _proc_running(proc):
    try:
        return proc is not None and proc.poll() is None
    except Exception:
        return False

def _release_runtime_lock():
    """Intern: Lock-FD freigeben + Registry + State löschen."""
    fd = _LOCK_REGISTRY.get("fd")
    if fd is not None:
        try: fcntl.flock(fd, fcntl.LOCK_UN)
        except Exception: pass
        try: os.close(fd)
        except Exception: pass
    _LOCK_REGISTRY.update({"fd": None, "owner": None,
                            "proc": None, "proc_name": None,
                            "started_ts": 0})
    _clear_state()


def reap_process():
    """
    Aufräumen wenn registrierter Prozess beendet ist.
    Sollte vor is_busy(), start_process(), stop_process() aufgerufen werden.
    """
    proc = _LOCK_REGISTRY.get("proc")
    if proc is None:
        # Stale State von anderem PID aufräumen
        st = _read_state()
        if st.get("locked") and st.get("pid") == os.getpid():
            _clear_state()
        return
    try:
        rc = proc.poll()
    except Exception:
        rc = 0
    if rc is not None:
        _release_runtime_lock()


def wait_until_free(timeout=2.5, interval=0.05):
    """
    Wartet kurz bis RTL-SDR wirklich frei ist — v0.8.10.
    Hilft bei Race Conditions direkt nach stop_process()/Quellenwechsel.
    Gibt True zurück wenn frei, False wenn timeout.
    """
    end = time.time() + timeout
    while time.time() < end:
        try:
            reap_process()
        except Exception:
            pass

        procs = find_rtl_processes()
        state = _read_state()

        locked = False
        if state.get("locked"):
            pid = state.get("pid")
            if pid and _pid_alive(pid):
                locked = True
            else:
                _clear_state()
                locked = False

        if not procs and not locked and not _proc_running(_LOCK_REGISTRY.get("proc")):
            return True

        time.sleep(interval)
    return False


def is_busy():
    """
    Busy wenn eigener RTL-Prozess läuft, fremde RTL-Prozesse laufen,
    oder ein fremder flock-State aktiv ist.
    """
    reap_process()
    if _proc_running(_LOCK_REGISTRY.get("proc")):
        return True
    if find_rtl_processes():
        return True
    state = _read_state()
    if state.get("locked"):
        pid = state.get("pid")
        if pid and _pid_alive(pid):
            return True
        _clear_state()  # stale
    return False


def acquire_runtime_lock(owner="unknown", blocking=False):
    """
    Persistentes flock-Lock holen — bleibt aktiv bis release_runtime_lock().
    Für lang laufende Prozesse bitte start_process() nutzen.
    """
    reap_process()
    if _LOCK_REGISTRY.get("fd") is not None:
        raise RTLBusyError(
            f"RTL-SDR intern belegt durch: {_LOCK_REGISTRY.get('owner')}")

    fd = os.open(LOCK_FILE, os.O_CREAT | os.O_RDWR, 0o666)
    try:
        flags = fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB)
        try:
            fcntl.flock(fd, flags)
        except BlockingIOError:
            try: os.close(fd)
            except Exception: pass
            state = _read_state()
            raise RTLBusyError(
                f"RTL-SDR belegt durch: {state.get('owner','?')}")

        meta = {"locked": True, "owner": owner,
                "pid": os.getpid(), "ts": int(time.time())}
        _write_state(meta)
        os.ftruncate(fd, 0)
        os.write(fd, json.dumps(meta).encode())
        _LOCK_REGISTRY["fd"] = fd
        _LOCK_REGISTRY["owner"] = owner
        _LOCK_REGISTRY["started_ts"] = int(time.time())
        return meta
    except Exception:
        try: os.close(fd)
        except Exception: pass
        raise


def release_runtime_lock():
    reap_process()
    _release_runtime_lock()


@contextmanager
def acquire_lock(owner="unknown", blocking=False, timeout_s=0):
    """
    Context-Manager für kurze exklusive Aktionen (z.B. Scan-Kanal).
    Lock wird beim Verlassen des with-Blocks freigegeben,
    SOFERN kein Prozess registriert ist.
    Für lang laufende Prozesse: start_process() / stop_process().
    """
    acquire_runtime_lock(owner=owner, blocking=blocking)
    try:
        yield {"locked": True, "owner": owner,
               "pid": os.getpid(), "ts": int(time.time())}
    finally:
        if _LOCK_REGISTRY.get("proc") is None:
            _release_runtime_lock()


def start_process(cmd, owner="unknown", **popen_kwargs):
    """
    RTL-Prozess starten und Lock an Prozesslebensdauer koppeln.
    Lock bleibt aktiv bis stop_process() oder der Prozess endet.
    Rückgabe: subprocess.Popen
    """
    reap_process()
    if is_busy():
        state = _read_state()
        holder = (state.get("owner") or
                  _LOCK_REGISTRY.get("owner") or "?")
        raise RTLBusyError(f"RTL-SDR belegt durch: {holder}")

    acquire_runtime_lock(owner=owner, blocking=False)
    try:
        proc = subprocess.Popen(cmd, **popen_kwargs)
        _LOCK_REGISTRY["proc"]       = proc
        _LOCK_REGISTRY["proc_name"]  = owner
        meta = {"locked": True, "owner": owner,
                "pid": os.getpid(), "child_pid": proc.pid,
                "ts": int(time.time())}
        _write_state(meta)
        fd = _LOCK_REGISTRY.get("fd")
        if fd is not None:
            try:
                os.ftruncate(fd, 0)
                os.write(fd, json.dumps(meta).encode())
            except Exception:
                pass
        return proc
    except Exception:
        _release_runtime_lock()
        raise


def stop_process(timeout=2.0, kill_timeout=2.0):
    """
    Registrierten RTL-Prozess beenden und Lock freigeben.
    Gibt True zurück wenn ein Prozess beendet wurde.
    """
    proc = _LOCK_REGISTRY.get("proc")
    if proc is None:
        _release_runtime_lock()
        return False
    try:
        if proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=kill_timeout)
    except Exception:
        pass
    finally:
        _release_runtime_lock()
    return True


# ── Aktive Smoke-Tests (öffnen das Device!) ───────────────────────────────

def smoke_test_rtl_test():
    """Kurzer rtl_test -t — öffnet Device exklusiv."""
    if not shutil.which("rtl_test"):
        return {"ok": False, "error": "rtl_test fehlt"}
    try:
        with acquire_lock(owner="smoke_rtl_test"):
            r = _run(["rtl_test", "-t"], timeout=4)
            text = (r["out"] + r["err"]).strip()
            ok = any(x in text for x in
                     ["Found Rafael Micro", "Found 1 device", "Using device 0"])
            error = ""
            if "usb_claim_interface" in text:
                error = "usb_claim_interface error — DVB-Treiber geladen?"
            elif "Failed to open" in text:
                error = "Stick nicht öffenbar"
            return {"ok": ok, "rc": r["rc"], "text": text[:2000], "error": error}
    except RTLBusyError as e:
        return {"ok": False, "error": str(e)}

def smoke_test_fm(freq="104.4M"):
    """rtl_fm 5s — liefert ok wenn >0 Bytes ankommen."""
    if not shutil.which("rtl_fm"):
        return {"ok": False, "error": "rtl_fm fehlt"}
    try:
        with acquire_lock(owner="smoke_fm"):
            r = _sh(f"timeout 5 rtl_fm -f {freq} -M wbfm -s 200k "
                    f"-r 32k 2>/dev/null | wc -c", timeout=7)
            try:
                count = int(r["out"].strip())
            except Exception:
                count = 0
            return {"ok": count > 0, "bytes": count, "rc": r["rc"]}
    except RTLBusyError as e:
        return {"ok": False, "error": str(e)}

def smoke_test_dab(channel="11D"):
    """welle-cli 10s — prüft ob Stick öffenbar."""
    if not shutil.which("welle-cli"):
        return {"ok": False, "error": "welle-cli fehlt"}
    try:
        with acquire_lock(owner="smoke_dab"):
            r = _sh(f"timeout 10 welle-cli -c {channel} -D 2>&1 | head -40",
                    timeout=12)
            text = (r["out"] + r["err"]).strip()
            ok = ("Opening rtl-sdr" in text or "Wait for" in text) \
                 and "usb_claim_interface error" not in text
            return {"ok": ok, "rc": r["rc"], "text": text[:3000]}
    except RTLBusyError as e:
        return {"ok": False, "error": str(e)}


# ── Volldiagnose ───────────────────────────────────────────────────────────

def diagnose(active_tests=False):
    """Volldiagnose — schreibt auch DEBUG_FILE."""
    data = {
        "ts":             int(time.time()),
        "usb":            detect_usb(),
        "tools":          which_tools(),
        "dvb_modules":    loaded_dvb_modules(),
        "processes":      find_rtl_processes(),
        "usb_open_files": lsof_usb(),
        "throttled":      get_throttled(),
        "voltage_log":    dmesg_voltage(),
        "busy":           is_busy(),
        "lock_state":     _read_state(),
    }
    if active_tests:
        for key, fn in [("smoke_rtl_test", smoke_test_rtl_test),
                        ("smoke_fm",       smoke_test_fm),
                        ("smoke_dab",      smoke_test_dab)]:
            try:
                data[key] = fn()
            except Exception as e:
                data[key] = {"ok": False, "error": str(e)}
    _atomic_json(DEBUG_FILE, data)
    return data


def clear_stale_lock():
    """
    Stale Lock-Datei aufräumen — v0.8.9.
    Wenn der Lock-Owner-PID nicht mehr existiert, Lock löschen.
    Verhindert 'RTL-SDR belegt' nach einem Neustart des Core-Service.
    """
    try:
        if not os.path.exists(LOCK_FILE):
            return
        state = _read_state()
        locked_pid = state.get("pid")
        if not locked_pid:
            return
        # Prüfen ob PID noch lebt
        try:
            os.kill(locked_pid, 0)
            # PID existiert → kein stale Lock
        except ProcessLookupError:
            # PID tot → staler Lock → aufräumen
            import log as _log
            _log.warn(f"RTL-SDR: staler Lock von PID {locked_pid} gefunden, wird bereinigt")
            try:
                os.remove(LOCK_FILE)
            except Exception:
                pass
            _write_state({"locked": False, "owner": "", "pid": 0,
                          "ts": int(time.time()), "child_pid": None})
        except PermissionError:
            # PID existiert aber gehört anderem User → nicht löschen
            pass
    except Exception:
        pass


def log_startup_check(log):
    """
    Passiver Startup-Check für main_core.py.
    Öffnet das Device NICHT — nur lsusb + lsmod + vcgencmd.
    """
    # Stale Lock von vorherigem Lauf bereinigen
    clear_stale_lock()

    usb = detect_usb()
    if usb["present"]:
        log.info("  ✓ RTL-SDR: Stick erkannt (DAB+/FM/Scanner verfuegbar)")
    else:
        log.warn("  ⚠ RTL-SDR: kein Stick — DAB+/FM/Scanner nicht verfuegbar")
        return

    # DVB-Treiber blockierend?
    dvb = loaded_dvb_modules()
    if dvb:
        log.warn("  ⚠ DVB-Treiber geladen — blockiert rtl_fm/welle-cli!")
        for m in dvb:
            log.warn("    " + m)
        log.warn("    Fix: sudo reboot (Blacklist in /etc/modprobe.d/)")
    else:
        log.info("  ✓ RTL-SDR: kein blockierender DVB-Treiber")

    # Tools
    tools = which_tools()
    for t in ("rtl_fm", "welle-cli"):
        if tools[t]:
            log.info(f"    ✓ {t}")
        else:
            log.warn(f"    ✗ {t} fehlt")

    # Unterspannung
    th = get_throttled()
    if th.get("undervoltage_now"):
        log.warn("  ⚠ Unterspannung AKTIV — 5V/3A Netzteil noetig!")
    elif th.get("undervoltage_seen"):
        log.warn(f"  ⚠ Unterspannung seit Boot ({th.get('raw','')}) "
                    "— Netzteil/Kabel pruefen")
    elif th.get("ok"):
        log.info("  ✓ Stromversorgung OK (kein Throttling)")


# ── Zusammenfassung (Text) ─────────────────────────────────────────────────

def summary(data):
    L = []
    usb = data.get("usb", {})
    th  = data.get("throttled", {})
    procs = data.get("processes", [])
    dvb   = data.get("dvb_modules", [])
    tools = data.get("tools", {})

    L.append("RTL-SDR Diagnose  v0.8.1")
    L.append("=" * 44)
    L.append(("✓" if usb.get("present") else "⚠") +
             " USB Stick: " + ("erkannt" if usb.get("present") else "NICHT erkannt"))
    for ln in usb.get("matches", []):
        L.append("  " + ln)

    L.append("")
    L.append("Tools:")
    for t in ("rtl_test", "rtl_fm", "welle-cli"):
        v = tools.get(t)
        L.append(f"  {'✓' if v else '✗'} {t}")

    L.append("")
    L.append("DVB-Treiber (sollten leer sein):")
    if dvb:
        for m in dvb:
            L.append("  ⚠ " + m)
        L.append("  → sudo reboot nach install.sh blacklist")
    else:
        L.append("  ✓ keine blockierenden Module")

    L.append("")
    L.append("Laufende RTL-Prozesse:")
    if procs:
        for p in procs:
            L.append(f"  ⚠ PID {p['pid']}: {p['cmd']}")
    else:
        L.append("  ✓ keine")

    L.append("")
    L.append("Stromversorgung:")
    if th.get("undervoltage_now"):
        L.append("  ⚠ UNTERSPANNUNG AKTIV")
    elif th.get("undervoltage_seen"):
        L.append(f"  ⚠ Unterspannung seit Boot: {th.get('raw','')}")
    else:
        L.append(f"  ✓ OK  {th.get('raw','')}")
    for ln in data.get("voltage_log", [])[-3:]:
        L.append("    " + ln)

    for key, label in [("smoke_rtl_test", "rtl_test"),
                       ("smoke_fm",       "FM 104.4"),
                       ("smoke_dab",      "DAB 11D")]:
        if key in data:
            r = data[key]
            icon = "✓" if r.get("ok") else "✗"
            detail = r.get("error") or r.get("bytes", "") or ""
            L.append(f"  {icon} Smoke {label}: "
                     f"{'OK' if r.get('ok') else 'FAIL'}  {detail}")

    return "\n".join(L)




# ── USB Reset ─────────────────────────────────────────────────────────────────

def usb_reset() -> dict:
    """
    RTL-SDR USB-Stick hard-reset ohne Reboot (v0.8.16).
    Nutzt sysfs authorized-Cycle: 0 → kurze Pause → 1.
    Funktioniert wenn der Stick sich aus dem USB-Subsystem verabschiedet hat.

    Ablauf:
    1. Alle rtl_fm/welle-cli Prozesse killen
    2. Lock + State bereinigen
    3. USB-Device via sysfs unbinden (authorized=0) und wieder binden (authorized=1)
    4. Kurz warten und Stick neu erkennen (lsusb)
    """
    import glob
    import time as _t
    result = {"ok": False, "steps": [], "found_after_reset": False}

    # Schritt 1: laufende Prozesse killen
    for proc in ("rtl_fm", "rtl_test", "welle-cli", "welle_cli"):
        try:
            _run(["pkill", "-9", "-f", proc], timeout=3)
            result["steps"].append(f"kill {proc}")
        except Exception:
            pass
    _t.sleep(0.5)

    # Schritt 2: Lock + State bereinigen
    try:
        clear_stale_lock()
        import os
        for f in (LOCK_FILE, STATE_FILE, "/tmp/pidrive_dab_welle.err"):
            try:
                os.remove(f)
            except FileNotFoundError:
                pass
        result["steps"].append("lock cleared")
    except Exception as e:
        result["steps"].append(f"lock clear error: {e}")

    # Schritt 3: USB-Device via sysfs authorized cycle
    # USB-Bus-Path für RTL2838 finden
    usb_path = None
    try:
        raw = _run(["lsusb"], timeout=3)
        for line in raw.splitlines():
            for uid in RTL_USB_MATCHES:
                if uid.lower() in line.lower():
                    # "Bus 001 Device 004" → /sys/bus/usb/devices/1-X
                    parts = line.split()
                    bus = parts[1].lstrip("0") or "1"
                    dev = parts[3].rstrip(":").lstrip("0") or "1"
                    # Sysfs-Pfad über product/idVendor suchen
                    patterns = glob.glob(f"/sys/bus/usb/devices/{bus}-*")
                    for p in patterns:
                        try:
                            idv = open(f"{p}/idVendor").read().strip()
                            idp = open(f"{p}/idProduct").read().strip()
                            if idv == "0bda" and idp in ("2838", "2832", "2837"):
                                usb_path = p
                                break
                        except Exception:
                            pass
                    break
    except Exception as e:
        result["steps"].append(f"usb path search error: {e}")

    if usb_path:
        result["steps"].append(f"usb path: {usb_path}")
        try:
            auth_file = f"{usb_path}/authorized"
            with open(auth_file, "w") as f:
                f.write("0")
            result["steps"].append("authorized=0 (unbind)")
            _t.sleep(1.5)
            with open(auth_file, "w") as f:
                f.write("1")
            result["steps"].append("authorized=1 (rebind)")
            _t.sleep(2.0)
        except Exception as e:
            result["steps"].append(f"sysfs write error: {e}")
            # Fallback: usbreset wenn vorhanden
            try:
                _run(["usbreset", "0bda:2838"], timeout=5)
                result["steps"].append("usbreset fallback")
                _t.sleep(2.0)
            except Exception:
                pass
    else:
        result["steps"].append("usb path not found — attempting usbreset")
        try:
            _run(["usbreset", "0bda:2838"], timeout=5)
            result["steps"].append("usbreset")
            _t.sleep(2.0)
        except Exception as e2:
            result["steps"].append(f"usbreset failed: {e2}")

    # Schritt 4: Ergebnis prüfen
    _t.sleep(1.0)
    usb_data = detect_usb()
    result["found_after_reset"] = usb_data.get("present", False)
    result["ok"] = result["found_after_reset"]
    result["steps"].append(
        "RTL-SDR wieder erkannt ✓" if result["found_after_reset"]
        else "RTL-SDR NICHT erkannt — Stick ggf. abziehen und neu einstecken"
    )

    # Diagnose neu schreiben
    try:
        _write_diag_json(diagnose())
    except Exception:
        pass

    return result

# ── CLI ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="PiDrive RTL-SDR Diagnose")
    ap.add_argument("--active", action="store_true",
                    help="aktive Smoke-Tests (öffnet Device)")
    ap.add_argument("--json", action="store_true",
                    help="JSON-Ausgabe")
    args = ap.parse_args()

    data = diagnose(active_tests=args.active)

    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(summary(data))
        print(f"\nDebug-JSON: {DEBUG_FILE}")

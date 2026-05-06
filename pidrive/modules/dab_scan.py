#!/usr/bin/env python3
"""dab_scan.py — DAB+ Suchlauf und Sender-Datenbank  v0.10.42"""

from modules.dab_helpers import (
    _write_json_atomic, _read_json, _run, _get_dab_gain,
    _last_scan_diag, _scan_running,
    SCAN_DEBUG_FILE, _rtlsdr, _src_state,
)
import os, json, time, threading, urllib.request as _ur
import log, ipc

STATIONS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config", "dab_stations.json"
)

def is_scan_running() -> bool:
    """Öffentliche Abfrage ob ein Scan läuft."""
    return _scan_running

def get_last_scan_diag():
    return dict(_last_scan_diag)


def _write_scan_diag_file():
    _write_json_atomic(SCAN_DEBUG_FILE, _last_scan_diag)


def load_last_scan_diag_file():
    return _read_json(SCAN_DEBUG_FILE, {})


# ─────────────────────────────────────────────────────────────────────────────
# Wiedergabe-Status / DLS Poller
# ─────────────────────────────────────────────────────────────────────────────


def load_stations():
    path = os.path.join(os.path.dirname(__file__), "../config/dab_stations.json")
    try:
        data = json.load(open(path, encoding="utf-8"))
        return data.get("stations", data) if isinstance(data, dict) else data
    except Exception:
        return []


def save_stations(stations):
    path = os.path.join(os.path.dirname(__file__), "../config/dab_stations.json")
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(stations, f, indent=2, ensure_ascii=False)
    except Exception as e:
        log.error(f"DAB save Fehler: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Scan
# ─────────────────────────────────────────────────────────────────────────────

def scan_dab_channels(settings=None):
    import subprocess as _sp
    import time as _t

    if settings is None:
        try:
            from settings import load_settings as _ls
            settings = _ls()
        except Exception:
            settings = {}

    SCAN_PORT = int(settings.get("dab_scan_port", 7981) or 7981)
    WAIT_LOCK = int(settings.get("dab_scan_wait_lock", 20) or 20)
    WAIT_HTTP = int(settings.get("dab_scan_http_timeout", 4) or 4)

    CHANNELS_REGIONAL = ["5C", "5D", "8D", "10A", "10D", "11D", "12D"]
    CHANNELS_FULL = [
        "5A","5B","5C","5D","6A","6B","6C","6D",
        "7A","7B","7C","7D","8A","8B","8C","8D",
        "9A","9B","9C","9D","10A","10B","10C","10D",
        "11A","11B","11C","11D","12A","12B","12C","12D",
        "13A","13B","13C","13D","13E","13F",
    ]

    requested_channels = settings.get("dab_scan_channels", []) or []
    if isinstance(requested_channels, str):
        requested_channels = [x.strip().upper() for x in requested_channels.split(",") if x.strip()]
    requested_channels = [str(x).strip().upper() for x in requested_channels if str(x).strip()]

    if requested_channels:
        region_list = [ch for ch in requested_channels if ch in CHANNELS_FULL]
        full_list = region_list[:]
        log.info(f"DAB Scan: gezielte Kanäle: {region_list} (WAIT_LOCK={WAIT_LOCK}s PORT={SCAN_PORT})")
    else:
        region_list = CHANNELS_REGIONAL
        full_list = CHANNELS_FULL
        log.info(f"DAB Scan: Standard-Scan (WAIT_LOCK={WAIT_LOCK}s PORT={SCAN_PORT})")

    gain_idx = _get_dab_gain(settings)
    found = []
    scanned = []

    def _lock_state_name(snr, ens_label, ens_id, services, fic_crc, last_fct0):
        if services > 0:
            return "services_found"
        if ens_label or (ens_id and ens_id != "0x0000"):
            return "ensemble_locked"
        if int(last_fct0 or 0) == 0:
            return "no_fct0_lock" if snr >= 2.0 else "no_signal"
        if fic_crc >= 0:
            return "fic_only"
        return "unknown"

    global _last_scan_diag
    _last_scan_diag = {
        "channels": {},
        "ts": int(time.time()),
        "wait_lock": WAIT_LOCK,
        "port": SCAN_PORT
    }
    _write_scan_diag_file()

    _sp.run("pkill -f welle-cli 2>/dev/null", shell=True, capture_output=True)
    _t.sleep(0.5)

    if _rtlsdr:
        usb = _rtlsdr.detect_usb()
        if not usb.get("present"):
            log.error("DAB Scan: RTL-SDR nicht erkannt")
            return []
        if _rtlsdr.is_busy():
            log.warn("DAB Scan: RTL-SDR belegt — warte 2s")
            _t.sleep(2)

    def _scan_channel(ch):
        _sp.run("pkill -f welle-cli 2>/dev/null", shell=True, capture_output=True)
        _t.sleep(0.3)

        cmd = (f"welle-cli -c {ch} -g {gain_idx} -C 1 -w {SCAN_PORT} "
               f"2>/tmp/pidrive_dab_welle.err")
        proc = _sp.Popen(cmd, shell=True, stdout=_sp.DEVNULL, stderr=_sp.DEVNULL)
        _t.sleep(WAIT_LOCK)

        services = []
        snr = 0.0
        ens_label = ""
        ens_id = ""
        freq_corr = 0
        fic_crc = -1
        last_fct0 = 0
        rx_gain = ""

        try:
            url = f"http://127.0.0.1:{SCAN_PORT}/mux.json"
            resp = _ur.urlopen(url, timeout=WAIT_HTTP)
            data = json.loads(resp.read().decode("utf-8"))

            snr = float(data.get("demodulator", {}).get("snr", 0) or data.get("demodulator_snr", 0))
            ens_label = (data.get("ensemble", {}).get("label", {}).get("label", "") or "")
            ens_id = data.get("ensemble", {}).get("id", "")
            fic_crc = int(data.get("demodulator", {}).get("fic", {}).get("numcrcerrors", -1))
            last_fct0 = int(data.get("demodulator", {}).get("time_last_fct0_frame", 0) or 0)
            freq_corr = int(data.get("receiver", {}).get("hardware", {}).get("freqcorr", 0) or 0)
            rx_gain = str(data.get("receiver", {}).get("hardware", {}).get("gain", ""))

            raw_svcs = data.get("services", [])
            for svc in raw_svcs:
                _lbl = svc.get("label", "")
                if isinstance(_lbl, dict):
                    _lbl = _lbl.get("label", "") or ""
                name = str(_lbl or "").strip()
                sid = str(svc.get("sid", "") or "").strip()
                url_mp3 = str(svc.get("url_mp3", "") or "").strip()
                if name:
                    services.append({
                        "name": name,
                        "service_id": sid,
                        "url_mp3": url_mp3
                    })

        except Exception as e:
            log.info(f"DAB Scan: {ch}: mux.json nicht erreichbar ({e})")

        try:
            proc.terminate()
        except Exception:
            pass
        _sp.run("pkill -f welle-cli 2>/dev/null", shell=True, capture_output=True)

        lock_state = _lock_state_name(
            snr=snr, ens_label=ens_label, ens_id=ens_id,
            services=len(services), fic_crc=fic_crc, last_fct0=last_fct0
        )

        _last_scan_diag["channels"][ch] = {
            "ensemble": ens_label,
            "ensemble_id": ens_id,
            "services": len(services),
            "snr": snr,
            "freqcorr": freq_corr,
            "gain": rx_gain,
            "ficcrc": fic_crc,
            "lastfct0": last_fct0,
            "service_names": [s["name"] for s in services],
            "lock_state": lock_state,
        }
        _write_scan_diag_file()
        return services, ens_label, ens_id, snr

    ipc.write_progress("DAB+ Suchlauf", "Regionale Kanäle...", color="blue")
    for ch in region_list:
        ipc.write_progress("DAB+ Suchlauf", f"Kanal {ch}...", color="blue")
        svcs, ens_label, ens_id, snr = _scan_channel(ch)
        scanned.append(ch)
        for svc in svcs:
            entry = {
                "name": svc["name"],
                "channel": ch,
                "ensemble": ens_label,
                "service_id": str(svc["service_id"] or "").strip(),
                "url_mp3": "",
                "id": f"dab_{svc['service_id'] or svc['name']}",
                "favorite": False,
                "enabled": True,
            }
            if not any(
                (str(e.get("service_id","") or "").strip() == entry["service_id"] and entry["service_id"])
                or (e["name"] == svc["name"] and e["channel"] == ch)
                for e in found
            ):
                found.append(entry)

    if len(found) < 3 and not requested_channels:
        log.info("DAB Scan: Regionalscan < 3 Sender — Vollscan...")
        ipc.write_progress("DAB+ Suchlauf", "Vollscan...", color="blue")
        for ch in full_list:
            if ch in scanned:
                continue
            ipc.write_progress("DAB+ Suchlauf", f"Vollscan {ch}...", color="blue")
            svcs, ens_label, ens_id, snr = _scan_channel(ch)
            scanned.append(ch)
            for svc in svcs:
                entry = {
                    "name": svc["name"],
                    "channel": ch,
                    "ensemble": ens_label,
                    "service_id": str(svc["service_id"] or "").strip(),
                    "url_mp3": "",
                    "id": f"dab_{svc['service_id'] or svc['name']}",
                    "favorite": False,
                    "enabled": True,
                }
                if not any(
                    (str(e.get("service_id","") or "").strip() == entry["service_id"] and entry["service_id"])
                    or (e["name"] == svc["name"] and e["channel"] == ch)
                    for e in found
                ):
                    found.append(entry)

    _last_scan_diag["found"] = len(found)
    _write_scan_diag_file()
    log.info(f"DAB Scan: FERTIG — {len(found)} Sender")
    return found




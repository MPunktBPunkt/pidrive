#!/usr/bin/env python3
"""cli_service.py — PiDrive CLI: Service-Layer (fachliche Kommandos)"""
import json
import os
import subprocess
import sys

# cli/service.py liegt unter pidrive/cli/ — Config ist unter pidrive/config/
BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # pidrive/
CONFIG_DIR = os.path.join(BASE_DIR, "config")

from cli.adapters import (
    IPCAdapter, HTTPAdapter,
    STATUS_FILE, MENU_FILE, SOURCE_STATE_FILE,
    BT_KNOWN_FILE, BT_DISC_FILE, DAB_DEBUG_FILE,
)

# Exit-Codes
EXIT_OK       = 0
EXIT_ERROR    = 1
EXIT_NOTFOUND = 2
EXIT_OFFLINE  = 3
EXIT_BUSY     = 4


class PiDriveService:
    def __init__(self, use_http: bool = False):
        self.ipc  = IPCAdapter()
        self.http = HTTPAdapter()
        self.use_http = use_http

    # ── Core ───────────────────────────────────────────────────────────────

    def require_online(self):
        if not self.ipc.core_online():
            raise SystemExit((EXIT_OFFLINE, "Core offline — PiDrive läuft nicht"))

    def send(self, cmd: str) -> dict:
        """Trigger senden. Gibt {"ok": True, "cmd": cmd} zurück."""
        if self.use_http:
            return self.http.post_cmd(cmd)
        self.ipc.write_cmd(cmd)
        return {"ok": True, "cmd": cmd}

    # ── Status ─────────────────────────────────────────────────────────────

    def get_status(self) -> dict:
        s  = self.ipc.read_json(STATUS_FILE, {})
        ss = self.ipc.read_json(SOURCE_STATE_FILE, {})
        return {
            "online":        self.ipc.core_online(),
            "source":        ss.get("source_current", "idle"),
            "radio":         s.get("radio", False),
            "radio_name":    s.get("radio_name", ""),
            "radio_type":    s.get("radio_type", ""),
            "track":         s.get("track", ""),
            "artist":        s.get("artist", ""),
            "dls":           s.get("dls_text", ""),
            "volume":        s.get("volume", "–"),
            "audio_out":     s.get("audio_out", "–"),
            "audio_eff":     s.get("audio_effective", "–"),
            "bt":            s.get("bt", False),
            "bt_device":     s.get("bt_device", ""),
            "bt_status":     s.get("bt_status", "–"),
            "wifi":          s.get("wifi", False),
            "wifi_ssid":     s.get("wifi_ssid", ""),
            "spotify":       s.get("spotify", False),
            "dab_attempting":  s.get("dab_attempting", False),
            "dab_play_state": s.get("dab_playback_state", ""),
        }

    def get_now(self) -> dict:
        s = self.ipc.read_json(STATUS_FILE, {})
        src = ""
        if s.get("spotify"):        src = "Spotify"
        elif s.get("radio"):        src = s.get("radio_type", "Radio")
        elif s.get("library"):      src = "Bibliothek"
        title  = (s.get("track") or s.get("radio_name") or
                  s.get("lib_track") or s.get("lib_artist") or "")
        artist = s.get("artist", "")
        dls    = s.get("dls_text", "")
        return {
            "source":             src,
            "title":              title,
            "artist":             artist,
            "dls":                dls,
            "metadata_unavailable": s.get("metadata_unavailable", False),
            "playing":            bool(s.get("radio") or s.get("spotify") or s.get("library")),
        }

    def get_quick(self) -> dict:
        s  = self.ipc.read_json(STATUS_FILE, {})
        ss = self.ipc.read_json(SOURCE_STATE_FILE, {})
        now = self.get_now()
        return {
            "source":    ss.get("source_current", "–"),
            "title":     now["title"] or "–",
            "volume":    s.get("volume", "–"),
            "audio":     s.get("audio_effective", "–"),
            "bt":        f"{'verbunden' if s.get('bt') else 'getrennt'} {s.get('bt_device','')}".strip(),
            "wifi":      f"{'an' if s.get('wifi') else 'aus'} {s.get('wifi_ssid','')}".strip(),
        }

    # ── Stationen ──────────────────────────────────────────────────────────

    def list_stations(self, source: str) -> list:
        fname = {
            "fm": "fm_stations.json", "dab": "dab_stations.json",
            "web": "stations.json",   "webradio": "stations.json",
        }.get(source.lower())
        if not fname:
            raise ValueError(f"Unbekannte Quelle: {source}")
        path = os.path.join(CONFIG_DIR, fname)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("stations", data) if isinstance(data, dict) else data

    def list_favorites(self) -> list:
        path = os.path.join(CONFIG_DIR, "favorites.json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("favorites", data) if isinstance(data, dict) else data

    def play(self, source: str, query: str) -> dict:
        """Spielt einen Sender anhand Name/Query auf der gegebenen Quelle."""
        src = source.lower()
        if src in ("web", "webradio"):
            stations = self.list_stations("web")
            match = _fuzzy(stations, query)
            if not match:
                raise LookupError(f"Webradio-Sender nicht gefunden: {query!r}")
            return self.send(f"play_web:{match['name']}")
        elif src == "dab":
            return self.send(f"play_dab:{query}")
        elif src == "fm":
            return self.send(f"play_fm:{query}")
        raise ValueError(f"Unbekannte Quelle: {source}")

    def play_favorite(self, query: str) -> dict:
        return self.send(f"favorites_play:{query}")

    # ── Bluetooth ──────────────────────────────────────────────────────────

    def bt_known(self) -> list:
        return self.ipc.read_json(BT_KNOWN_FILE, {}).get("devices", [])

    def bt_discovered(self) -> list:
        return self.ipc.read_json(BT_DISC_FILE, {}).get("devices", [])

    def bt_resolve(self, query: str) -> dict | None:
        q = query.strip().lower()
        for d in (self.bt_discovered() + self.bt_known()):
            if q == (d.get("mac","")).lower() or q in (d.get("name","")).lower():
                return d
        return None

    # ── DAB ────────────────────────────────────────────────────────────────

    def dab_status(self) -> dict:
        if self.use_http:
            try:
                return self.http.get_json("/api/dab/status")
            except Exception:
                pass
        return {"ok": True, "data": self.ipc.read_json(DAB_DEBUG_FILE, {})}

    # ── System ─────────────────────────────────────────────────────────────

    def run_diagnose(self) -> str:
        """Startet diagnose.py als Subprocess und gibt Ausgabe zurück."""
        diag_path = os.path.join(BASE_DIR, "diagnose.py")
        try:
            r = subprocess.run(
                [sys.executable, diag_path],
                capture_output=True, text=True, timeout=30
            )
            return r.stdout + (r.stderr[:200] if r.stderr else "")
        except Exception as e:
            return f"Diagnose-Fehler: {e}"

    def system_resources(self) -> dict:
        if self.use_http:
            try:
                return self.http.get_json("/api/system/resources")
            except Exception:
                pass
        # Fallback: Shell
        def _sh(cmd):
            try:
                return subprocess.check_output(cmd, shell=True, text=True).strip()
            except Exception:
                return "–"
        return {
            "ram":     _sh("free -m | awk 'NR==2{print $3\"/\"$2\" MB\"}'"),
            "disk":    _sh("df -h / | awk 'NR==2{print $3\"/\"$2\" (\"$5\")\"}'"),
            "uptime":  _sh("uptime -p"),
            "throttled": _sh("vcgencmd get_throttled 2>/dev/null | cut -d= -f2"),
        }

    def raspotify_status(self) -> dict:
        """Raspotify-Status und Anleitung zur Aktivierung."""
        import subprocess as _sp
        r = _sp.run(['systemctl', 'is-active', 'raspotify'],
                    capture_output=True, text=True)
        active = r.stdout.strip() == 'active'
        r2 = _sp.run(['systemctl', 'is-enabled', 'raspotify'],
                     capture_output=True, text=True)
        enabled = r2.stdout.strip() == 'enabled'
        return {
            'active':  active,
            'enabled': enabled,
            'enable_cmd':  'sudo systemctl enable --now raspotify',
            'oauth_cmd':   ('sudo systemctl stop raspotify && '
                            '/usr/bin/librespot --name PiDrive --enable-oauth '
                            '--system-cache /var/cache/raspotify'),
        }

    def get_version(self) -> str:
        vf = os.path.join(BASE_DIR, "VERSION")
        try:
            return open(vf).read().strip()
        except Exception:
            return "–"

    def log(self, target: str = "core", lines: int = 40) -> str:
        svc_map = {
            "core": "pidrive_core", "display": "pidrive_display",
            "app": "pidrive_core", "avrcp": "pidrive_avrcp",
        }
        svc = svc_map.get(target, target)
        try:
            return subprocess.check_output(
                f"journalctl -u {svc} -n {lines} --no-pager 2>/dev/null",
                shell=True, text=True
            )
        except Exception as e:
            return f"Log nicht verfügbar: {e}"


    # ── Live-Watch Methoden ────────────────────────────────────────────────

    def watch_bt_scan(self, scan_seconds: int = 22, on_device=None, on_tick=None):
        """BT-Scan starten und live Geräte zurückgeben.
        on_device(device_dict) wird aufgerufen wenn neues Gerät erscheint.
        on_tick(elapsed, total) wird aufgerufen jede Sekunde.
        Gibt am Ende alle gefundenen Geräte zurück.
        """
        import time
        self.send("bt_scan")
        time.sleep(1.0)   # kurz warten bis Core den Scan startet

        seen_macs = set()
        found = []
        start = time.time()

        while True:
            elapsed = time.time() - start
            if elapsed > scan_seconds + 3:
                break

            # Entdeckte Geräte aus IPC-Datei lesen
            devs = self.ipc.read_json("/tmp/pidrive_bt_devices.json",
                                       {}).get("devices", [])
            for d in devs:
                mac = d.get("mac", "")
                if mac and mac not in seen_macs:
                    seen_macs.add(mac)
                    found.append(d)
                    if on_device:
                        on_device(d)

            if on_tick:
                on_tick(int(elapsed), scan_seconds)

            time.sleep(1.5)

        return found

    def watch_dab_play(self, station_name: str, timeout: int = 30,
                        on_status=None, on_log_line=None):
        """DAB-Station starten und live Status verfolgen.
        on_status(state_dict) bei jeder Statusänderung.
        on_log_line(line) für jede neue Zeile im DAB-Errlog.
        Gibt finalen Status zurück: 'locked'|'no_lock'|'partial_sync'|'timeout'
        """
        import time, os, glob
        self.send(f"play_dab:{station_name}")
        time.sleep(0.8)

        start    = time.time()
        last_state = ""
        log_pos  = 0   # Leseposition im Errlog

        while True:
            elapsed = time.time() - start
            if elapsed > timeout:
                return "timeout"

            # Status-JSON lesen
            s = self.ipc.read_json("/tmp/pidrive_status.json", {})
            state = s.get("dab_playback_state", "")
            if state and state != last_state:
                last_state = state
                if on_status:
                    on_status({
                        "state":       state,
                        "sync_ok":     s.get("dab_sync_ok", False),
                        "pcm":         s.get("dab_pcm_seen", False),
                        "sync_seen":   s.get("dab_sync_seen", False),
                        "attempting":  s.get("dab_attempting", False),
                        "last_error":  s.get("dab_last_error", ""),
                        "elapsed":     int(elapsed),
                    })
                if state in ("locked", "pcm_only"):
                    return "locked"
                if state == "no_lock" and elapsed > 15:
                    return "no_lock"

            # DAB Errlog tail
            try:
                # Neueste Errlog-Datei finden
                pattern = "/tmp/pidrive_dab_*.err"
                errlogs = sorted(glob.glob(pattern))
                if errlogs:
                    errlog = errlogs[-1]
                    with open(errlog) as f:
                        f.seek(0, 2)  # initial ans Ende
                        if log_pos == 0:
                            log_pos = max(0, f.tell() - 500)
                        f.seek(log_pos)
                        new = f.read()
                        if new:
                            log_pos += len(new.encode())
                            for line in new.splitlines():
                                line = line.strip()
                                if line and on_log_line:
                                    on_log_line(line)
            except Exception:
                pass

            time.sleep(1.5)


    # ── Debug ──────────────────────────────────────────────────────────────

    def debug_state(self) -> dict:
        s  = self.ipc.read_json(STATUS_FILE, {})
        ss = self.ipc.read_json(SOURCE_STATE_FILE, {})
        mn = self.ipc.read_json("/tmp/pidrive_menu.json", {})
        return {"status": s, "source_state": ss, "menu": mn}


def _fuzzy(stations: list, query: str) -> dict | None:
    q = query.strip().lower()
    # Exact match first
    for s in stations:
        if q == (s.get("name","") or "").lower():
            return s
    # Partial match
    for s in stations:
        if q in (s.get("name","") or "").lower():
            return s
    return None

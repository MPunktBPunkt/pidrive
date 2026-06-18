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
        vol = self.get_volume()
        return {
            "online":        self.ipc.core_online(),
            "source":        ss.get("source_current", "idle"),
            "volume":        vol,
            "radio":         s.get("radio", False),
            "radio_name":    s.get("radio_name", ""),
            "radio_type":    s.get("radio_type", ""),
            "track":         s.get("track", ""),
            "artist":        s.get("artist", ""),
            "dls":           s.get("dls_text", ""),
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
        s  = self.ipc.read_json(STATUS_FILE, {})
        ss = self.ipc.read_json(SOURCE_STATE_FILE, {})
        src = ""
        # source_current ist autoritativ — spotify=True heisst nur Raspotify läuft
        _cur = ss.get("source_current", "")
        _src_labels = {"spotify":"Spotify Connect","library":"Bibliothek",
                       "local":"Lokal","scanner":"Scanner"}
        if _cur in _src_labels:       src = _src_labels[_cur]
        elif _cur in ("dab","fm","webradio"): src = s.get("radio_type", _cur.upper())
        elif _cur and _cur != "idle": src = _cur.upper()
        elif s.get("radio"):          src = s.get("radio_type", "Radio")
        title  = (s.get("track") or s.get("radio_name") or
                  s.get("lib_track") or s.get("lib_artist") or "")
        _src_err = s.get("source_error", "")
        artist = s.get("artist", "")
        dls    = s.get("dls_text", "")
        return {
            "source":             src,
            "title":              title,
            "artist":             artist,
            "dls":                dls,
            "metadata_unavailable": s.get("metadata_unavailable", False),
            "playing":            (_cur not in ("", "idle", None)),
            "source_error":       _src_err,
        }

    def get_volume(self) -> int | None:
        """Liest Lautstärke: erst settings.json (aktuell nach vol_up/down), dann PA-Fallback."""
        # settings["volume"] wird von audio.volume_up/down sofort aktualisiert
        try:
            import json as _j, os as _os
            _cfg = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
                                 "config", "settings.json")
            _vol = _j.load(open(_cfg)).get("volume")
            if _vol is not None:
                return int(_vol)
        except Exception:
            pass
        # Fallback: aktuellen PA-Sink direkt abfragen (nicht @DEFAULT_SINK@)
        import subprocess, re as _re
        try:
            # Finde aktiven Sink aus status.json
            _status = self.get_status()
            _route = _status.get("audio_effective", "") or _status.get("audio_out", "")
            # Versuche PA direkt (aktiver Sink aus pactl)
            r = subprocess.run(
                "PULSE_SERVER=unix:/var/run/pulse/native pactl list sinks short 2>/dev/null",
                shell=True, capture_output=True, text=True, timeout=2
            )
            # nimm ersten non-null Sink
            for line in r.stdout.splitlines():
                if "null" not in line.lower() and "pidrive_null" not in line.lower():
                    sink_name = line.split()[1] if len(line.split()) > 1 else "@DEFAULT_SINK@"
                    rv = subprocess.run(
                        f"PULSE_SERVER=unix:/var/run/pulse/native pactl get-sink-volume {sink_name}",
                        shell=True, capture_output=True, text=True, timeout=2)
                    m = _re.search(r'(\d+)%', rv.stdout)
                    return int(m.group(1)) if m else None
        except Exception:
            pass
        return None

    def get_quick(self) -> dict:
        s  = self.ipc.read_json(STATUS_FILE, {})
        ss = self.ipc.read_json(SOURCE_STATE_FILE, {})
        now = self.get_now()
        vol = self.get_volume()
        _cur = ss.get("source_current", "")
        # Wenn idle: keinen veralteten Titel zeigen
        _title = now["title"] if _cur not in ("", "idle") else "–"
        return {
            "source":    _cur or "idle",
            "title":     _title or "–",
            "volume":    (str(vol) + "%") if vol is not None else "–",
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
        """Gibt Favoriten aus favorites.json PLUS starred Eintraege aus Stationslisten."""
        import json as _json
        favs = []
        # Quelle 1: favorites.json (explizit hinzugefügt)
        try:
            with open(os.path.join(CONFIG_DIR, "favorites.json"), encoding="utf-8") as f:
                data = _json.load(f)
            favs = data.get("favorites", []) if isinstance(data, dict) else data
        except Exception:
            pass
        # Quelle 2: favorite=True in Stationslisten (★ Markierungen)
        known_names = {f.get("name","").lower() for f in favs}
        for src_file, src_label in [
            ("dab_stations.json", "dab"),
            ("fm_stations.json",  "fm"),
            ("stations.json",     "webradio"),
        ]:
            try:
                with open(os.path.join(CONFIG_DIR, src_file), encoding="utf-8") as f:
                    raw = _json.load(f)
                stations = raw.get("stations", raw) if isinstance(raw, dict) else raw
                for s in stations:
                    if s.get("favorite") and s.get("name","").lower() not in known_names:
                        favs.append({
                            "name":   s["name"],
                            "source": src_label,
                            "from_station_list": True,
                        })
                        known_names.add(s.get("name","").lower())
            except Exception:
                pass
        return favs

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
        st = self.ipc.read_json(STATUS_FILE, {})
        dbg = self.ipc.read_json(DAB_DEBUG_FILE, {})
        merged = dict(dbg)
        merged["dab_playback_state"] = st.get("dab_playback_state") or dbg.get("state") or dbg.get("dab_state", "")
        merged["dab_sync_ok"] = st.get("dab_sync_ok", dbg.get("sync_ok"))
        merged["dab_pcm_seen"] = st.get("dab_pcm_seen", dbg.get("pcm_seen"))
        merged["dab_sync_seen"] = st.get("dab_sync_seen", dbg.get("sync_seen"))
        merged["dab_last_error"] = st.get("dab_last_error", dbg.get("last_error_line", ""))
        merged["dab_attempting"] = st.get("dab_attempting")
        merged["dls"] = st.get("dls") or st.get("dls_text") or dbg.get("last_dls_raw", "")
        return {"ok": True, "data": merged}

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
            "core": "pidrive_core",
            "app": "pidrive_core", "avrcp": "pidrive_avrcp",
        }
        svc = svc_map.get(target, target)
        try:
            out = subprocess.check_output(
                f"journalctl -u {svc} -n {lines} --no-pager 2>&1",
                shell=True, text=True
            )
            if "-- No entries --" in out or not out.strip():
                import os as _os, grp as _grp
                try:
                    _gids = [g.gr_gid for g in _grp.getgrall()
                             if _os.environ.get("USER","") in g.gr_mem]
                    _gnames = [g.gr_name for g in _grp.getgrall() if g.gr_gid in _gids]
                    if "systemd-journal" not in _gnames:
                        return ("-- Keine Log-Eintraege --\n"
                                "Tipp: pidrive-User ist nicht in systemd-journal Gruppe\n"
                                "  Fix: sudo usermod -a -G systemd-journal $USER && su - $USER\n"
                                "  Oder: su root && journalctl -u " + svc + " -n " + str(lines))
                except Exception: pass
            return out
        except Exception as e:
            return f"Log nicht verfuegbar: {e}"



    def watch_bt_connect(self, mac, name="?", timeout=20, on_status=None):
        """BT-Connect senden und auf Verbindung warten.
        Gibt 'connected', 'failed' oder 'timeout' zurueck.
        """
        import time
        self.send("bt_connect:" + mac)
        start = time.time()
        last = ""
        while True:
            elapsed = time.time() - start
            if elapsed > timeout:
                return "timeout"
            d = self.ipc.read_json("/tmp/pidrive_status.json", {})
            state = "connected" if d.get("bt") and d.get("bt_device","").replace("-",":").upper() == mac.upper() else                     "connecting" if d.get("bt_on") else "failed"
            if state != last:
                last = state
                if on_status: on_status({"state": state, "elapsed": int(elapsed), "mac": mac})
                if state == "connected": return "connected"
            time.sleep(1.5)


    # ── DAB Live Monitor ──────────────────────────────────────────────────

    def get_dab_live_snapshot(self) -> dict:
        """Aggregiert Status, Source-State und DAB-Debug zu einem Live-Snapshot."""
        import time as _t
        s  = self.ipc.read_json(STATUS_FILE, {})
        ss = self.ipc.read_json(SOURCE_STATE_FILE, {})
        dd = self.ipc.read_json(DAB_DEBUG_FILE, {})

        snap = {
            "ts":                 _t.time(),
            "online":             self.ipc.core_online(),
            # Quelle + Transition
            "source_current":     ss.get("source_current", s.get("source_current", "?")),
            "transition":         ss.get("transition", False),
            "audio_route":        ss.get("audio_route", s.get("audio_out", "?")),
            # Wiedergabe
            "radio_playing":      bool(s.get("radio")),
            "radio_name":         s.get("radio_name", "") or dd.get("station", ""),
            "channel":            dd.get("channel", ""),
            "service_id":         dd.get("service_id", ""),
            "ensemble":           dd.get("ensemble", ""),
            # DAB Empfangsstatus (aus status.json primär)
            "dab_playback_state": s.get("dab_playback_state", dd.get("state", "?")),
            "dab_attempting":     bool(s.get("dab_attempting")),
            "dab_sync_ok":        bool(s.get("dab_sync_ok")),
            "dab_sync_seen":      bool(s.get("dab_sync_seen") or dd.get("sync_seen")),
            "dab_partial_sync":   bool(s.get("dab_partial_sync")),
            "dab_pcm_seen":       bool(s.get("dab_pcm_seen") or dd.get("pcm_seen")),
            "dab_audio_ready":    bool(s.get("dab_audio_ready")),
            "dab_superframe_seen":bool(s.get("dab_superframe_seen") or dd.get("superframe_seen")),
            # Fehler + DLS
            "last_error":         s.get("dab_last_error", "") or dd.get("last_error_line", ""),
            "dls_text":           s.get("dls_text", "") or dd.get("last_dls_raw", ""),
            "artist":             s.get("artist", "") or dd.get("last_dls_artist", ""),
            "track":              s.get("track", "") or dd.get("last_dls_track", ""),
            # Session (aus debug)
            "session_id":         dd.get("session_id", ""),
            "sess_err_file":      dd.get("sess_err_file", ""),
            # Warnungen
            "warnings":           [],
        }

        # Warnregeln: Zustandswidersprüche sichtbar machen
        if snap["dab_pcm_seen"] and not snap["radio_playing"]:
            snap["warnings"].append("PCM gesehen aber radio_playing=nein")
        if snap["dab_sync_seen"] and snap["dab_playback_state"] == "no_lock":
            snap["warnings"].append("Sync gesehen aber State=no_lock")
        if snap["dab_audio_ready"] and not snap["dab_sync_ok"]:
            snap["warnings"].append("audio_ready ohne stabilen Sync")
        if snap["source_current"] != "dab" and snap["session_id"]:
            snap["warnings"].append("DAB-Session aktiv aber source_current!='dab'")
        return snap

    # Felder die Change-Detection auslösen
    _DAB_LIVE_CHANGE_KEYS = [
        "session_id", "source_current", "radio_name", "channel",
        "dab_playback_state", "dab_attempting", "dab_sync_ok",
        "dab_sync_seen", "dab_pcm_seen", "dab_audio_ready",
        "dab_superframe_seen", "radio_playing", "last_error", "dls_text",
    ]

    def iter_dab_live(self, interval=1.0, changes=False, once=False):
        """Generator: liefert Snapshots. Bei changes=True nur bei Änderung."""
        import time as _t
        prev = None
        while True:
            snap = self.get_dab_live_snapshot()
            if once:
                yield snap, True
                return
            if changes and prev is not None:
                diff = {k: snap[k] for k in self._DAB_LIVE_CHANGE_KEYS
                        if snap.get(k) != prev.get(k)}
                if diff:
                    yield snap, diff
            else:
                yield snap, None
            prev = snap
            _t.sleep(interval)

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

    def watch_dab_play(self, station_name, timeout=55, on_status=None, on_log_line=None):
        """DAB-Station starten und live Status verfolgen.
        Gibt 'locked', 'no_lock', 'partial_sync' oder 'timeout' zurueck.
        """
        import time, glob
        # Zustand VOR dem Start merken um ihn zu ignorieren
        pre = self.ipc.read_json("/tmp/pidrive_status.json", {})
        initial_state = pre.get("dab_playback_state", "")
        initial_ts    = pre.get("ts", 0)

        self.send("play_dab:" + station_name)
        time.sleep(1.5)  # Core braucht Zeit um neuen Versuch zu starten

        start      = time.time()
        last_state = ""
        best_state = ""
        log_pos    = 0
        RANK = {"locked": 4, "pcm_only": 3, "partial_sync": 2, "no_lock": 1, "starting": 0}

        while True:
            elapsed = time.time() - start
            if elapsed > timeout:
                return "no_lock" if best_state in ("no_lock", "partial_sync") else "timeout"

            s     = self.ipc.read_json("/tmp/pidrive_status.json", {})
            state = s.get("dab_playback_state", "")
            cur_ts = s.get("ts", 0)

            # Initialen Zustand ignorieren solange ts unveraendert
            if state == initial_state and cur_ts == initial_ts and elapsed < 5:
                time.sleep(0.5)
                continue

            if state and state != last_state:
                last_state = state
                if RANK.get(state, -1) > RANK.get(best_state, -1):
                    best_state = state
                if on_status:
                    on_status({
                        "state":      state,
                        "sync_ok":    s.get("dab_sync_ok", False),
                        "pcm":        s.get("dab_pcm_seen", False),
                        "attempting": s.get("dab_attempting", False),
                        "last_error": s.get("dab_last_error", ""),
                        "elapsed":    int(elapsed),
                    })
                if state in ("locked", "pcm_only"):
                    if s.get("dab_pcm_seen") or s.get("dab_audio_ready"):
                        return "locked"
                    if elapsed > 20:
                        return "partial_sync"
                if state == "partial_sync" and elapsed > 25:
                    return "partial_sync"  # laeuft mit instabilem Empfang
                if state == "no_lock" and elapsed > 12:
                    return "no_lock"

            # DAB Errlog tail — nur relevante Zeilen
            try:
                errlogs = sorted(glob.glob("/tmp/pidrive_dab_*.err"))
                if errlogs:
                    with open(errlogs[-1]) as f:
                        if log_pos == 0:
                            f.seek(0, 2)
                            log_pos = max(0, f.tell() - 500)
                        f.seek(log_pos)
                        new = f.read()
                        if new:
                            log_pos += len(new.encode("utf-8", errors="replace"))
                            for line in new.splitlines():
                                line = line.strip()
                                if not line:
                                    continue
                                low = line.lower()
                                # Rauschige Zeilen ausblenden
                                if any(x in low for x in [
                                    "synconphase", "synconendnull", "syncondnull",
                                    "lost coarse", "lost fine",
                                ]):
                                    continue
                                if on_log_line:
                                    on_log_line(line)
            except Exception:
                pass
            time.sleep(1.2)

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

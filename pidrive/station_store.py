#!/usr/bin/env python3
"""station_store.py — StationStore  v0.10.20
Ausgelagert aus menu_model.py."""

import os
import json
import time
import log
import ipc
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from modules.scanner import BANDS, VHF_RANGE, UHF_RANGE
try:
    from modules import favorites as _fav_mod
except Exception:
    _fav_mod = None

from menu_state import MenuNode

# ── StationStore ──────────────────────────────────────────────────────────────

class StationStore:
    """Senderlisten aus JSON-Dateien mit Hot-Reload und Merge."""

    def __init__(self, config_dir: str):
        self.config_dir  = config_dir
        self.fm:  List[dict] = []
        self.dab: List[dict] = []
        self.web: List[dict] = []
        self._mtimes: Dict[str, float] = {}

        self._fm_file  = self._path("fm_stations.json")
        self._dab_file = self._path("dab_stations.json")
        self._web_file = self._path("stations.json")
        self.webradio  = self.web

    def _path(self, name: str) -> str:
        return os.path.join(self.config_dir, name)

    def _mtime(self, name: str) -> float:
        try:
            return os.path.getmtime(self._path(name))
        except Exception:
            return 0.0

    def _load(self, name: str) -> List[dict]:
        p = self._path(name)
        if not os.path.exists(p):
            return []
        try:
            with open(p, encoding="utf-8") as f:
                raw = f.read().strip()
            if not raw:
                return []
            data = json.loads(raw)

            if isinstance(data, dict):
                stations = data.get("stations", [])
            elif isinstance(data, list):
                stations = data
            else:
                log.warn(f"StationStore: {name} unbekanntes Format")
                return []

            result = [
                s for s in stations
                if isinstance(s, dict)
                and s.get("name")
                and s.get("enabled", True)
            ]
            return result

        except json.JSONDecodeError as e:
            log.warn(f"StationStore: {name} JSON-Fehler: {e} — behalte alten Zustand")
            return getattr(self, {
                "fm_stations.json": "fm",
                "dab_stations.json": "dab",
                "stations.json": "web"
            }.get(name, "fm"), [])
        except Exception as e:
            log.warn(f"StationStore: {name} Ladefehler: {e}")
            return []

    def load_all(self):
        self.fm  = self._load("fm_stations.json")
        self.dab = self._load("dab_stations.json")
        self.web = self._load("stations.json")
        self.webradio = self.web

        self._fm_file  = self._path("fm_stations.json")
        self._dab_file = self._path("dab_stations.json")
        self._web_file = self._path("stations.json")

        for n in ("fm_stations.json", "dab_stations.json", "stations.json"):
            self._mtimes[n] = self._mtime(n)

        log.info(f"StationStore: FM={len(self.fm)} DAB={len(self.dab)} Web={len(self.web)}")

    def reload_if_changed(self) -> bool:
        changed = False
        for name, attr in [
            ("fm_stations.json", "fm"),
            ("dab_stations.json", "dab"),
            ("stations.json", "web")
        ]:
            mt = self._mtime(name)
            if mt != self._mtimes.get(name, 0):
                setattr(self, attr, self._load(name))
                self._mtimes[name] = mt
                log.info(f"StationStore: {name} neu geladen ({len(getattr(self, attr))} Sender)")
                changed = True
        return changed

    def reload_source(self, source: str):
        mapping = {
            "fm": "fm_stations.json",
            "dab": "dab_stations.json",
            "webradio": "stations.json",
            "web": "stations.json"
        }
        name = mapping.get(source)
        if name:
            attr = {
                "fm_stations.json": "fm",
                "dab_stations.json": "dab",
                "stations.json": "web"
            }[name]
            setattr(self, attr, self._load(name))
            self._mtimes[name] = self._mtime(name)
            if attr == "web":
                self.webradio = self.web
            log.info(f"StationStore: {source} neu geladen")

    def _write_json(self, path: str, stations: list, source: str):
        try:
            existing = {}
            try:
                with open(path, encoding="utf-8") as f:
                    existing = json.load(f)
            except Exception:
                pass

            existing["stations"] = stations
            existing["updated_at"] = int(time.time())

            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(existing, f, indent=2, ensure_ascii=False)
            os.replace(tmp, path)
        except Exception as _e:
            log.error(f"StationStore write {path}: {_e}")

    def _save(self, name: str, stations: List[dict]):
        import datetime
        data = {
            "version":    1,
            "updated_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "stations":   stations,
        }
        p   = self._path(name)
        tmp = p + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(tmp, p)
            log.info(f"StationStore: {name} gespeichert ({len(stations)} Sender)")
        except Exception as e:
            log.error(f"StationStore: {name} Speicherfehler: {e}")

    # ── Favoriten ─────────────────────────────────────────────────────────

    def set_favorite_fm(self, station_id: str, is_fav: bool):
        for s in self.fm:
            freq = str(s.get("freq_mhz", s.get("freq", "")))
            sid  = "fm_" + freq.replace(".", "_")
            if sid == station_id:
                s["favorite"] = is_fav
        self._write_json(self._fm_file, self.fm, "fm")

    def set_favorite_dab(self, station_id: str, is_fav: bool):
        for s in self.dab:
            sid = str(s.get("service_id", "") or "").strip()
            key = f"dab_{sid or s.get('name','?')}"
            if key == station_id:
                s["favorite"] = is_fav
        self._write_json(self._dab_file, self.dab, "dab")

    def set_favorite_web(self, station_id: str, is_fav: bool):
        for s in self.webradio:
            name = s.get("name", "?")
            if f"web_{name.lower().replace(' ', '_')[:20]}" == station_id:
                s["favorite"] = is_fav
        self._write_json(self._web_file, self.webradio, "webradio")

    # ── Save / Merge / Replace ────────────────────────────────────────────

    def save_dab(self, stations: List[dict]):
        existing = self._load("dab_stations.json")
        merged   = self._merge_dab(existing, stations)
        self._save("dab_stations.json", merged)
        self.dab = [s for s in merged if s.get("enabled", True)]
        self._mtimes["dab_stations.json"] = self._mtime("dab_stations.json")

    def replace_dab(self, stations: List[dict]):
        """
        DAB-Liste komplett ersetzen, Favoriten gleicher service_id/name übernehmen.
        """
        existing = self._load("dab_stations.json")
        fav_by_sid = {}
        fav_by_name = {}

        for s in existing:
            sid = str(s.get("service_id", "") or "").strip().lower()
            nm  = str(s.get("name", "") or "").strip().lower()
            if sid:
                fav_by_sid[sid] = bool(s.get("favorite", False))
            if nm:
                fav_by_name[nm] = bool(s.get("favorite", False))

        replaced = []
        for s in stations:
            row = dict(s)
            sid = str(row.get("service_id", "") or "").strip().lower()
            nm  = str(row.get("name", "") or "").strip().lower()
            row["favorite"] = fav_by_sid.get(sid, fav_by_name.get(nm, False))
            row["enabled"]  = row.get("enabled", True)
            replaced.append(row)

        self._save("dab_stations.json", replaced)
        self.dab = [s for s in replaced if s.get("enabled", True)]
        self._mtimes["dab_stations.json"] = self._mtime("dab_stations.json")

    def save_fm(self, stations: List[dict]):
        existing = self._load("fm_stations.json")
        merged   = self._merge_fm(existing, stations)
        self._save("fm_stations.json", merged)
        self.fm = [s for s in merged if s.get("enabled", True)]
        self._mtimes["fm_stations.json"] = self._mtime("fm_stations.json")

    def _merge_dab(self, existing: List[dict], scanned: List[dict]) -> List[dict]:
        """
        DAB Merge:
        - bevorzugt service_id
        - Fallback: channel + normalized(name)
        - behält Favoriten
        - behält Reihenfolge der bestehenden Liste so weit wie möglich
        """
        def _norm_name(x):
            return (x or "").strip().lower()

        def _key_sid(s):
            sid = str(s.get("service_id", "") or "").strip().lower()
            return f"sid:{sid}" if sid else ""

        def _key_fb(s):
            ch = str(s.get("channel", "") or "").strip().upper()
            nm = _norm_name(s.get("name", ""))
            return f"chname:{ch}:{nm}" if ch and nm else ""

        scanned_by_sid = {}
        scanned_by_fb  = {}

        for s in scanned:
            ks = _key_sid(s)
            kf = _key_fb(s)
            if ks:
                scanned_by_sid[ks] = dict(s)
            if kf:
                scanned_by_fb[kf] = dict(s)

        result = []
        used = set()

        # 1) Bestehende Reihenfolge anreichern
        for old in existing:
            ks_old = _key_sid(old)
            kf_old = _key_fb(old)
            new = None
            used_key = ""

            if ks_old and ks_old in scanned_by_sid:
                new = dict(scanned_by_sid[ks_old]); used_key = ks_old
            elif kf_old and kf_old in scanned_by_fb:
                new = dict(scanned_by_fb[kf_old]); used_key = kf_old

            if new:
                new["favorite"] = old.get("favorite", False)
                new["enabled"]  = old.get("enabled", True)
                if old.get("name"):
                    new["name"] = old["name"]
                result.append(new)
                used.add(used_key)
            else:
                keep = dict(old)
                keep.setdefault("service_id", "")
                keep.setdefault("url_mp3", "")
                keep.setdefault("enabled", True)
                keep.setdefault("favorite", False)
                result.append(keep)

        # 2) Neue unbekannte Sender anhängen
        for s in scanned:
            ks = _key_sid(s)
            kf = _key_fb(s)
            if ks and ks in used:
                continue
            if (not ks) and kf and kf in used:
                continue

            if ks:
                used.add(ks)
            elif kf:
                used.add(kf)

            row = dict(s)
            row.setdefault("favorite", False)
            row.setdefault("enabled", True)
            result.append(row)

        return result

    def _merge_fm(self, existing: List[dict], scanned: List[dict]) -> List[dict]:
        def freq_key(s):
            try:
                return round(float(s.get("freq_mhz") or s.get("freq", 0)), 1)
            except Exception:
                return 0.0

        by_freq = {freq_key(s): s for s in existing}
        result  = []

        for s in scanned:
            key = freq_key(s)
            if key in by_freq:
                old    = by_freq[key]
                merged = dict(s)
                merged["favorite"] = old.get("favorite", False)
                merged["enabled"]  = old.get("enabled", True)
                if old.get("name"):
                    merged["name"] = old["name"]
                result.append(merged)
            else:
                result.append(dict(s))

        return result




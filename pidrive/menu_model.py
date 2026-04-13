import ipc
"""
menu_model.py - PiDrive Menümodell v0.7.10
Baumstruktur statt flacher Kategorien/Items.

Architektur nach GPT-5.4 Analyse:
- MenuNode: Knoten im Baum (folder/station/action/toggle/info)
- MenuState: Stack-basierte Navigation, beliebig tief
- StationStore: Senderlisten aus JSON, Hot-Reload, Merge-Strategie

Typen:
  folder  → führt in Untermenü (children)
  station → abspielbarer Sender
  action  → führt Aktion aus
  toggle  → An/Aus Schalter
  info    → reine Anzeige
"""

import os
import json
try:
    from modules import favorites as _fav_mod
except Exception:
    _fav_mod = None
import time
import log
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


# ── MenuNode ──────────────────────────────────────────────────────────────────

@dataclass
class MenuNode:
    id:       str
    label:    str
    type:     str   # folder / station / action / toggle / info

    children:  List["MenuNode"] = field(default_factory=list)
    action:    Optional[str]    = None   # Action-ID fuer type=action
    source:    Optional[str]    = None   # Quelle: fm / dab / webradio / spotify
    playable:  bool = False
    active:    bool = False              # Wird gerade abgespielt
    meta:      Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id":       self.id,
            "label":    self.label,
            "type":     self.type,
            "action":   self.action,
            "source":   self.source,
            "playable": self.playable,
            "active":   self.active,
            "meta":     self.meta,
            "has_children": len(self.children) > 0,
        }


# ── MenuState ─────────────────────────────────────────────────────────────────

class MenuState:
    """Stack-basierte Navigation — beliebig viele Ebenen."""

    def __init__(self, root: MenuNode):
        self.root          = root
        self._stack:   List[MenuNode] = [root]
        self._cursors: List[int]      = [0]
        self.rev: int = 0   # Aenderungszaehler fuer UI-Invalidierung

    # ── Eigenschaften ──────────────────────────────────────────────────────

    @property
    def current(self) -> MenuNode:
        return self._stack[-1]

    @property
    def cursor(self) -> int:
        return self._cursors[-1]

    @property
    def depth(self) -> int:
        return len(self._stack)

    @property
    def path(self) -> List[str]:
        return [n.label for n in self._stack]

    @property
    def current_nodes(self) -> List[MenuNode]:
        return self.current.children

    @property
    def selected(self) -> Optional[MenuNode]:
        nodes = self.current_nodes
        if not nodes:
            return None
        return nodes[min(self.cursor, len(nodes) - 1)]

    # ── Navigation ─────────────────────────────────────────────────────────

    def key_up(self):
        if self._cursors[-1] > 0:
            self._cursors[-1] -= 1
            self.rev += 1

    def key_down(self):
        n = len(self.current_nodes)
        if n > 0 and self._cursors[-1] < n - 1:
            self._cursors[-1] += 1
            self.rev += 1

    def key_enter(self):
        """Tiefer gehen oder Aktion ausführen."""
        node = self.selected
        if node is None:
            return
        if node.type == "folder" and node.children:
            self._stack.append(node)
            self._cursors.append(0)
            self.rev += 1
            return node
        elif node.type in ("station", "action", "toggle"):
            self.rev += 1
            return node  # Caller fuehrt Aktion aus
        return None

    def key_back(self):
        if len(self._stack) > 1:
            self._stack.pop()
            self._cursors.pop()
            self.rev += 1

    def key_left(self):
        self.key_back()

    def key_right(self):
        return self.key_enter()

    def navigate_to(self, node_id: str):
        """Direkt zu einem Knoten navigieren (fuer cat:X Trigger)."""
        for i, node in enumerate(self.root.children):
            if node.id == node_id or node.label.lower() == node_id.lower():
                self._stack   = [self.root, node]
                self._cursors = [i, 0]
                self.rev += 1
                return True
        # Top-Level-Index erlauben (cat:0..3)
        try:
            idx = int(node_id)
            if 0 <= idx < len(self.root.children):
                node = self.root.children[idx]
                self._stack   = [self.root, node]
                self._cursors = [idx, 0]
                self.rev += 1
                return True
        except (ValueError, TypeError):
            pass
        return False

    def clamp_cursors(self):
        """Cursor nach Rebuild in gültigem Bereich halten (GPT-5.4 Phase 1)."""
        for depth in range(len(self._stack)):
            if depth == 0:
                # root: cursor = index des aktuellen 2. Stacks-Elements
                if len(self._stack) > 1:
                    try:
                        self._cursors[0] = self.root.children.index(self._stack[1])
                    except ValueError:
                        self._cursors[0] = 0
            else:
                parent   = self._stack[depth - 1]
                children = parent.children
                old_cur  = self._cursors[depth] if depth < len(self._cursors) else 0
                if not children:
                    self._cursors[depth] = 0
                else:
                    self._cursors[depth] = min(old_cur, len(children) - 1)

    def export(self) -> dict:
        """Menüzustand als Dict für IPC/JSON."""
        nodes = self.current_nodes
        cursor = min(self.cursor, max(0, len(nodes) - 1))
        return {
            "rev":       self.rev,
            "path":      self.path,
            "title":     " / ".join(self.path[-2:]) if len(self.path) > 1 else self.path[0],
            "cursor":    cursor,
            "can_back":  self.depth > 1,
            "nodes":     [n.to_dict() for n in nodes],
            # Compat-Felder fuer alte Display/Web-Versionen
            "cat":        0,
            "cat_label":  self._stack[1].label if len(self._stack) > 1 else self.root.label,
            "item":       cursor,
            "item_label": nodes[cursor].label if nodes else "",
            "categories": [c.label for c in self.root.children],
            "items":      [n.label for n in nodes],
        }


# ── StationStore ──────────────────────────────────────────────────────────────

class StationStore:
    """Senderlisten aus JSON-Dateien mit Hot-Reload und Merge."""

    def __init__(self, config_dir: str):
        self.config_dir  = config_dir
        self.fm:  List[dict] = []
        self.dab: List[dict] = []
        self.web: List[dict] = []
        self._mtimes: Dict[str, float] = {}

    def _path(self, name: str) -> str:
        return os.path.join(self.config_dir, name)

    def _mtime(self, name: str) -> float:
        try:
            return os.path.getmtime(self._path(name))
        except Exception:
            return 0.0

    def _load(self, name: str) -> List[dict]:
        """JSON laden — robust gegen alle Fehler, letzten Zustand erhalten."""
        p = self._path(name)
        if not os.path.exists(p):
            return []
        try:
            with open(p, encoding="utf-8") as f:
                raw = f.read().strip()
            if not raw:
                return []
            data = json.loads(raw)
            # Neues Format: {"stations": [...]}
            if isinstance(data, dict):
                stations = data.get("stations", [])
            elif isinstance(data, list):
                stations = data
            else:
                log.warn(f"StationStore: {name} unbekanntes Format")
                return []
            # Filtern: enabled + mindestens name vorhanden
            result = [s for s in stations
                      if isinstance(s, dict) and s.get("name")
                      and s.get("enabled", True)]
            return result
        except json.JSONDecodeError as e:
            log.warn(f"StationStore: {name} JSON-Fehler: {e} — behalte alten Zustand")
            return getattr(self, {"fm_stations.json":"fm","dab_stations.json":"dab",
                                   "stations.json":"web"}.get(name,"fm"), [])
        except Exception as e:
            log.warn(f"StationStore: {name} Ladefehler: {e}")
            return []

    def load_all(self):
        self.fm  = self._load("fm_stations.json")
        self.dab = self._load("dab_stations.json")
        self.web = self._load("stations.json")
        for n in ("fm_stations.json", "dab_stations.json", "stations.json"):
            self._mtimes[n] = self._mtime(n)
        log.info(f"StationStore: FM={len(self.fm)} DAB={len(self.dab)} Web={len(self.web)}")

    def reload_if_changed(self) -> bool:
        """Prüft Dateiänderungen, lädt bei Bedarf neu. Gibt True zurück wenn reload."""
        changed = False
        for name, attr in [("fm_stations.json","fm"),
                            ("dab_stations.json","dab"),
                            ("stations.json","web")]:
            mt = self._mtime(name)
            if mt != self._mtimes.get(name, 0):
                setattr(self, attr, self._load(name))
                self._mtimes[name] = mt
                log.info(f"StationStore: {name} neu geladen ({len(getattr(self,attr))} Sender)")
                changed = True
        return changed

    def set_favorite_fm(self, station_id: str, is_fav: bool):
        """FM Station als Favorit markieren/entfernen und speichern."""
        for s in self.fm:
            if f"fm_{str(s.get('freq_mhz',s.get('freq','')))
                    .replace('.','_')}" == station_id:
                s["favorite"] = is_fav
        self._write_json(self._fm_file, self.fm, "fm")

    def set_favorite_dab(self, station_id: str, is_fav: bool):
        """DAB Station als Favorit markieren/entfernen und speichern."""
        for s in self.dab:
            if f"dab_{s.get('service_id', s.get('name','?'))}" == station_id:
                s["favorite"] = is_fav
        self._write_json(self._dab_file, self.dab, "dab")

    def set_favorite_web(self, station_id: str, is_fav: bool):
        """Webradio Station als Favorit markieren/entfernen und speichern."""
        for s in self.webradio:
            name = s.get("name","?")
            if f"web_{name.lower().replace(' ','_')[:20]}" == station_id:
                s["favorite"] = is_fav
        self._write_json(self._web_file, self.webradio, "webradio")

    def _write_json(self, path: str, stations: list, source: str):
        """Senderliste in JSON-Datei schreiben."""
        try:
            import time as _t
            existing = {}
            try:
                with open(path) as _f:
                    existing = json.load(_f)
            except Exception:
                pass
            existing["stations"] = stations
            existing["updated_at"] = int(_t.time())
            tmp = path + ".tmp"
            with open(tmp, "w") as _f:
                json.dump(existing, _f, indent=2, ensure_ascii=False)
            import os as _os
            _os.replace(tmp, path)
        except Exception as _e:
            import log
            log.error(f"StationStore write {path}: {_e}")


    def reload_source(self, source: str):
        """Einzelne Quelle neu laden."""
        mapping = {"fm": "fm_stations.json", "dab": "dab_stations.json",
                   "webradio": "stations.json", "web": "stations.json"}
        name = mapping.get(source)
        if name:
            attr = {"fm_stations.json":"fm","dab_stations.json":"dab",
                    "stations.json":"web"}[name]
            setattr(self, attr, self._load(name))
            self._mtimes[name] = self._mtime(name)
            log.info(f"StationStore: {source} neu geladen")

    def save_dab(self, stations: List[dict]):
        """DAB-Stationen speichern (nach Scan, mit Merge)."""
        existing = self._load("dab_stations.json")
        merged   = self._merge_dab(existing, stations)
        self._save("dab_stations.json", merged)
        self.dab = [s for s in merged if s.get("enabled", True)]
        self._mtimes["dab_stations.json"] = self._mtime("dab_stations.json")

    def save_fm(self, stations: List[dict]):
        """FM-Stationen speichern (nach Scan, mit Merge)."""
        existing = self._load("fm_stations.json")
        merged   = self._merge_fm(existing, stations)
        self._save("fm_stations.json", merged)
        self.fm = [s for s in merged if s.get("enabled", True)]
        self._mtimes["fm_stations.json"] = self._mtime("fm_stations.json")

    def _save(self, name: str, stations: List[dict]):
        """Atomar speichern mit neuem Format."""
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

    def _merge_dab(self, existing: List[dict], scanned: List[dict]) -> List[dict]:
        """Merge: Favoriten und Namen aus existing behalten."""
        by_id = {s.get("service_id","") or s.get("name",""): s
                 for s in existing if s.get("service_id") or s.get("name")}
        result = []
        for s in scanned:
            key = s.get("service_id","") or s.get("name","")
            if key in by_id:
                old = by_id[key]
                merged = dict(s)
                merged["favorite"] = old.get("favorite", False)
                merged["enabled"]  = old.get("enabled",  True)
                if old.get("name") and old["name"] != key:
                    merged["name"] = old["name"]
                result.append(merged)
            else:
                result.append(dict(s))
        return result

    def _merge_fm(self, existing: List[dict], scanned: List[dict]) -> List[dict]:
        """Merge: Favoriten und Namen aus existing behalten."""
        def freq_key(s):
            try: return round(float(s.get("freq_mhz") or s.get("freq",0)), 1)
            except: return 0.0
        by_freq = {freq_key(s): s for s in existing}
        result  = []
        for s in scanned:
            key = freq_key(s)
            if key in by_freq:
                old    = by_freq[key]
                merged = dict(s)
                merged["favorite"] = old.get("favorite", False)
                merged["enabled"]  = old.get("enabled",  True)
                if old.get("name"):
                    merged["name"] = old["name"]
                result.append(merged)
            else:
                result.append(dict(s))
        return result


# ── Menübaum aufbauen ─────────────────────────────────────────────────────────

def build_tree(store: StationStore, S: dict, settings: dict) -> MenuNode:
    """Vollständigen Menübaum aus StationStore aufbauen."""

    def _station_nodes_fm(stations):
        """FM-Stationen mit Frequenz und Favoriten-Markierung."""
        # Favoriten zuerst
        favs    = [s for s in stations if s.get("favorite")]
        others  = [s for s in stations if not s.get("favorite")]
        ordered = favs + others
        nodes   = []
        for s in ordered:
            freq  = s.get("freq_mhz") or s.get("freq", "")
            name  = s.get("name", str(freq))
            fav   = "★ " if s.get("favorite") else ""
            label = f"{fav}{name}  {freq} MHz" if freq else f"{fav}{name}"
            active= (S.get("radio_type") == "FM" and
                     S.get("radio_station","").startswith(name[:10]))
            _fid = f"fm_{str(freq).replace('.','_')}"
            _meta_fm = {"freq": str(freq), "name": name, "favorite": s.get("favorite",False)}
            nodes.append(MenuNode(
                id=_fid, label=label, type="station",
                source="fm", playable=True, active=active,
                meta=_meta_fm,
                children=[_fav_node(_fid, name, "fm", _meta_fm,
                                   s.get("favorite",False))]
            ))
        return nodes

    def _station_nodes_dab(stations):
        """DAB-Stationen mit Ensemble und Favoriten."""
        favs   = [s for s in stations if s.get("favorite")]
        others = [s for s in stations if not s.get("favorite")]
        nodes  = []
        for s in (favs + others):
            name  = s.get("name", s.get("service_name", "?"))
            fav   = "★ " if s.get("favorite") else ""
            ens   = s.get("ensemble","")
            label = f"{fav}{name}  [{ens}]" if ens else f"{fav}{name}"
            active= (S.get("radio_type") == "DAB" and
                     S.get("radio_station","") == name)
            _did = f"dab_{s.get('service_id',name)}"
            _meta_dab = {"ensemble": ens, "service_id": s.get("service_id",""),
                         "name": name, "favorite": s.get("favorite",False)}
            nodes.append(MenuNode(
                id=_did, label=label, type="station",
                source="dab", playable=True, active=active,
                meta=_meta_dab,
                children=[_fav_node(_did, name, "dab", _meta_dab,
                                   s.get("favorite",False))]
            ))
        return nodes

    def _station_nodes_web(stations):
        """Webradio-Stationen mit Genre und Favoriten."""
        favs   = [s for s in stations if s.get("favorite")]
        others = [s for s in stations if not s.get("favorite")]
        nodes  = []
        for s in (favs + others):
            name  = s.get("name", "?")
            fav   = "★ " if s.get("favorite") else ""
            genre = s.get("genre","")
            label = f"{fav}{name}  [{genre}]" if genre else f"{fav}{name}"
            active= (S.get("radio_type") == "WEB" and
                     S.get("radio_station","") == name)
            _wid = f"web_{name.lower().replace(' ','_')[:20]}"
            _meta_web = {"url": s.get("url",""), "genre": genre,
                         "name": name, "favorite": s.get("favorite",False)}
            nodes.append(MenuNode(
                id=_wid, label=label, type="station",
                source="webradio", playable=True, active=active,
                meta=_meta_web,
                children=[_fav_node(_wid, name, "webradio", _meta_web,
                                    s.get("favorite",False))]
            ))
        return nodes


    def _fav_node(node_id, name, source, meta, is_fav):
        """Favorit-Toggle-Node für eine Station."""
        import json as _jj
        _lbl = ("☆ Aus Favoriten entfernen" if is_fav 
                else "★ Zu Favoriten hinzufuegen")
        _meta_str = _jj.dumps(meta, ensure_ascii=False)
        _action = f"fav_toggle:{source}:{node_id}:{name}:{_meta_str}"
        return MenuNode(
            id="fav_" + node_id, label=_lbl, type="action",
            action=_action)

    # ── Jetzt läuft ─────────────────────────────────────────────────────────
    now_playing = MenuNode(id="now_playing", label="Jetzt laeuft", type="folder", children=[
        MenuNode(id="np_source",  label="Quelle",      type="info"),
        MenuNode(id="np_title",   label="Titel/Sender", type="info"),
        MenuNode(id="spotify_tog",label="Spotify",      type="toggle",
                 action="spotify_toggle",
                 active=S.get("spotify", False)),
        MenuNode(id="audio_out",  label="Audioausgang", type="action",
                 action="audio_select"),
        MenuNode(id="vol_up",     label="Lauter",        type="action", action="vol_up"),
        MenuNode(id="vol_down",   label="Leiser",        type="action", action="vol_down"),
    ])

    # ── Quellen → FM ────────────────────────────────────────────────────────
    fm_sender = MenuNode(id="fm_stations", label="Sender", type="folder",
                         children=_station_nodes_fm(store.fm) or [
                             MenuNode(id="fm_empty", label="Kein Sender — Suchlauf starten",
                                      type="info")])
    fm_node = MenuNode(id="fm", label="FM Radio", type="folder", children=[
        MenuNode(id="fm_now",     label="Jetzt laeuft", type="info"),
        fm_sender,
        MenuNode(id="fm_scan",    label="Suchlauf starten", type="action", action="fm_scan"),
        MenuNode(id="fm_next",    label="Naechster Sender", type="action", action="fm_next"),
        MenuNode(id="fm_prev",    label="Vorheriger Sender",type="action", action="fm_prev"),
        MenuNode(id="fm_manual",  label="Frequenz manuell", type="action", action="fm_manual"),
    ])

    # ── Quellen → DAB+ ──────────────────────────────────────────────────────
    dab_sender = MenuNode(id="dab_stations", label="Sender", type="folder",
                          children=_station_nodes_dab(store.dab) or [
                              MenuNode(id="dab_empty", label="Kein Sender — Suchlauf starten",
                                       type="info")])
    dab_node = MenuNode(id="dab", label="DAB+", type="folder", children=[
        MenuNode(id="dab_now",    label="Jetzt laeuft", type="info"),
        dab_sender,
        MenuNode(id="dab_scan",   label="Suchlauf starten", type="action", action="dab_scan"),
        MenuNode(id="dab_next",   label="Naechster Sender", type="action", action="dab_next"),
        MenuNode(id="dab_prev",   label="Vorheriger Sender",type="action", action="dab_prev"),
    ])

    # ── Quellen → Webradio ──────────────────────────────────────────────────
    web_sender = MenuNode(id="web_stations", label="Sender", type="folder",
                          children=_station_nodes_web(store.web) or [
                              MenuNode(id="web_empty", label="Keine Stationen",
                                       type="info")])
    webradio_node = MenuNode(id="webradio", label="Webradio", type="folder", children=[
        MenuNode(id="web_now",    label="Jetzt laeuft", type="info"),
        web_sender,
        MenuNode(id="web_reload", label="Sender neu laden", type="action",
                 action="reload_stations:webradio"),
    ])

    # ── Quellen → Scanner ────────────────────────────────────────────────────
    def _scanner_band(band_id, label):
        # Aktuellen Kanal/Frequenz aus S-State lesen
        scanner_key = f"scanner_{band_id}"
        current_info = S.get(scanner_key, "")
        active = bool(S.get("radio_type") == "SCANNER" and
                      band_id.upper() in S.get("radio_station","").upper())
        info_label = f"▶ {current_info}" if (active and current_info) else                      (current_info or "– kein Kanal aktiv –")
        return MenuNode(id=band_id, label=label, type="folder",
                        active=active, children=[
            MenuNode(id=f"{band_id}_info",  label=info_label, type="info"),
            MenuNode(id=f"{band_id}_up",    label="Kanal +",
                     type="action", action=f"scan_up:{band_id}"),
            MenuNode(id=f"{band_id}_down",  label="Kanal -",
                     type="action", action=f"scan_down:{band_id}"),
            MenuNode(id=f"{band_id}_next",  label="Scan weiter",
                     type="action", action=f"scan_next:{band_id}"),
            MenuNode(id=f"{band_id}_prev",  label="Scan zurueck",
                     type="action", action=f"scan_prev:{band_id}"),
        ])

    scanner_node = MenuNode(id="scanner", label="Scanner", type="folder", children=[
        _scanner_band("pmr446",  "PMR446"),
        _scanner_band("freenet", "Freenet"),
        _scanner_band("lpd433",  "LPD433"),
        _scanner_band("vhf",     "VHF"),
        _scanner_band("uhf",     "UHF"),
    ])

    # ── Quellen → Bibliothek & Spotify ──────────────────────────────────────
    spotify_node = MenuNode(id="spotify", label="Spotify", type="folder", children=[
        MenuNode(id="spot_toggle", label="Spotify An/Aus", type="toggle",
                 action="spotify_toggle", active=S.get("spotify", False)),
        MenuNode(id="spot_status", label="Status", type="info"),
    ])

    lib_node = MenuNode(id="library", label="Bibliothek", type="folder", children=[
        MenuNode(id="lib_browse", label="Durchsuchen", type="action", action="lib_browse"),
        MenuNode(id="lib_stop",   label="Stop",        type="action", action="library_stop"),
        MenuNode(id="lib_path",   label="Pfad",        type="info"),
    ])

    # ── Quellen ─────────────────────────────────────────────────────────────
    quellen = MenuNode(id="sources", label="Quellen", type="folder", children=[
        spotify_node,
        lib_node,
        webradio_node,
        dab_node,
        fm_node,
        scanner_node,
    ])


    # ── Favoriten ─────────────────────────────────────────────────────────────
    fav_nodes = []
    if _fav_mod:
        for _fav in _fav_mod.get_all():
            _src  = _fav.get("source","")
            _id   = _fav.get("id","")
            _name = _fav.get("name", _id)
            _meta = _fav.get("meta", {})
            _lbl  = "★ " + _name
            if _src in ("fm","dab","webradio"):
                fav_nodes.append(MenuNode(
                    id="fav_" + _id, label=_lbl, type="station",
                    source=_src, meta=_meta))
            elif _src == "scanner":
                _band = _meta.get("band","pmr446")
                _ch   = _meta.get("ch", 1)
                fav_nodes.append(MenuNode(
                    id="fav_" + _id, label=_lbl, type="action",
                    action="scan_up:" + _band, meta=_meta))

    favoriten = MenuNode(id="favoriten", label="Favoriten", type="folder",
        children=fav_nodes or [MenuNode(id="fav_empty",
            label="Noch keine Favoriten", type="info")])

    # ── Verbindungen ─────────────────────────────────────────────────────────
    # BT: gefundene Geraete als Submenu (aus /tmp/pidrive_bt_devices.json)
    bt_devs = []
    try:
        import os as _os
        if _os.path.exists("/tmp/pidrive_bt_devices.json"):
            with open("/tmp/pidrive_bt_devices.json") as _f:
                _btd = json.load(_f)
            for _d in _btd.get("devices", []):
                _m = _d.get("mac",""); _n = _d.get("name",_m)
                _lbl = ("★ " if _d.get("known") else "") + _n
                bt_devs.append(MenuNode(
                    id="btd_" + _m.replace(":",""), label=_lbl,
                    type="action", action="bt_connect:" + _m,
                    meta={"mac": _m, "name": _n}))
    except Exception as _e:
        pass  # Datei noch nicht vorhanden oder JSON-Fehler
    bt_geraete = MenuNode(id="bt_geraete", label="Geraete", type="folder",
        children=bt_devs or [MenuNode(id="bt_hint",
            label="Zuerst scannen", type="info")])

    # WiFi: gefundene Netzwerke als Submenu (aus /tmp/pidrive_wifi_nets.json)
    wifi_nets = []
    try:
        import os as _os2
        if _os2.path.exists("/tmp/pidrive_wifi_nets.json"):
            with open("/tmp/pidrive_wifi_nets.json") as _f2:
                _wfd = json.load(_f2)
            for _n in _wfd.get("networks", []):
                _s = _n.get("ssid","")
                if _s:
                    wifi_nets.append(MenuNode(
                        id="wfn_" + _s.replace(" ","_")[:16], label=_s,
                        type="action", action="wifi_connect:" + _s,
                        meta={"ssid": _s}))
    except Exception as _e:
        pass  # Datei noch nicht vorhanden oder JSON-Fehler
    wifi_netze = MenuNode(id="wifi_netze", label="Netzwerke", type="folder",
        children=wifi_nets or [MenuNode(id="wifi_hint",
            label="Zuerst scannen", type="info")])

    verbindungen = MenuNode(id="connections", label="Verbindungen", type="folder", children=[
        MenuNode(id="bt_toggle",  label="Bluetooth An/Aus", type="toggle",
                 action="bt_toggle", active=S.get("bt", False)),
        MenuNode(id="bt_scan",    label="Geraete scannen",  type="action", action="bt_scan"),
        bt_geraete,
        MenuNode(id="bt_status",  label="Verbunden mit",    type="info"),
        MenuNode(id="wifi_toggle",label="WiFi An/Aus",      type="toggle",
                 action="wifi_toggle", active=S.get("wifi", False)),
        MenuNode(id="wifi_scan",  label="Netzwerke scannen",type="action", action="wifi_scan"),
        wifi_netze,
        MenuNode(id="wifi_status",label="SSID",             type="info"),
    ])

    # ── System ───────────────────────────────────────────────────────────────
    system = MenuNode(id="system", label="System", type="folder", children=[
        MenuNode(id="sys_ip",      label="IP Adresse",  type="info"),
        MenuNode(id="sys_info",    label="System-Info", type="action", action="sys_info"),
        MenuNode(id="sys_version", label="Version",     type="action", action="sys_version"),
        MenuNode(id="sys_reboot",  label="Neustart",    type="action", action="reboot"),
        MenuNode(id="sys_off",     label="Ausschalten", type="action", action="shutdown"),
        MenuNode(id="sys_update",  label="Update",      type="action", action="update"),
    ])

    # ── Root ─────────────────────────────────────────────────────────────────
    root = MenuNode(id="root", label="PiDrive", type="folder", children=[
        now_playing,
        favoriten,
        quellen,
        verbindungen,
        system,
    ])
    return root

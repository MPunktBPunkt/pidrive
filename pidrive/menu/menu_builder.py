#!/usr/bin/env python3
"""menu_builder.py — build_tree()  v0.11.123

Fahrtaugliches Menü für die Bedienung über BMW iDrive (AVRCP):
  - Nur up/down (Skip) + enter (Play/Pause) sind im Auto zuverlässig.
  - "Zurück" (Stop) ist je nach Fahrzeug nicht erreichbar → jeder Ordner hat
    einen expliziten "Zurueck"-Eintrag (per enter bedienbar).
  - Favoriten zuerst, quellenübergreifend (FM/DAB/Webradio/Spotify/Scanner).
  - Gefährliche/folgenreiche Aktionen (Reboot/Shutdown/Update, BT trennen/aus)
    laufen über eine Bestätigungs-Ebene (erster Eintrag = Abbrechen).
"""

import os
import json
import socket
import time
import log
import ipc
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from modules.radio.scanner import BANDS, VHF_RANGE, UHF_RANGE
try:
    from modules import favorites as _fav_mod
except Exception:
    _fav_mod = None

from menu.menu_state import MenuNode, MenuState
from menu.station_store import StationStore


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def _local_ip() -> str:
    """Aktuelle IP für die Anzeige im System-Menü."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.3)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "?"


def _back(prefix: str) -> MenuNode:
    """Expliziter Zurueck-Eintrag (per enter bedienbar, da Stop unzuverlässig)."""
    return MenuNode(id=f"{prefix}_back", label="Zurueck", type="action", action="back")


def _folder(node_id: str, label: str, children: List[MenuNode],
            active: bool = False) -> MenuNode:
    """Ordner mit vorangestelltem Zurueck-Eintrag."""
    return MenuNode(id=node_id, label=label, type="folder", active=active,
                    children=[_back(node_id)] + list(children))


def _confirm(prefix: str, label: str, confirm_label: str, action: str) -> MenuNode:
    """Bestätigungs-Ordner: erster Eintrag = Abbrechen (kein versehentliches Auslösen)."""
    return MenuNode(id=prefix, label=label, type="folder", children=[
        MenuNode(id=f"{prefix}_cancel", label="Abbrechen", type="action", action="back"),
        MenuNode(id=f"{prefix}_yes",    label=confirm_label, type="action", action=action),
    ])


# ── Menübaum aufbauen ─────────────────────────────────────────────────────────

def build_tree(store: StationStore, S: dict, settings: dict) -> MenuNode:
    """Vollständigen Menübaum aus StationStore aufbauen."""

    def _fav_node(node_id, name, source, meta, is_fav):
        """Pro-Station Favoriten-Umschalter (nur über WebUI erreichbar)."""
        import json as _jj
        _lbl = ("Aus Favoriten entfernen" if is_fav
                else "Zu Favoriten hinzufuegen")
        _meta_str = _jj.dumps(meta, ensure_ascii=False)
        _action = f"fav_toggle:{source}:{node_id}:{name}:{_meta_str}"
        return MenuNode(
            id="fav_" + node_id, label=_lbl, type="action",
            action=_action
        )

    def _station_nodes_fm(stations):
        favs    = [s for s in stations if s.get("favorite")]
        others  = [s for s in stations if not s.get("favorite")]
        nodes   = []

        for s in (favs + others):
            freq  = s.get("freq_mhz") or s.get("freq", "")
            name  = s.get("name", str(freq))
            fav   = "* " if s.get("favorite") else ""
            label = f"{fav}{name}  {freq} MHz" if freq else f"{fav}{name}"
            active = (
                S.get("radio_type") == "FM" and
                S.get("radio_station", "").startswith(name[:10])
            )
            _fid = f"fm_{str(freq).replace('.', '_')}"
            _meta_fm = {"freq": str(freq), "name": name, "favorite": s.get("favorite", False)}

            nodes.append(MenuNode(
                id=_fid, label=label, type="station",
                source="fm", playable=True, active=active,
                meta=_meta_fm,
                children=[_fav_node(_fid, name, "fm", _meta_fm, s.get("favorite", False))]
            ))
        return nodes

    def _station_nodes_dab(stations):
        """DAB-Sender flach (v0.11.123): Favoriten zuerst, dann alle Sender.
        Frühere Kanal-Gruppierung entfernt — bei einzeiligem iDrive-Display und
        Skip-Tasten ist eine flache Liste schneller bedienbar."""
        def _make_node(s):
            name   = s.get("name", s.get("service_name", "?"))
            fav    = "* " if s.get("favorite") else ""
            ens    = s.get("ensemble", "")
            sid    = str(s.get("service_id", "") or "").strip()
            ch     = str(s.get("channel", "") or "").strip().upper()
            active = (
                S.get("radio_type") == "DAB" and
                (S.get("radio_station", "") == name or S.get("radio_name", "") == name)
            )
            _did = f"dab_{sid or name.lower().replace(' ','_')}"
            _meta = {"ensemble": ens, "service_id": sid, "channel": ch,
                     "url_mp3": s.get("url_mp3", ""), "name": name,
                     "favorite": s.get("favorite", False)}
            return MenuNode(
                id=_did, label=f"{fav}{name}", type="station",
                source="dab", playable=True, active=active, meta=_meta,
                children=[_fav_node(_did, name, "dab", _meta, s.get("favorite", False))]
            )

        favs   = [s for s in stations if s.get("favorite")]
        others = [s for s in stations if not s.get("favorite")]
        return [_make_node(s) for s in (favs + others)]

    def _station_nodes_web(stations):
        favs   = [s for s in stations if s.get("favorite")]
        others = [s for s in stations if not s.get("favorite")]
        nodes  = []

        for s in (favs + others):
            name  = s.get("name", "?")
            fav   = "* " if s.get("favorite") else ""
            genre = s.get("genre", "")
            label = f"{fav}{name}  [{genre}]" if genre else f"{fav}{name}"
            active = (
                S.get("radio_type") == "WEB" and
                S.get("radio_station", "") == name
            )
            _wid = f"web_{name.lower().replace(' ', '_')[:20]}"
            _meta_web = {
                "url": s.get("url", ""),
                "genre": genre,
                "name": name,
                "favorite": s.get("favorite", False)
            }

            nodes.append(MenuNode(
                id=_wid, label=label, type="station",
                source="webradio", playable=True, active=active,
                meta=_meta_web,
                children=[_fav_node(_wid, name, "webradio", _meta_web, s.get("favorite", False))]
            ))
        return nodes

    # ── 1. Favoriten (quellenübergreifend) ─────────────────────────────────
    fav_nodes = []
    if _fav_mod:
        for _fav in _fav_mod.get_all():
            _src  = _fav.get("source", "")
            _id   = _fav.get("id", "")
            _name = _fav.get("name", _id)
            _meta = _fav.get("meta", {})
            if _src in ("fm", "dab", "webradio"):
                fav_nodes.append(MenuNode(
                    id="favx_" + _id, label="* " + _name, type="station",
                    source=_src, meta=_meta
                ))
            elif _src == "spotify":
                fav_nodes.append(MenuNode(
                    id="favx_" + _id, label="* " + _name + "  (Spotify)",
                    type="action", action="play_spotify", meta=_meta
                ))
            elif _src == "scanner":
                _band = _meta.get("band", "pmr446")
                fav_nodes.append(MenuNode(
                    id="favx_" + _id, label="* " + _name,
                    type="action", action="scan_up:" + _band, meta=_meta
                ))

    favoriten = MenuNode(id="favoriten", label="Favoriten", type="folder", children=(
        [
            _back("favoriten"),
            MenuNode(id="fav_add_current", label="Aktuellen Sender merken",
                     type="action", action="favorites_add_current"),
        ]
        + (fav_nodes or [MenuNode(id="fav_empty", label="Noch keine Favoriten", type="info")])
    ))

    # ── 2. Quellen ──────────────────────────────────────────────────────────
    fm_sender = _folder("fm_stations", "Sender", _station_nodes_fm(store.fm) or [
        MenuNode(id="fm_empty", label="Kein Sender — Suchlauf starten", type="info")
    ])
    fm_node = _folder("fm", "FM Radio", [
        fm_sender,
        MenuNode(id="fm_scan",   label="Suchlauf starten",  type="action", action="fm_scan"),
        MenuNode(id="fm_next",   label="Naechster Sender",  type="action", action="fm_next"),
        MenuNode(id="fm_prev",   label="Vorheriger Sender", type="action", action="fm_prev"),
        MenuNode(id="fm_manual", label="Frequenz manuell",  type="action", action="fm_manual"),
    ])

    dab_sender = _folder("dab_stations", "Sender", _station_nodes_dab(store.dab) or [
        MenuNode(id="dab_empty", label="Kein Sender — Suchlauf starten", type="info")
    ])
    dab_node = _folder("dab", "DAB+", [
        dab_sender,
        MenuNode(id="dab_scan",  label="Suchlauf starten",  type="action", action="dab_scan"),
        MenuNode(id="dab_next",  label="Naechster Sender",  type="action", action="dab_next"),
        MenuNode(id="dab_prev",  label="Vorheriger Sender", type="action", action="dab_prev"),
    ])

    web_sender = _folder("web_stations", "Sender", _station_nodes_web(store.web) or [
        MenuNode(id="web_empty", label="Keine Stationen", type="info")
    ])
    webradio_node = _folder("webradio", "Webradio", [
        web_sender,
        MenuNode(id="web_reload", label="Sender neu laden", type="action",
                 action="reload_stations:webradio"),
    ])

    def _scanner_band(band_id, label):
        scanner_key = f"scanner_{band_id}"
        current_info = S.get(scanner_key, "")
        active = bool(
            S.get("radio_type") == "SCANNER" and
            band_id.upper() in S.get("radio_station", "").upper()
        )
        if not current_info and BANDS.get(band_id, {}).get("band"):
            _b = BANDS[band_id]["band"]
            current_info = f"{_b.get('start', _b.get('min', 0)):.3f} MHz"
        info_label = f"> {current_info}" if (active and current_info) else (current_info or "kein Kanal aktiv")
        return _folder(band_id, label, [
            MenuNode(id=f"{band_id}_info", label=info_label, type="info"),
            MenuNode(id=f"{band_id}_up",   label="Kanal +",      type="action", action=f"scan_up:{band_id}"),
            MenuNode(id=f"{band_id}_down", label="Kanal -",      type="action", action=f"scan_down:{band_id}"),
            MenuNode(id=f"{band_id}_next", label="Scan weiter",  type="action", action=f"scan_next:{band_id}"),
            MenuNode(id=f"{band_id}_prev", label="Scan zurueck", type="action", action=f"scan_prev:{band_id}"),
        ], active=active)

    scanner_node = _folder("scanner", "Scanner", [
        _scanner_band("pmr446",  "PMR446"),
        _scanner_band("freenet", "Freenet"),
        _scanner_band("lpd433",  "LPD433"),
        _scanner_band("cb",      "CB-Funk (DE/EU)"),
        _scanner_band("vhf",     "VHF"),
        _scanner_band("uhf",     "UHF"),
    ])

    spotify_node = _folder("spotify", "Spotify", [
        MenuNode(id="spot_toggle", label="Spotify An/Aus", type="toggle",
                 action="spotify_toggle", active=S.get("spotify", False)),
        MenuNode(id="spot_status",
                 label=("Status: aktiv" if S.get("spotify") else "Status: inaktiv"),
                 type="info"),
    ])

    # Bibliothek: music_dir aus settings.json + Unterordner + USB (nur Abspielen)
    _music_dir = settings.get("music_dir") or settings.get("music_path") or "/home/pidrive/Musik"
    _lib_name = os.path.basename(_music_dir.rstrip("/")) or "Musik"
    _lib_children = [
        MenuNode(id="lib_play",    label=f"Alle: {_lib_name}",
                 type="action", action=f"local_play:{_music_dir}"),
        MenuNode(id="lib_shuffle", label="Alle zufaellig",
                 type="action", action=f"local_play:{_music_dir}|shuffle"),
    ]
    try:
        from modules.music_library import list_subfolders_for_menu as _lsfm
        for _sf in _lsfm(settings):
            _sid = "lib_" + _sf["name"].replace(" ", "_")[:20]
            _lib_children.append(MenuNode(
                id=_sid, label=f"Ordner: {_sf['name']} ({_sf['files']})",
                type="action", action=f"local_play:{_sf['path']}",
            ))
    except Exception:
        pass
    _lib_children.append(MenuNode(id="lib_stop", label="Stop", type="action", action="library_stop"))
    try:
        from modules.usb_music import find_usb_sticks as _fus
        for _ui, _usb in enumerate(_fus()):
            _uid   = f"usb_{_ui}"
            _ulbl  = f"USB: {_usb['name']}  ({_usb['files']} Dateien)"
            _upath = _usb["path"]
            _lib_children.append(_folder(_uid, _ulbl, [
                MenuNode(id=f"{_uid}_play",    label="Abspielen",
                         type="action", action=f"local_play:{_upath}"),
                MenuNode(id=f"{_uid}_shuffle", label="Zufaellig",
                         type="action", action=f"local_play:{_upath}|shuffle"),
            ]))
    except Exception:
        pass
    lib_node = _folder("library", "Bibliothek", _lib_children)

    quellen = _folder("sources", "Quellen", [
        fm_node,
        dab_node,
        webradio_node,
        spotify_node,
        scanner_node,
        lib_node,
    ])

    # ── 3. Audio (Ausgang + Lautstärke) ────────────────────────────────────
    _out = settings.get("audio_output", "auto")
    audio_node = _folder("audio_out", "Audio", [
        MenuNode(id="ao_status", label=f"Ausgang: {_out}", type="info"),
        MenuNode(id="ao_auto",   label="Auto",          type="action", action="audio_all"),
        MenuNode(id="ao_bt",     label="Bluetooth",     type="action", action="audio_bt"),
        MenuNode(id="ao_klinke", label="Klinke (AUX)",  type="action", action="audio_klinke"),
        MenuNode(id="ao_hdmi",   label="HDMI",          type="action", action="audio_hdmi"),
        MenuNode(id="ao_volup",  label="Lauter",        type="action", action="vol_up"),
        MenuNode(id="ao_voldown",label="Leiser",        type="action", action="vol_down"),
    ])

    # ── 4. Verbindungen (BT + WiFi) ─────────────────────────────────────────
    _bt_on     = bool(S.get("bt", False))
    _bt_dev    = S.get("bt_device", "") or "-"
    _bt_last   = settings.get("bt_last_name", "") or "-"
    _bt_status = S.get("bt_status", "getrennt")

    if _bt_status == "verbunden":
        _bt_state_label = "Bluetooth: verbunden"
    elif _bt_status == "verbindet":
        _bt_state_label = "Bluetooth: verbindet..."
    elif _bt_status == "aus":
        _bt_state_label = "Bluetooth: aus"
    else:
        _bt_state_label = "Bluetooth: getrennt"

    bt_devs_ext = []
    try:
        if os.path.exists("/tmp/pidrive_bt_devices.json"):
            with open("/tmp/pidrive_bt_devices.json", encoding="utf-8") as _f:
                _btd = json.load(_f)
            for _d in _btd.get("devices", []):
                _m = _d.get("mac", "")
                _n = _d.get("name", _m)
                _prefix = ""
                if _d.get("connected"):
                    _prefix = "> "
                elif _d.get("known") or _d.get("paired"):
                    _prefix = "* "
                bt_devs_ext.append(_folder("btd_" + _m.replace(":", ""), _prefix + _n, [
                    MenuNode(id="btconn_" + _m.replace(":", ""), label="Verbinden",
                             type="action", action="bt_connect:" + _m),
                    MenuNode(id="btforget_" + _m.replace(":", ""), label="Vergessen",
                             type="action", action="bt_forget:" + _m),
                ]))
    except Exception:
        pass

    bt_geraete = MenuNode(
        id="bt_geraete", label="Geraete", type="folder",
        children=[_back("bt_geraete")] + (bt_devs_ext or [
            MenuNode(id="bt_hint", label="Zuerst scannen", type="info")])
    )

    wifi_nets = []
    try:
        if os.path.exists("/tmp/pidrive_wifi_nets.json"):
            with open("/tmp/pidrive_wifi_nets.json", encoding="utf-8") as _f2:
                _wfd = json.load(_f2)
            for _n in _wfd.get("networks", []):
                _s = _n.get("ssid", "")
                if _s:
                    wifi_nets.append(MenuNode(
                        id="wfn_" + _s.replace(" ", "_")[:16],
                        label=_s, type="action",
                        action="wifi_connect:" + _s, meta={"ssid": _s}
                    ))
    except Exception:
        pass
    wifi_netze = _folder("wifi_netze", "Netzwerke", wifi_nets or [
        MenuNode(id="wifi_hint", label="Zuerst scannen", type="info")])

    # BT-Aktionen zustandsabhängig — Trennen/Ausschalten mit Rückfrage,
    # weil danach keine iDrive-Steuerung mehr möglich ist.
    bt_actions = [
        MenuNode(id="bt_scan", label="Geraete scannen", type="action", action="bt_scan"),
        bt_geraete,
        MenuNode(id="bt_reconn", label="Letztes Geraet verbinden", type="action",
                 action="bt_reconnect_last"),
    ]
    if _bt_on:
        bt_actions.append(_confirm("bt_disc", "Bluetooth trennen",
                                   "Ja, trennen", "bt_disconnect"))
        bt_actions.append(_confirm("bt_off", "Bluetooth ausschalten",
                                   "Ja, ausschalten", "bt_off"))
    else:
        bt_actions.append(MenuNode(id="bt_on", label="Bluetooth einschalten",
                                   type="action", action="bt_on"))
    bt_actions += [
        MenuNode(id="bt_state",  label=_bt_state_label, type="info"),
        MenuNode(id="bt_status", label="Geraet: " + _bt_dev[:24], type="info"),
        MenuNode(id="bt_last",   label="Letztes: " + _bt_last[:24], type="info"),
    ]

    verbindungen = _folder("connections", "Verbindungen", bt_actions + [
        MenuNode(id="wifi_toggle", label="WiFi An/Aus", type="toggle",
                 action="wifi_toggle", active=S.get("wifi", False)),
        MenuNode(id="wifi_scan",   label="Netzwerke scannen", type="action", action="wifi_scan"),
        wifi_netze,
        MenuNode(id="wifi_status", label="SSID: " + (S.get("wifi_ssid", "") or "-"), type="info"),
    ])

    # ── 5. System (folgenreiche Aktionen mit Rückfrage) ─────────────────────
    system = _folder("system", "System", [
        MenuNode(id="sys_ip",      label="IP: " + _local_ip(), type="info"),
        MenuNode(id="sys_info",    label="System-Info", type="action", action="sys_info"),
        MenuNode(id="sys_version", label="Version",     type="action", action="sys_version"),
        _confirm("sys_reboot", "Neustart",    "Ja, neu starten", "reboot"),
        _confirm("sys_off",    "Ausschalten", "Ja, ausschalten", "shutdown"),
        _confirm("sys_update", "Update",      "Ja, Update",      "update"),
    ])

    # ── Wurzel ──────────────────────────────────────────────────────────────
    root = MenuNode(id="root", label="PiDrive", type="folder", children=[
        favoriten,
        quellen,
        MenuNode(id="stop_all", label="Stop", type="action", action="radio_stop"),
        audio_node,
        verbindungen,
        system,
    ])
    return root

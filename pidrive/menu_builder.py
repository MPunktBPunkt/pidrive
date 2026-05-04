#!/usr/bin/env python3
"""menu_builder.py — build_tree()  v0.10.23
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

from menu_state import MenuNode, MenuState
from station_store import StationStore

# ── Menübaum aufbauen ─────────────────────────────────────────────────────────

def build_tree(store: StationStore, S: dict, settings: dict) -> MenuNode:
    """Vollständigen Menübaum aus StationStore aufbauen."""

    def _fav_node(node_id, name, source, meta, is_fav):
        import json as _jj
        _lbl = ("☆ Aus Favoriten entfernen" if is_fav
                else "★ Zu Favoriten hinzufuegen")
        _meta_str = _jj.dumps(meta, ensure_ascii=False)
        _action = f"fav_toggle:{source}:{node_id}:{name}:{_meta_str}"
        return MenuNode(
            id="fav_" + node_id, label=_lbl, type="action",
            action=_action
        )

    def _station_nodes_fm(stations):
        favs    = [s for s in stations if s.get("favorite")]
        others  = [s for s in stations if not s.get("favorite")]
        ordered = favs + others
        nodes   = []

        for s in ordered:
            freq  = s.get("freq_mhz") or s.get("freq", "")
            name  = s.get("name", str(freq))
            fav   = "★ " if s.get("favorite") else ""
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
        """
        DAB Sender nach Kanal gruppiert (v0.9.15).
        Favoriten oben als eigene Gruppe, dann Unterordner pro Kanal.
        Ohne Gruppierung wäre die Liste mit vielen Sendern unübersichtlich.
        """
        def _make_node(s):
            name   = s.get("name", s.get("service_name", "?"))
            fav    = "★ " if s.get("favorite") else ""
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

        favs = [s for s in stations if s.get("favorite")]
        nodes = []

        # Favoriten als eigene Gruppe ganz oben
        if favs:
            nodes.append(MenuNode(
                id="dab_favs", label=f"★ Favoriten ({len(favs)})", type="folder",
                children=[_make_node(s) for s in favs]
            ))

        # Alle Sender nach Kanal gruppieren
        channels_seen = []
        by_channel = {}
        for s in stations:
            ch  = str(s.get("channel", "") or "").strip().upper() or "?"
            ens = s.get("ensemble", "")
            if ch not in by_channel:
                by_channel[ch] = {"ens": ens, "stations": []}
                channels_seen.append(ch)
            by_channel[ch]["stations"].append(s)

        for ch in channels_seen:
            group     = by_channel[ch]
            ens_label = group["ens"] or ch
            ch_nodes  = [_make_node(s) for s in group["stations"]]
            folder_label = f"{ch}  {ens_label}" if ens_label != ch else ch
            nodes.append(MenuNode(
                id=f"dab_ch_{ch.lower()}", label=folder_label, type="folder",
                children=ch_nodes
            ))

        return nodes

    def _station_nodes_web(stations):
        favs   = [s for s in stations if s.get("favorite")]
        others = [s for s in stations if not s.get("favorite")]
        nodes  = []

        for s in (favs + others):
            name  = s.get("name", "?")
            fav   = "★ " if s.get("favorite") else ""
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

    # ── Jetzt läuft ───────────────────────────────────────────────────────
    now_playing = MenuNode(id="now_playing", label="Jetzt laeuft", type="folder", children=[
        MenuNode(id="np_source",   label="Quelle",        type="info"),
        MenuNode(id="np_title",    label="Titel/Sender",  type="info"),
        MenuNode(id="spotify_tog", label="Spotify",       type="toggle",
                 action="spotify_toggle", active=S.get("spotify", False)),
        MenuNode(id="audio_out",   label="Audioausgang",  type="action", action="audio_select"),
        MenuNode(id="vol_up",      label="Lauter",        type="action", action="vol_up"),
        MenuNode(id="vol_down",    label="Leiser",        type="action", action="vol_down"),
    ])

    # ── Quellen → FM ──────────────────────────────────────────────────────
    fm_sender = MenuNode(id="fm_stations", label="Sender", type="folder",
                         children=_station_nodes_fm(store.fm) or [
                             MenuNode(id="fm_empty", label="Kein Sender — Suchlauf starten", type="info")
                         ])
    fm_node = MenuNode(id="fm", label="FM Radio", type="folder", children=[
        MenuNode(id="fm_now",    label="Jetzt laeuft",      type="info"),
        fm_sender,
        MenuNode(id="fm_scan",   label="Suchlauf starten",  type="action", action="fm_scan"),
        MenuNode(id="fm_next",   label="Naechster Sender",  type="action", action="fm_next"),
        MenuNode(id="fm_prev",   label="Vorheriger Sender", type="action", action="fm_prev"),
        MenuNode(id="fm_manual", label="Frequenz manuell",  type="action", action="fm_manual"),
    ])

    # ── Quellen → DAB+ ────────────────────────────────────────────────────
    dab_sender = MenuNode(id="dab_stations", label="Sender", type="folder",
                          children=_station_nodes_dab(store.dab) or [
                              MenuNode(id="dab_empty", label="Kein Sender — Suchlauf starten", type="info")
                          ])
    dab_node = MenuNode(id="dab", label="DAB+", type="folder", children=[
        MenuNode(id="dab_now",   label="Jetzt laeuft",      type="info"),
        dab_sender,
        MenuNode(id="dab_scan",  label="Suchlauf starten",  type="action", action="dab_scan"),
        MenuNode(id="dab_next",  label="Naechster Sender",  type="action", action="dab_next"),
        MenuNode(id="dab_prev",  label="Vorheriger Sender", type="action", action="dab_prev"),
    ])

    # ── Quellen → Webradio ────────────────────────────────────────────────
    web_sender = MenuNode(id="web_stations", label="Sender", type="folder",
                          children=_station_nodes_web(store.web) or [
                              MenuNode(id="web_empty", label="Keine Stationen", type="info")
                          ])
    webradio_node = MenuNode(id="webradio", label="Webradio", type="folder", children=[
        MenuNode(id="web_now",    label="Jetzt laeuft",      type="info"),
        web_sender,
        MenuNode(id="web_reload", label="Sender neu laden",  type="action", action="reload_stations:webradio"),
    ])

    # ── Quellen → Scanner ─────────────────────────────────────────────────
    def _scanner_band(band_id, label):
        scanner_key = f"scanner_{band_id}"
        current_info = S.get(scanner_key, "")
        active = bool(
            S.get("radio_type") == "SCANNER" and
            band_id.upper() in S.get("radio_station", "").upper()
        )
        # v0.9.24: VHF/UHF — Startfrequenz zeigen wenn noch kein Schritt
        if not current_info and BANDS.get(band_id, {}).get("band"):
            _b = BANDS[band_id]["band"]
            current_info = f"{_b.get('start', _b.get('min', 0)):.3f} MHz"
        info_label = f"▶ {current_info}" if (active and current_info) else (current_info or "– kein Kanal aktiv –")
        return MenuNode(id=band_id, label=label, type="folder", active=active, children=[
            MenuNode(id=f"{band_id}_info", label=info_label, type="info"),
            MenuNode(id=f"{band_id}_up",   label="Kanal +",       type="action", action=f"scan_up:{band_id}"),
            MenuNode(id=f"{band_id}_down", label="Kanal -",       type="action", action=f"scan_down:{band_id}"),
            MenuNode(id=f"{band_id}_next", label="Scan weiter",   type="action", action=f"scan_next:{band_id}"),
            MenuNode(id=f"{band_id}_prev", label="Scan zurueck",  type="action", action=f"scan_prev:{band_id}"),
        ])

    scanner_node = MenuNode(id="scanner", label="Scanner", type="folder", children=[
        _scanner_band("pmr446",  "PMR446"),
        _scanner_band("freenet", "Freenet"),
        _scanner_band("lpd433",  "LPD433"),
        _scanner_band("cb",      "CB-Funk (DE/EU)"),
        _scanner_band("vhf",     "VHF"),
        _scanner_band("uhf",     "UHF"),
    ])

    # ── Quellen → Bibliothek & Spotify ────────────────────────────────────
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

    quellen = MenuNode(id="sources", label="Quellen", type="folder", children=[
        spotify_node,
        lib_node,
        webradio_node,
        dab_node,
        fm_node,
        scanner_node,
    ])

    # ── Favoriten ──────────────────────────────────────────────────────────
    fav_nodes = []
    if _fav_mod:
        for _fav in _fav_mod.get_all():
            _src  = _fav.get("source", "")
            _id   = _fav.get("id", "")
            _name = _fav.get("name", _id)
            _meta = _fav.get("meta", {})
            _lbl  = "★ " + _name
            if _src in ("fm", "dab", "webradio"):
                fav_nodes.append(MenuNode(
                    id="fav_" + _id, label=_lbl, type="station",
                    source=_src, meta=_meta
                ))
            elif _src == "scanner":
                _band = _meta.get("band", "pmr446")
                fav_nodes.append(MenuNode(
                    id="fav_" + _id, label=_lbl, type="action",
                    action="scan_up:" + _band, meta=_meta
                ))

    favoriten = MenuNode(
        id="favoriten", label="Favoriten", type="folder",
        children=fav_nodes or [MenuNode(id="fav_empty", label="Noch keine Favoriten", type="info")]
    )

    # ── Verbindungen ───────────────────────────────────────────────────────
    _bt_on     = bool(S.get("bt", False))
    _bt_dev    = S.get("bt_device", "") or "–"
    _bt_last   = settings.get("bt_last_name", "") or "–"
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
                    _prefix = "▶ "
                elif _d.get("known") or _d.get("paired"):
                    _prefix = "★ "
                bt_devs_ext.append(MenuNode(
                    id="btd_" + _m.replace(":", ""),
                    label=_prefix + _n,
                    type="folder",
                    meta={"mac": _m, "name": _n},
                    children=[
                        # v0.9.29: Verbinden = connect_device() erkennt selbst ob pair nötig
                        MenuNode(id="btconn_" + _m.replace(":", ""), label="Verbinden",
                                 type="action", action="bt_connect:" + _m),
                        MenuNode(id="btforget_" + _m.replace(":", ""), label="Vergessen",
                                 type="action", action="bt_forget:" + _m),
                    ]
                ))
    except Exception:
        pass

    bt_geraete = MenuNode(
        id="bt_geraete", label="Geraete", type="folder",
        children=bt_devs_ext or [MenuNode(id="bt_hint", label="Zuerst scannen", type="info")]
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
                        label=_s,
                        type="action",
                        action="wifi_connect:" + _s,
                        meta={"ssid": _s}
                    ))
    except Exception:
        pass

    wifi_netze = MenuNode(
        id="wifi_netze", label="Netzwerke", type="folder",
        children=wifi_nets or [MenuNode(id="wifi_hint", label="Zuerst scannen", type="info")]
    )

    verbindungen = MenuNode(id="connections", label="Verbindungen", type="folder", children=[
        MenuNode(id="bt_toggle",   label="Bluetooth An/Aus", type="toggle",
                 action="bt_toggle", active=_bt_on),
        MenuNode(id="bt_scan",     label="Geraete scannen",  type="action", action="bt_scan"),
        bt_geraete,
        MenuNode(id="bt_reconn",   label="Letztes Geraet verbinden", type="action", action="bt_reconnect_last"),
        MenuNode(id="bt_disc",     label="Bluetooth trennen", type="action", action="bt_disconnect"),
        MenuNode(id="bt_state",    label=_bt_state_label, type="info"),
        MenuNode(id="bt_status",   label="Geraet: " + _bt_dev[:24], type="info"),
        MenuNode(id="bt_last",     label="Letztes: " + _bt_last[:24], type="info"),
        MenuNode(id="wifi_toggle", label="WiFi An/Aus", type="toggle",
                 action="wifi_toggle", active=S.get("wifi", False)),
        MenuNode(id="wifi_scan",   label="Netzwerke scannen", type="action", action="wifi_scan"),
        wifi_netze,
        MenuNode(id="wifi_status", label="SSID: " + (S.get("wifi_ssid", "") or "–"), type="info"),
    ])

    # ── System ─────────────────────────────────────────────────────────────
    system = MenuNode(id="system", label="System", type="folder", children=[
        MenuNode(id="sys_ip",      label="IP Adresse",  type="info"),
        MenuNode(id="sys_info",    label="System-Info", type="action", action="sys_info"),
        MenuNode(id="sys_version", label="Version",     type="action", action="sys_version"),
        MenuNode(id="sys_reboot",  label="Neustart",    type="action", action="reboot"),
        MenuNode(id="sys_off",     label="Ausschalten", type="action", action="shutdown"),
        MenuNode(id="sys_update",  label="Update",      type="action", action="update"),
    ])

    root = MenuNode(id="root", label="PiDrive", type="folder", children=[
        now_playing,
        favoriten,
        quellen,
        verbindungen,
        system,
    ])
    return root

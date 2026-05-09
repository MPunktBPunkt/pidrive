# PiDrive — Architektur & Verzeichnisstruktur

## Übersicht

PiDrive ist ein modulares Car-Infotainment-System auf Raspberry Pi 3B für BMW iDrive (NBT EVO).

```
PiDrive
├── Menülogik / Triggerverarbeitung      trigger_dispatcher, td_*.py
├── Fachmodule (DAB, FM, BT, Audio…)    modules/
├── WebUI (Flask API + Frontend)         webui.py, web/
├── IPC / Status / Einstellungen         ipc.py, status.py, settings.py
├── AVRCP / MPRIS2 (BMW-Integration)    avrcp_trigger.py, mpris2.py
└── Konfiguration                        config/
```

---

## Verzeichnisstruktur

```
pidrive/
│
├── main_core.py            ← Prozess-Einstieg (Core)
├── main_display.py         ← Prozess-Einstieg (Display/TFT)
│
├── ipc.py                  ← Interprozesskommunikation (status.json, cmd-Datei)
├── status.py               ← Status-Felder initialisieren
├── settings.py             ← settings.json lesen/schreiben
├── log.py                  ← Logging-Konfiguration
├── diagnose.py             ← Diagnose-Skript
│
├── menu_model.py           ← Menübaumstruktur (Knoten, Typen)
├── menu_state.py           ← Menüzustand (Cursor, Pfad, History)
├── menu_builder.py         ← Menübaum aufbauen (aus Stationsdaten, Favoriten)
├── station_store.py        ← Senderdaten-Store (FM/DAB/Webradio)
│
├── trigger_dispatcher.py   ← Hauptdispatcher (liest /tmp/pidrive_cmd)
├── td_nav.py               ← Trigger: Navigation + Quellwechsel
├── td_hardware.py          ← Trigger: Hardware-Buttons
├── td_radio.py             ← Trigger: Radio (DAB/FM/Webradio/Favoriten)
│   ├── play_dab:<name>     (CLI/API High-Level-Trigger)
│   ├── play_fm:<name>
│   ├── play_web:<name>
│   └── favorites_play:<nr>
├── td_scanner.py           ← Trigger: Scanner/Spektrum
├── td_system.py            ← Trigger: System (Reboot, Shutdown, Updates)
│
├── webui.py                ← Flask-App (REST-API + HTML-Seiten)
├── webui_shared.py         ← Gemeinsame Konstanten (ALLOWED_COMMANDS, PA_ENV)
│
├── avrcp_trigger.py        ← BMW iDrive AVRCP → File-Trigger
├── mpris2.py               ← D-Bus MPRIS2-Adapter
├── mpv_meta.py             ← mpv Socket-Metadaten-Listener
│
├── cli.py                  ← pidrivectl CLI Entry Point
├── cli_service.py          ← CLI Service-Layer
├── cli_adapters.py         ← CLI IPC/HTTP-Adapter
├── cli_format.py           ← CLI Ausgabe-Formatierung
│
├── modules/                ← Fachmodule
│   ├── audio.py            ← PulseAudio / Volume / Routing
│   ├── wifi.py             ← WiFi-Management
│   ├── favorites.py        ← Favoriten-Persistenz
│   ├── library.py          ← Musikbibliothek
│   ├── source_state.py     ← Source-State-Machine
│   ├── system.py           ← System-Infos (RAM, Temp, etc.)
│   ├── update.py           ← OTA-Update-Mechanismus
│   ├── webradio.py         ← mpv-basiertes Webradio
│   │
│   ├── bluetooth/          ← Bluetooth-Subsystem (Namespace)
│   │   └── __init__.py     ← re-exportiert bt_* Module
│   ├── bluetooth.py        ← BT-Facade (A2DP, Pairing, Status)
│   ├── bt_helpers.py       ← Hilfsfunktionen (MAC, bluetoothctl-Wrapper)
│   ├── bt_agent.py         ← BT-Agent (Pairing-Automatik)
│   ├── bt_devices.py       ← Gerätescan + Discovery
│   ├── bt_connect.py       ← Verbindungslogik (connect/disconnect)
│   ├── bt_audio.py         ← A2DP-Audio-Routing
│   ├── bt_backup.py        ← Known-Devices-Backup/Restore
│   ├── bt_watcher.py       ← BT-State-Watcher (Hintergrundprozess)
│   │
│   ├── radio/              ← Radio/RF-Subsystem (Namespace)
│   │   └── __init__.py     ← re-exportiert dab_*/fm/scanner/rtlsdr Module
│   ├── dab.py              ← DAB-Facade (play_by_name, play_station)
│   ├── dab_play.py         ← welle-cli-Integration (Lock-Wait, PCM, DLS)
│   ├── dab_dls.py          ← DLS-Poller (Textzeilen aus welle-cli stderr)
│   ├── dab_scan.py         ← DAB-Kanalsuche
│   ├── dab_helpers.py      ← DAB-Hilfsfunktionen (Parsing, JSON-Write)
│   ├── fm.py               ← FM-Wiedergabe (rtl_fm)
│   ├── scanner.py          ← RTL-SDR Scanner (PMR446, Freenet, VHF)
│   ├── spectrum.py         ← FFT-Spektrum-Analyzer
│   └── rtlsdr.py           ← RTL-SDR Prozess-Manager (Lock, Ownership)
│
├── web/                    ← Web-Frontend
│   ├── app.py              ← Alias für webui.py (für neue Importe)
│   ├── shared.py           ← Alias für webui_shared.py
│   ├── api/
│   │   ├── routes_audio.py   ← /api/audio, /api/volume
│   │   ├── routes_bt.py      ← /api/bt/*
│   │   ├── routes_dab.py     ← /api/dab/*
│   │   └── routes_webradio.py← /api/webradio/*
│   ├── templates/
│   │   ├── base.html         ← Layout-Template
│   │   ├── index.html        ← Alltag (Favoriten, Medien, BT, Vol, System)
│   │   ├── bluetooth.html    ← BT-Verwaltung
│   │   ├── audio.html        ← Audio Debug Cockpit
│   │   ├── diagnostics.html  ← Logs, Diagnose, System
│   │   ├── rf-tools.html     ← DAB/RTL-SDR/Spektrum-Tools
│   │   ├── avrcp.html        ← AVRCP/BMW Debug
│   │   └── webradio-admin.html← Webradio-Senderverwaltung
│   └── static/
│       ├── style.css
│       └── js/               ← (Phase 3: separate JS-Module)
│
└── config/
    ├── settings.json
    ├── stations.json         ← Webradio-Sender
    ├── dab_stations.json     ← DAB-Sender
    ├── fm_stations.json      ← FM-Sender
    └── favorites.json        ← Favoriten
```

---

## Datenfluss: Trigger-System

```
BMW iDrive (AVRCP)          Shell/WebUI/CLI
       ↓                           ↓
  avrcp_trigger.py           /api/cmd  bzw.
       ↓                    /tmp/pidrive_cmd
       └──────────────→ trigger_dispatcher.py
                                   ↓
                    td_nav / td_radio / td_scanner / …
                                   ↓
                         modules/ (Fachmodule)
                                   ↓
                     /tmp/pidrive_status.json
                     /tmp/pidrive_source_state.json
                                   ↓
                          webui.py (Flask API)
                                   ↓
                        Browser / pidrivectl CLI
```

---

## IPC-Dateien (`/tmp/pidrive_*.json`)

| Datei | Inhalt | Schreiber |
|---|---|---|
| `pidrive_status.json` | Wiedergabe-/BT-/WiFi-Status | `ipc.write_status()` |
| `pidrive_source_state.json` | Aktive Quelle, Transition | `source_state.py` |
| `pidrive_menu.json` | Menüzustand (Cursor, Pfad) | `ipc.write_menu()` |
| `pidrive_cmd` | Trigger-Datei (write → Core verarbeitet) | WebUI, CLI, AVRCP |
| `pidrive_bt_devices.json` | Entdeckte BT-Geräte | `bt_devices.py` |
| `pidrive_bt_known_devices.json` | Bekannte BT-Geräte | `bt_devices.py` |
| `pidrive_dab_play_debug.json` | DAB Lock/DLS Debug | `dab_helpers.py` |

---

## API-Endpunkte (Auswahl)

| Endpunkt | Seite | Beschreibung |
|---|---|---|
| `GET /api/core` | index.html | Schnell-Poll: Status + Menü + Progress |
| `POST /api/cmd` | alle | Trigger senden |
| `GET /api/state` | index.html | Status-JSON |
| `GET /api/dab/status` | rf-tools.html | DAB Lock/PCM/DLS Debug |
| `GET /api/audio` | audio.html | Audio-Routing-Details |
| `GET /api/bt/known` | bluetooth.html | Bekannte BT-Geräte |
| `GET /api/spectrum/last` | rf-tools.html | FFT-Spektrum-Snapshot |
| `GET /api/logs?target=core` | diagnostics.html | Core-Log |
| `GET /api/avrcp` | avrcp.html | AVRCP-Debug-Status |

---

## pidrivectl CLI

```bash
pidrivectl status              # Systemstatus
pidrivectl now                 # Aktuelle Wiedergabe
pidrivectl quick               # Schnellübersicht
pidrivectl play dab "ROCK FM"  # DAB-Sender starten
pidrivectl play web "Bayern 1" # Webradio starten
pidrivectl play fm "Bayern 3"  # FM starten
pidrivectl stop                # Stoppen
pidrivectl favorites list      # Favoriten
pidrivectl bt scan             # BT scannen
pidrivectl volume up           # Lauter
pidrivectl debug state         # Status-JSONs anzeigen
```

---

## Bekannte Erwartbare Warnungen

| Meldung | Ursache | Bedeutung |
|---|---|---|
| `fbcon not available` | TFT nicht angesteckt | pidrive_display optional |
| `DAB: no_lock` | Schlechter DAB-Empfang (Innenraum) | Im Auto mit Antenne OK |
| `bt_state=failed` | Kein BT-Gerät in Reichweite | Automatisch nach Pairing |
| `Socket nicht gefunden: /tmp/pidrive_mpv.sock` | mpv noch nicht bereit | Metadaten folgen |

---

*Zuletzt aktualisiert: v0.10.54+*

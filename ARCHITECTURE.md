# PiDrive — Architektur & Verzeichnisstruktur

**Stand v0.11.122**

## Übersicht

PiDrive ist ein modulares, GUI-loses Car-Infotainment-System für BMW iDrive (NBT EVO).
Zielplattform ist der Raspberry Pi 4; entwickelt und getestet wird zusätzlich auf
x86/Debian. Es gibt kein TFT-Display mehr (dauerhaft entfernt in v0.10.83) — die
Bedienung erfolgt über BMW iDrive (AVRCP), die WebUI (Port 8080) und die CLI
(`pidrivectl`).

```
PiDrive
├── Core-Loop / Triggerverarbeitung      main_core.py, trigger/
├── Fachmodule (DAB, FM, BT, Audio…)     modules/
├── WebUI (Flask API + Frontend)         web/ (Entry-Shim: webui.py)
├── CLI (pidrivectl)                      cli/
├── IPC / Status / Einstellungen          ipc.py, status.py, settings.py
├── AVRCP / MPRIS2 (BMW-Integration)      integration/avrcp_trigger.py, mpris2.py
├── Menü-Modell                           menu/
└── Konfiguration                         config/
```

> **Modulpfade & Kompatibilitäts-Shims:** Die früher flache Struktur (z. B. `td_*.py`,
> `cli_*.py`, `webui.py`, `modules/bluetooth.py` direkt im Wurzelverzeichnis) wurde in
> Pakete umgebaut (`trigger/`, `cli/`, `web/`, `modules/bluetooth/`, `modules/radio/`,
> `integration/`). Für Rückwärtskompatibilität existieren dünne **Shims** an den alten
> Pfaden, die auf die neue Implementierung weiterleiten:
>
> | Shim (alt) | Echte Implementierung |
> |---|---|
> | `webui.py` | `web/app.py` |
> | `web/shared.py` | `web/shared/*` (Re-Export-Layer) |
> | `avrcp_trigger.py` | `integration/avrcp_trigger.py` |
> | `modules/dab.py` | `modules/radio/dab.py` |
> | `modules/fm.py` | `modules/radio/fm.py` |
> | `modules/scanner.py` | `modules/radio/scanner.py` |
>
> Die systemd-Dienste `pidrive_web.service` und `pidrive_avrcp.service` starten teils
> noch die Shim-Pfade (`webui.py` bzw. direkt `integration/avrcp_trigger.py`).

---

## Verzeichnisstruktur

```
pidrive/
│
├── main_core.py            ← Prozess-Einstieg (Core, systemd-Entry)
│
├── ipc.py                  ← Interprozesskommunikation (status.json, cmd-Queue)
├── status.py               ← Status-Felder initialisieren
├── settings.py             ← settings.json lesen/schreiben
├── log.py                  ← Logging-Konfiguration
├── diagnose.py             ← Diagnose-Skript (Core, Audio, BT, RTL-SDR)
├── test_suite.py           ← Systemtest (pidrivectl test all)
│
├── mpris2.py               ← D-Bus MPRIS2-Adapter (BMW-Display-Metadaten)
├── mpv_meta.py             ← mpv-Socket-Metadaten-Listener (ICY/Now-Playing)
│
├── webui.py                ← Entry-Shim → web/app.py
├── avrcp_trigger.py        ← Entry-Shim → integration/avrcp_trigger.py
│
├── menu/                   ← Menü-Modell
│   ├── menu_model.py       ← Menübaumstruktur (Knoten, Typen)
│   ├── menu_state.py       ← Menüzustand (Cursor, Pfad, History)
│   ├── menu_builder.py     ← Menübaum aufbauen (Stationsdaten, Favoriten)
│   └── station_store.py    ← Senderdaten-Store (FM/DAB/Webradio)
│
├── trigger/                ← Triggerverarbeitung
│   ├── trigger_dispatcher.py ← Hauptdispatcher (handle_trigger)
│   ├── td_nav.py           ← Navigation + Quellwechsel
│   ├── td_radio.py         ← Radio (DAB/FM/Webradio/Favoriten/Local/Spotify)
│   ├── td_hardware.py      ← Audio-Routing, BT, Lautstärke
│   ├── td_scanner.py       ← Scanner/Spektrum
│   └── td_system.py        ← System (Reboot, Shutdown, Update)
│
├── cli/                    ← pidrivectl CLI
│   ├── cli.py              ← Entry-Point + Subcommand-Parser
│   ├── service.py          ← Service-Layer (svc.play, svc.bt, …)
│   ├── adapters.py         ← IPC/HTTP-Adapter (write_cmd, read_status)
│   └── format.py           ← Ausgabe-Formatierung
│
├── integration/
│   └── avrcp_trigger.py    ← BMW iDrive AVRCP → File-Trigger (echte Impl.)
│
├── modules/                ← Fachmodule
│   ├── audio.py            ← PipeWire/PulseAudio-Kompat: Volume / Routing / Sink-Wahl
│   ├── wifi.py             ← WiFi-Management
│   ├── favorites.py        ← Favoriten-Persistenz
│   ├── local_player.py     ← Lokale Musik (mpv, Ordner/Playlist, Shuffle)
│   ├── usb_music.py        ← USB-Stick-Erkennung & Mount
│   ├── playback_meta.py    ← Metadaten-Reset bei Quellwechsel
│   ├── source_state.py     ← Source-State-Machine (boot_phase, aktive Quelle)
│   ├── system.py           ← System-Infos (RAM, Temp, throttled)
│   ├── update.py           ← OTA-Update-Mechanismus
│   ├── webradio.py         ← mpv-basiertes Webradio (IPC-Socket-Metadaten)
│   ├── platform.py         ← Plattformerkennung + CAPS-Dictionary
│   │
│   ├── dab.py / fm.py / scanner.py   ← Compat-Shims → modules/radio/*
│   │
│   ├── bluetooth/          ← Bluetooth-Subsystem
│   │   ├── bluetooth.py    ← BT-Facade (A2DP, Pairing, Status)
│   │   ├── bt_helpers.py   ← Hilfsfunktionen (MAC, _device_type, bluetoothctl)
│   │   ├── bt_agent.py     ← BT-Agent (DisplayYesNo, Pairing-Automatik)
│   │   ├── bt_devices.py   ← Gerätescan + Discovery
│   │   ├── bt_connect.py   ← Verbindungslogik (connect/disconnect/reconnect)
│   │   ├── bt_audio.py     ← A2DP-Audio-Routing (find_bt_sink_for_mac)
│   │   ├── bt_backup.py    ← Known-Devices-Backup/Restore
│   │   └── bt_watcher.py   ← BT-State-Watcher (Hintergrundprozess)
│   │
│   └── radio/              ← Radio/RF-Subsystem
│       ├── dab.py          ← DAB-Facade (play_by_name, play_station)
│       ├── dab_play.py     ← welle-cli-Integration (Lock-Wait, PCM, DLS)
│       ├── dab_dls.py      ← DLS-Poller (Titel/Interpret aus welle-cli)
│       ├── dab_scan.py     ← DAB-Kanalsuche
│       ├── dab_helpers.py  ← DAB-Hilfsfunktionen (Parsing, JSON-Write)
│       ├── fm.py           ← FM-Wiedergabe (rtl_fm | mpv)
│       ├── scanner.py      ← RTL-SDR Scanner (PMR446, Freenet, VHF, UHF, CB)
│       ├── spectrum.py     ← FFT-Spektrum-Analyzer
│       └── rtlsdr.py       ← RTL-SDR Prozess-Manager (Lock, Ownership, PPM)
│
├── web/                    ← Web-Frontend
│   ├── app.py              ← Flask-App (REST-API + HTML-Seiten, echte Impl.)
│   ├── shared.py           ← Re-Export-Layer für web/shared/*
│   ├── shared/
│   │   ├── constants.py    ← Pfade, ALLOWED_COMMANDS, PA_ENV
│   │   ├── files.py        ← read_json, write_cmd, file_age
│   │   ├── audio.py        ← Audio-Debug-Helfer
│   │   ├── system.py       ← System-Debug-Helfer
│   │   └── view_model.py   ← build_view_model()
│   ├── api/
│   │   ├── routes_audio.py    ← /api/audio, /api/gain, /api/volume
│   │   ├── routes_bt.py       ← /api/bt/*
│   │   ├── routes_dab.py      ← /api/dab/*
│   │   └── routes_webradio.py ← /api/webradio/*
│   ├── templates/
│   │   ├── base.html         ← Layout-Template
│   │   ├── index.html        ← Alltag (Favoriten, Medien, BT, Vol, System)
│   │   ├── index_full.html   ← Voll-Ansicht
│   │   ├── bluetooth.html    ← BT-Verwaltung
│   │   ├── audio.html        ← Audio Debug Cockpit
│   │   ├── diagnostics.html  ← Logs, Diagnose, System
│   │   ├── rf-tools.html     ← DAB/RTL-SDR/Spektrum-Tools
│   │   ├── avrcp.html        ← AVRCP/BMW Debug
│   │   ├── webradio-admin.html ← Webradio-Senderverwaltung
│   │   └── legacy/           ← Alte Templates (Archiv)
│   └── static/
│       ├── css/              ← base.css, cards.css, layout.css
│       ├── style.css
│       └── js/               ← api-core.js, page-*.js (pro Seite ein Modul)
│
└── config/
    ├── settings.json
    ├── stations.json         ← Webradio-Sender
    ├── dab_stations.json     ← DAB-Sender
    ├── fm_stations.json      ← FM-Sender
    ├── favorites.json        ← Favoriten
    └── play_history.json     ← Wiedergabeverlauf (nicht versioniert / .gitignore)
```

---

## Datenfluss: Trigger-System

Alle Eingaben (BMW AVRCP, WebUI, CLI) landen als Text-Zeile in der Append-Queue
`/tmp/pidrive_cmd`, die der Core in seiner Hauptschleife abarbeitet.

```
BMW iDrive (AVRCP)          WebUI (Browser)        pidrivectl (CLI)
       │                          │                       │
integration/avrcp_trigger.py   web/app.py            cli/adapters.py
       │                          │                       │
       └────────────┬─────────────┴───────────┬──────────┘
                    ▼                          ▼
              /tmp/pidrive_cmd  (Append-Queue, eine Zeile = ein Trigger)
                    │
                    ▼
              main_core.py — Core-Loop (check_trigger, ~alle 0.2s)
                    │
                    ▼
        trigger/trigger_dispatcher.py — handle_trigger()
          ┌──────────┬──────────┬───────────┬──────────┐
       td_nav    td_radio   td_hardware  td_scanner  td_system
                    │
                    ▼
              modules/ (Fachmodule: webradio, radio/*, bluetooth/*, audio …)
                    │
                    ▼
       /tmp/pidrive_status.json · /tmp/pidrive_source_state.json · /tmp/pidrive_menu.json
                    │
                    ▼
              web/app.py (Flask API)  →  Browser / pidrivectl
```

Parallel dazu pflegt der Core die BMW-Display-Metadaten über `mpris2.py`
(D-Bus `org.mpris.MediaPlayer2.pidrive`), das von BlueZ ausgelesen wird.

---

## IPC-Dateien (`/tmp/pidrive_*`)

| Datei | Inhalt | Schreiber |
|---|---|---|
| `pidrive_cmd` | Trigger-Queue (Append-Mode) | WebUI, CLI, AVRCP |
| `pidrive_status.json` | Wiedergabe-/BT-/WiFi-Status | `ipc.write_status()` |
| `pidrive_source_state.json` | Aktive Quelle, boot_phase, Transition | `modules/source_state.py` |
| `pidrive_menu.json` | Menüzustand (Cursor, Pfad, Knoten) | `ipc` / Core |
| `pidrive_progress.json` | Task-Fortschritt (Scan, Update) | Core / Module |
| `pidrive_list.json` | Listen-Overlay (blockiert NAV-Trigger) | Core |
| `pidrive_avrcp_events.json` | AVRCP-Event-Ringbuffer (30 Events) | `integration/avrcp_trigger.py` |
| `pidrive_avrcp_status.json` | Letztes AVRCP-Event / Kontext | `integration/avrcp_trigger.py` |
| `pidrive_dab_play_debug.json` | DAB Lock/PCM/DLS Debug | `modules/radio/dab_helpers.py` |
| `pidrive_dab_welle.err` | welle-cli stderr (Sync, PCM, DLS) | welle-cli (überschrieben pro Start) |
| `pidrive_mpv.sock` | mpv IPC-Socket (Metadaten) | mpv |
| `pidrive_test_results.json` | Ergebnis `pidrivectl test all` | `test_suite.py` |

---

## API-Endpunkte (Auswahl)

| Endpunkt | Quelle | Beschreibung |
|---|---|---|
| `GET /api/core` | `web/app.py` | Schnell-Poll: Status + Menü + Progress |
| `POST /api/cmd` | `web/app.py` | Trigger senden (Whitelist `ALLOWED_COMMANDS`) |
| `GET /api/state` | `web/app.py` | Status-JSON |
| `GET /api/runtime` | `web/app.py` | Laufzeit-/Prozess-Info |
| `GET /api/playlist` | `web/app.py` | Aktuelle Playlist |
| `GET /api/audio` | `web/api/routes_audio.py` | Audio-Routing-Details |
| `GET /api/volume` · `GET /api/gain` | `web/api/routes_audio.py` | Lautstärke / Gain |
| `GET /api/bt/known` · `/api/bt/discovered` | `web/api/routes_bt.py` | BT-Geräte |
| `POST /api/bt/connect_known` | `web/api/routes_bt.py` | Bekanntes Gerät verbinden |
| `GET /api/dab/status` · `/api/dab/diag` | `web/api/routes_dab.py` | DAB Lock/PCM/DLS |
| `GET /api/dab/scan/last` | `web/api/routes_dab.py` | Letztes Scan-Ergebnis |
| `GET /api/webradio/stations` | `web/api/routes_webradio.py` | Webradio-Senderliste |
| `GET /api/spectrum/last` | `web/app.py` | FFT-Spektrum-Snapshot |
| `GET /api/rtlsdr` | `web/app.py` | RTL-SDR-Status |
| `GET /api/logs?target=core` | `web/app.py` | Core-Log |
| `GET /api/avrcp` | `web/app.py` | AVRCP-Debug-Status |
| `GET /api/system/resources` | `web/app.py` | RAM/CPU/Temp |

---

## pidrivectl CLI (Kurzreferenz)

```bash
pidrivectl status              # Systemstatus
pidrivectl now                 # Aktuelle Wiedergabe
pidrivectl version             # Version
pidrivectl play dab "ROCK FM"  # DAB-Sender starten (oder: play dab 22)
pidrivectl play web "Bayern 1" # Webradio starten (oder: play web 1)
pidrivectl play fm 104.4       # FM starten
pidrivectl play spotify        # Spotify Connect
pidrivectl play local /pfad    # Lokale Musik [--shuffle]
pidrivectl stop                # Stoppen
pidrivectl favorites list      # Favoriten
pidrivectl bt scan / pair / connect / known / status
pidrivectl audio route bt|klinke|hdmi|auto
pidrivectl volume up / down / set 70
pidrivectl dab scan / status / live / stop
pidrivectl test all            # Komplett-Systemtest
pidrivectl debug mpris status  # MPRIS2 D-Bus prüfen
```

Vollständige Referenz: `pidrivectl --help` sowie `KontextPiDrive.md`.

---

## Systemd-Dienste

| Service | Aufgabe | Entry-Point |
|---|---|---|
| `pidrive_core.service` | Core-Loop, Wiedergabe, Menü, MPRIS2, BT-Agent | `main_core.py` |
| `pidrive_web.service` | WebUI + REST-API (Port 8080) | `webui.py` → `web/app.py` |
| `pidrive_avrcp.service` | BMW AVRCP → Trigger-Queue | `integration/avrcp_trigger.py` |
| `pipewire.service` | Audio-Server (System-Mode, `User=pulse`) | — |
| `pipewire-pulse.service` | PulseAudio-Kompat (`/var/run/pulse/native`) | — |
| `wireplumber.service` | Session-Manager, BT A2DP automatisch | — |

> `pidrive.service` und `pidrive_display.service` sind Alt-Units aus der TFT-Zeit
> (Display in v0.10.83 entfernt) und werden nicht mehr aktiv genutzt.

---

## Bekannte erwartbare Warnungen

| Meldung | Ursache | Bedeutung |
|---|---|---|
| `DAB: no_lock` / `SyncOnPhase failed` | Schwacher DAB-Empfang (Innenraum) | Im Auto mit Antenne OK, kein Code-Bug |
| `bt_state=failed` | Kein BT-Gerät in Reichweite | Normal bis zum Pairing/Connect |
| `Audio: virtual` | Kein BT-Sink (pidrive_null aktiv) | BT verbinden für echtes Audio |
| `Socket nicht gefunden: /tmp/pidrive_mpv.sock` | mpv noch nicht bereit | Metadaten folgen kurz danach |
| `mpv rc=2 nach 5s` | Kein PA-Sink (BT getrennt) | Erwartet ohne BT, kein Bug |
| `pidrive_display.service: deaktiviert` | TFT entfernt (v0.10.83) | Erwartet |

---

*Weiterführend: `DEVELOPER_GUIDE.md` (Wo liegt der Code?), `RUNTIME_FLOWS.md`
(Laufzeitpfade), `TROUBLESHOOTING.md` (Fehlerbehebung), `KontextPiDrive.md`
(Entwicklungsverlauf & Entscheidungen).*

*Zuletzt aktualisiert: v0.11.122*

# PiDrive — Funktions-Inventar

**Stand:** v0.11.132 · 2026-09-16

Vertrag über garantierte Fähigkeiten. Jede Zeile ist per CLI prüfbar.
Status: ✅ verifiziert · 🟡 nur im Fahrzeug prüfbar · ⛔ bekannt defekt

---

## Wiedergabe

| ID | Fähigkeit | CLI-Prüfung | Erwartung | Abhängigkeit | Stand |
|----|-----------|-------------|-----------|--------------|-------|
| F-001 | DAB-Sender nach Name starten | `pidrivectl play dab "ROCK FM"` | `pidrivectl now` → Quelle DAB | RTL-SDR, welle-cli | 🟡 |
| F-002 | FM-Sender starten | `pidrivectl play fm "104.4"` | `pidrivectl now` → Quelle FM | RTL-SDR | 🟡 |
| F-003 | Webradio starten | `pidrivectl play web "Rock Antenne"` | `pidrivectl now` → Quelle web | Netzwerk | ✅ |
| F-004 | Spotify starten | `pidrivectl play spotify` | librespot aktiv | Spotify OAuth | 🟡 |
| F-005 | Lokale Datei abspielen | `pidrivectl play local /pfad/datei.mp3` | Quelle library | USB/Dateisystem | 🟡 |
| F-006 | Wiedergabe stoppen | `pidrivectl stop` | `pidrivectl now` → idle | Core läuft | ✅ |
| F-007 | DAB next/prev | `pidrivectl dab next` / `prev` | Sender wechselt | DAB aktiv | 🟡 |

## Favoriten

| ID | Fähigkeit | CLI-Prüfung | Erwartung | Abhängigkeit | Stand |
|----|-----------|-------------|-----------|--------------|-------|
| F-010 | Favoritenliste | `pidrivectl favorites list` | JSON/Liste | config/favorites.json | ✅ |
| F-011 | Favorit abspielen | `pidrivectl favorites play 1` | Wiedergabe startet | Core | 🟡 |
| F-012 | Aktuellen Sender merken | Trigger `favorites_add_current` | Eintrag in favorites.json | Core | 🟡 |

## Bluetooth

| ID | Fähigkeit | CLI-Prüfung | Erwartung | Abhängigkeit | Stand |
|----|-----------|-------------|-----------|--------------|-------|
| F-020 | BT-Status | `pidrivectl bt status` | verbunden/getrennt/aus | BT-Dongle | 🟡 |
| F-021 | BT-Geräte scannen | `pidrivectl bt scan` | Geräteliste | BT-Adapter | 🟡 |
| F-022 | BT verbinden | `pidrivectl bt connect <mac\|name>` | verbunden | Gepairtes Gerät | 🟡 |
| F-023 | BT trennen | `pidrivectl bt disconnect` | getrennt | Verbindung aktiv | 🟡 |
| F-024 | BT ein/aus | `pidrivectl bt on` / `off` | Adapter-Status | rfkill | 🟡 |
| F-025 | A2DP Source → BMW | `pidrivectl audio route bt` + Wiedergabe | Audio am Headunit | PipeWire, BlueZ | 🟡 |

## Audio & Lautstärke

| ID | Fähigkeit | CLI-Prüfung | Erwartung | Abhängigkeit | Stand |
|----|-----------|-------------|-----------|--------------|-------|
| F-030 | Lautstärke setzen | `pidrivectl volume set 50` | Level 50 | PipeWire/Pulse | ✅ |
| F-031 | Audio-Route wählen | `pidrivectl audio route klinke` | Route klinke | ALSA/PipeWire | ✅ |
| F-032 | PPM-Offset | `pidrivectl ppm set 45` | Wert gespeichert | RTL-SDR | 🟡 |

## Scanner

| ID | Fähigkeit | CLI-Prüfung | Erwartung | Abhängigkeit | Stand |
|----|-----------|-------------|-----------|--------------|-------|
| F-040 | FM-Scanner | `pidrivectl scanner fm scan` | Scan läuft | RTL-SDR | 🟡 |
| F-041 | PMR446-Scanner | `pidrivectl scanner pmr446 scan` | Scan läuft | RTL-SDR | 🟡 |

## System

| ID | Fähigkeit | CLI-Prüfung | Erwartung | Abhängigkeit | Stand |
|----|-----------|-------------|-----------|--------------|-------|
| F-050 | Systemstatus | `pidrivectl status` | JSON mit Quelle/BT/IP | Core | ✅ |
| F-051 | Schnellübersicht | `pidrivectl now` | Aktuelle Quelle + Titel | Core | ✅ |
| F-052 | Diagnose | `pidrivectl system diagnose` | Keine kritischen Fehler | — | 🟡 |
| F-053 | System-Info | Trigger `sys_info` | Log/Status | Core | ✅ |

## Menü (M0)

| ID | Fähigkeit | CLI-Prüfung | Erwartung | Abhängigkeit | Stand |
|----|-----------|-------------|-----------|--------------|-------|
| F-060 | Menü-Lint | `pidrivectl menu lint` | Exit 0 (Warnungen OK) | Offline | ✅ |
| F-061 | Menü-Verify | `pidrivectl menu verify` | Exit 0, keine Verluste | tests/golden/ | ✅ |
| F-062 | Golden Master | `pidrivectl menu snapshot` | menu_tree.json | Offline | ✅ |
| F-063 | Menü-Kosten | `pidrivectl menu cost sources/dab/...` | Zahl der Tastendrücke | Offline | ✅ |
| F-064 | Ergonomie-Report | `pidrivectl menu report` | Median/Max/Über-20 | Offline | ✅ |
| F-065 | Menübaum export | `pidrivectl menu tree --json` | volle UID-Baumstruktur | Offline | ✅ |
| F-066 | Menü goto | `pidrivectl menu goto sources/dab/...` | Cursor auf Ziel | Offline | ✅ |
| F-067 | Menü activate | `pidrivectl menu activate <uid>` | Knoten ausgewählt | Offline | ✅ |
| F-068 | Rebuild hält Position | `pidrivectl menu rebuild` | Pfad+UID gleich | Offline | ✅ |
| F-069 | iDrive-Event | `pidrivectl idrive next --offline` | Mapping + Menübewegung | Offline | ✅ |
| F-070 | iDrive-Skript ROCK FM | `pidrivectl idrive script tests/idrive/rockfm.txt --offline` | activated=ROCK FM | Offline | ✅ |

## WebUI (W0)

| ID | Fähigkeit | CLI-Prüfung | Erwartung | Abhängigkeit | Stand |
|----|-----------|-------------|-----------|--------------|-------|
| F-080 | Seiten: Alltag `/` | Browser / `curl -s localhost:8080/` | HTML mit Player, Favoriten, Quellen | pidrive_web | 🟡 |
| F-081 | Seiten: Bluetooth `/bluetooth` | `curl -s localhost:8080/bluetooth` | Geräteliste, Scan/Reconnect | pidrive_web | 🟡 |
| F-082 | Seiten: Audio `/audio` | `curl -s localhost:8080/audio` | Route, Volume, Debug-Cockpit | pidrive_web | ✅ S11 behoben |
| F-083 | Seiten: RF/DAB `/rf-tools` | `curl -s localhost:8080/rf-tools` | PPM, RTL-SDR, Spektrum | pidrive_web | 🟡 S4 Hook da; F3 Watch offen |
| F-084 | Seiten: Diagnose `/diagnostics` | `curl -s localhost:8080/diagnostics` | Logs, Ressourcen | pidrive_web | ✅ S5/S8 Feldnamen |
| F-085 | Seiten: AVRCP `/avrcp` | `curl -s localhost:8080/avrcp` | Event-Log | pidrive_web | ✅ S4/S5 |
| F-086 | Seiten: Webradio-Admin | `curl -s localhost:8080/webradio-admin` | Stationen CRUD | pidrive_web | 🟡 |
| F-087 | Seiten: Medien-Admin | `curl -s localhost:8080/music-admin` | Upload/Ordner/ID3 | pidrive_web | 🟡 |
| F-088 | Core-Polling `/api/core` | `curl -s localhost:8080/api/core` | status_age/menu_age top-level; Banner bei >3s | Core+Web | ✅ W2/S1/S2 |
| F-089 | Trigger `/api/cmd` | `curl -X POST …/api/cmd -d '{"cmd":"radio_stop"}'` | ok:true | Core | ✅ |
| F-090 | prev/next Station-Buttons | UI → `dab_prev`/`fm_prev` etc. | Senderwechsel | — | ✅ W3/V4 |
| F-091 | PPM Auto-Kalibrieren | RF-Tools → `fetch /api/ppm_calibrate` | PPM-Wert | — | ✅ W3/V4 |
| F-092 | WebUI-Check | `pidrivectl webui check` | 0 Treffer | Offline | ✅ |
| F-093 | WebUI-Selftest | `pidrivectl webui selftest` | 0 Fehler | Offline | ✅ |
| F-094 | Routen-Inventar | `pidrivectl webui routes` | Liste inkl. Blueprints | Offline | ✅ |
| F-095 | Menü-Fernsteuerung | `/api/core` path/nodes + UI | wie `menu goto/activate` | Core | ⛔ V3 Oberfläche fehlt |
| F-096 | Billige Listen | `curl -s localhost:8080/api/lists` | dab/web/fm/favorites ohne pactl | Web | ✅ W2/S9 |
| F-097 | processes in Status | `/api/core` → `status.processes` | nicht-leer wenn mpv/welle läuft | Core | ✅ W2/S3 |

## Navigation / Trigger (AVRCP → Core)

| ID | Fähigkeit | CLI-Prüfung | Erwartung | Abhängigkeit | Stand |
|----|-----------|-------------|-----------|--------------|-------|
| F-070 | Menü hoch/runter | `pidrivectl debug inject down` | Cursor bewegt sich | Core | 🟡 |
| F-071 | Menü Enter | `pidrivectl debug inject enter` | Aktion/Sender | Core | 🟡 |
| F-072 | Menü Zurück | `pidrivectl debug inject back` | Eine Ebene zurück | Core | 🟡 |
| F-073 | Kategorie-Sprung | Trigger `cat:sources` | Quellen-Ordner | Core | 🟡 |
| F-074 | AVRCP-Inject | `pidrivectl avrcp inject next` | Event verarbeitet | AVRCP-Service | 🟡 |

## Bekannte Lücken

| ID | Fähigkeit | CLI-Prüfung | Erwartung | Stand |
|----|-----------|-------------|-----------|-------|
| F-900 | `dab_scan_replace` | — | Kein Dispatcher-Handler | ⛔ |
| F-901 | `favorites_add:{name}` | `pidrivectl favorites add Name` | Nur `_current` implementiert | ⛔ |
| F-902 | `ppm_calibrate` | `pidrivectl ppm calibrate` | Nur WebUI, nicht Dispatcher | ⛔ |
| F-903 | BMW 3-Zeilen-Display | `pidrivectl now` + iDrive | Metadaten sichtbar | ✅ 2026-09-16 Spotify+Webradio; Menü-Zeilen ⬜ |
| F-904 | Menü-ID-Eindeutigkeit | `pidrivectl menu lint` | 3 doppelte IDs (B3) | ⛔ |

---

*Vollständige Trigger-Liste: `trigger/trigger_dispatcher.py` (`would_handle`).*
*CLI-Referenz: `docs/architektur/ARCHITECTURE.md`, `pidrivectl --help`.*

# PiDrive — Funktions-Inventar

**Stand:** v0.11.127 · 2026-09-15

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
| F-903 | BMW 3-Zeilen-Display | `pidrivectl now` + iDrive | Metadaten sichtbar | 🟡 |
| F-904 | Menü-ID-Eindeutigkeit | `pidrivectl menu lint` | 3 doppelte IDs (B3) | ⛔ |

---

*Vollständige Trigger-Liste: `trigger/trigger_dispatcher.py` (`would_handle`).*
*CLI-Referenz: `docs/architektur/ARCHITECTURE.md`, `pidrivectl --help`.*

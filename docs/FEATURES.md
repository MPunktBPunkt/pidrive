# PiDrive — Funktions-Inventar

**Stand:** v0.11.143 · 2026-09-19

Vertrag über garantierte Fähigkeiten. Jede Zeile ist per CLI prüfbar.
Status: ✅ verifiziert · 🟡 nur im Fahrzeug prüfbar · ⛔ bekannt defekt

---

## Wiedergabe

| ID | Fähigkeit | CLI-Prüfung | Erwartung | Abhängigkeit | Stand |
|----|-----------|-------------|-----------|--------------|-------|
| F-001 | DAB-Sender nach Name starten | `pidrivectl play dab "ROCK FM"` | `pidrivectl now` → Quelle DAB | RTL-SDR, welle-cli | 🟡 Indoor oft no_lock |
| F-002 | FM-Sender starten | `pidrivectl play fm "104.4"` | `pidrivectl now` → Quelle FM | RTL-SDR | ✅ |
| F-003 | Webradio starten | `pidrivectl play web "Rock Antenne"` | `pidrivectl now` → Quelle web | Netzwerk | ✅ |
| F-004 | Spotify starten | `pidrivectl play spotify` | librespot aktiv | Spotify OAuth | 🟡 |
| F-005 | Lokale Datei abspielen | `pidrivectl play local /pfad/datei.mp3` | Quelle library | USB/Dateisystem | 🟡 |
| F-006 | Wiedergabe stoppen | `pidrivectl stop` | `pidrivectl now` → idle | Core läuft | ✅ |
| F-007 | DAB next/prev | `pidrivectl dab next` / `prev` | Sender wechselt | DAB aktiv | 🟡 |
| F-008 | FM next/prev / Listen-Klick | WebUI Alltag / `play_fm:<freq>` | Quelle FM, Name+Freq | RTL-SDR | ✅ v0.11.143 |

## Favoriten

| ID | Fähigkeit | CLI-Prüfung | Erwartung | Abhängigkeit | Stand |
|----|-----------|-------------|-----------|--------------|-------|
| F-010 | Favoritenliste | `pidrivectl favorites list` | JSON/Liste | config/favorites.json | ✅ |
| F-011 | Favorit abspielen | `pidrivectl favorites play 1` | Wiedergabe startet | Core | ✅ |
| F-012 | Aktuellen Sender merken | Trigger `favorites_add_current` | Eintrag in favorites.json | Core | ✅ |

## Bluetooth

| ID | Fähigkeit | CLI-Prüfung | Erwartung | Abhängigkeit | Stand |
|----|-----------|-------------|-----------|--------------|-------|
| F-020 | BT-Status | `pidrivectl bt status` | verbunden/getrennt/aus | BT-Dongle | 🟡 |
| F-021 | BT-Geräte scannen | `pidrivectl bt scan` | Geräteliste | BT-Adapter | 🟡 |
| F-022 | BT verbinden | `pidrivectl bt connect <mac\|name>` | verbunden | Gepairtes Gerät | 🟡 |
| F-023 | BT trennen | `pidrivectl bt disconnect` | getrennt | Verbindung aktiv | 🟡 |
| F-024 | BT ein/aus | `pidrivectl bt on` / `off` | Adapter-Status | rfkill | 🟡 |
| F-025 | A2DP Source → BMW | `pidrivectl audio route bt` + Wiedergabe | Audio am Headunit | PipeWire, BlueZ | 🟡 |
| F-026 | A2DP-Recovery ohne PipeWire-Kill auf Klinke | Route klinke + FM | kein PW-Restart | bt_connect | ✅ |

## Audio & Lautstärke

| ID | Fähigkeit | CLI-Prüfung | Erwartung | Abhängigkeit | Stand |
|----|-----------|-------------|-----------|--------------|-------|
| F-030 | Lautstärke setzen | `pidrivectl volume set 50` | Level 50 | PipeWire/Pulse | ✅ |
| F-031 | Audio-Route wählen | `pidrivectl audio route klinke` | Route klinke | ALSA/PipeWire | ✅ |
| F-032 | PPM-Offset | `pidrivectl ppm set 49` | Wert gespeichert | RTL-SDR | ✅ |
| F-033 | Browser-Monitor | `GET /api/audio/listen` | MP3-Stream | Core + Audio | ✅ |
| F-034 | FM-Gain Default | settings `fm_gain` | 25–30 typisch | UKW-Scan | ✅ |

## Scanner & Spektrum

| ID | Fähigkeit | CLI-Prüfung | Erwartung | Abhängigkeit | Stand |
|----|-----------|-------------|-----------|--------------|-------|
| F-040 | FM-Scanner | `pidrivectl scanner fm scan` | Scan läuft | RTL-SDR | 🟡 |
| F-041 | PMR446-Scanner | `pidrivectl scanner pmr446 ch N` / WebUI 16 Kanäle | NBFM-Audio, Watch, Monitor | RTL-SDR + Walkie | ✅ |
| F-042 | Spektrum-Scan | `pidrivectl spectrum scan [RANGE] -n N` | Peak-Liste | RTL-SDR | ✅ |
| F-043 | Spektrum-Peek | `pidrivectl spectrum peek <mhz>` | Kanalenergie | RTL-SDR | ✅ |
| F-044 | Spektrum last | `pidrivectl spectrum last [--json]` | Letztes Ergebnis | — | ✅ |
| F-045 | PMR446 Dauer-Monitor | `pidrivectl scanner monitor start\|status\|log\|stop` | hits/cycles, JSONL | RTL-SDR | ✅ |
| F-046 | Airband AM | `pidrivectl scanner airband list\|ch\|freq\|scan\|next\|prev\|monitor` / WebUI | AM-Audio, EDJA-Presets, Preset-Scan, Dauer-Monitor | RTL-SDR | ✅ |

## System

| ID | Fähigkeit | CLI-Prüfung | Erwartung | Abhängigkeit | Stand |
|----|-----------|-------------|-----------|--------------|-------|
| F-050 | Systemstatus | `pidrivectl status` | JSON mit Quelle/BT/IP | Core | ✅ |
| F-051 | Schnellübersicht | `pidrivectl now` | Aktuelle Quelle + Titel | Core | ✅ |
| F-052 | Diagnose | `pidrivectl system diagnose` | Keine kritischen Fehler | — | 🟡 |
| F-053 | System-Info | Trigger `sys_info` | Log/Status | Core | ✅ |
| F-054 | OTA-Update prüfen | `pidrivectl update --check` | Lokal/GitHub-Version | git, Netzwerk | ✅ |
| F-055 | OTA-Update einspielen | `pidrivectl update --yes` | Services active | git, sudo | ✅ |
| F-056 | Quellen-Zustand | `pidrivectl source state` | current/transition/`play_gen` | Core | ✅ |
| F-057 | Transition-Historie | `pidrivectl source history` | letzte Übergänge | Core | ✅ |

## Menü (M0)

| ID | Fähigkeit | CLI-Prüfung | Erwartung | Abhängigkeit | Stand |
|----|-----------|-------------|-----------|--------------|-------|
| F-060 | Menü-Lint | `pidrivectl menu lint` | Exit 0 | Offline | ✅ |
| F-061 | Menü-Verify | `pidrivectl menu verify` | Exit 0 | tests/golden/ | ✅ |
| F-062 | Golden Master | `pidrivectl menu snapshot` | menu_tree.json | Offline | ✅ |
| F-063–F-071 | goto/activate/cost/report/walk/idrive | `pidrivectl menu …` / `idrive …` | siehe ARCHITECTURE | Offline | ✅ |

## WebUI (W0)

| ID | Fähigkeit | CLI-Prüfung | Erwartung | Abhängigkeit | Stand |
|----|-----------|-------------|-----------|--------------|-------|
| F-080 | Alltag `/` | `curl -s localhost:8080/` | Player, Favoriten, Listen-Klick | pidrive_web | ✅ |
| F-081 | Bluetooth `/bluetooth` | curl | Geräteliste | pidrive_web | 🟡 |
| F-082 | Audio `/audio` | curl | Route, Volume, Monitor | pidrive_web | ✅ |
| F-083 | RF/DAB `/rf-tools` | curl | PPM, Spektrum | pidrive_web | ✅ |
| F-084 | Diagnose `/diagnostics` | curl | Logs + WebUI Live-Smoke | pidrive_web | ✅ |
| F-085–F-087 | AVRCP / Webradio-Admin / music-admin | curl | Tabs OK | pidrive_web | ✅ |
| F-088 | `/api/core` | curl | status_age | Core+Web | ✅ |
| F-089 | `/api/cmd` | POST radio_stop | ok:true | Core | ✅ |
| F-090 | prev/next | UI | Senderwechsel | — | ✅ |
| F-091 | PPM calibrate | `/api/ppm_calibrate` | PPM | — | ✅ |
| F-092–F-094 | webui check/selftest/routes | pidrivectl webui … | Exit 0 | Offline | ✅ |
| F-095 | Menü-Fernsteuerung UI | — | fehlt | Core | ⛔ |
| F-096 | `/api/lists` | curl | dab/web/fm/fav | Web | ✅ |
| F-097 | status.processes | `/api/core` | nicht-leer | Core | ✅ |
| F-098 | Offline-CI | `bash tools/ci_offline.sh` | Exit 0 | Offline | ✅ |
| F-099 | WebUI Live-Smoke | `pidrivectl webui smoke` / `test all` | FAIL=0 (DAB-Lock indoor optional) | Pi | ✅ |
| F-100 | Alltag Listen-Klick | Tippen DAB/FM/Web-Zeile | play_* via data-attrs | WebUI | ✅ v0.11.143 |

## Navigation / Trigger

| ID | Fähigkeit | Stand |
|----|-----------|-------|
| F-110–F-114 | Menü inject / AVRCP inject | 🟡 Fahrzeug |

## Bekannte Lücken

| ID | Stand |
|----|-------|
| F-901 favorites_add:{name} | ⛔ nur _current |
| F-902 ppm_calibrate CLI | ⛔ nur WebUI |
| F-903 BMW Menü-Zeilen | ⬜ |
| F-904 Indoor-DAB-Lock | 🟡 Signal, nicht SW |

---

*Trigger: `trigger/trigger_dispatcher.py`. Smoke: `tools/webui_live_smoke.py`.*

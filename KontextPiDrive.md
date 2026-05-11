# PiDrive — Kontext & Projektdokumentation v0.10.70

## Projektbeschreibung

**PiDrive** ist ein Raspberry Pi 3B-basiertes Car-Infotainment-System für BMW 118d 2017 (NBT EVO).
Es emuliert einen iPod gegenüber dem BMW iDrive via AVRCP und zeigt eine eigene Menüoberfläche
auf einem TFT-Display. WebUI auf Port 8080 + vollständige Kommandozeile (`pidrivectl`).

**GitHub:** https://github.com/MPunktBPunkt/pidrive

**Install/Update:**
```bash
curl -sL https://raw.githubusercontent.com/MPunktBPunkt/pidrive/main/install.sh | sudo bash
```

---

## Hardware

| Komponente | Details |
|---|---|
| Raspberry Pi | Pi 3 Model B Rev 1.2 |
| Display | Joy-IT RB-TFT3.5, 480×320, SPI, fb1 |
| RTL-SDR | RTL2838 DVB-T (ID 0bda:2838, Rafael Micro R820T) |
| Bluetooth | Cambridge Silicon Radio Dongle |
| Audio-Ausgang | 3.5mm Klinke (hw:1,0) → BMW AUX-IN oder Bluetooth A2DP |
| BMW | BMW 118d 2017, NBT EVO |

---

## Aktueller Stand (v0.10.70)

### Services

| Service | Beschreibung | Status |
|---|---|---|
| `pidrive_core` | Hauptprozess (Menü, Trigger, Radio) | ✓ aktiv |
| `pidrive_web` | Flask WebUI Port 8080 | ✓ aktiv |
| `pidrive_avrcp` | BMW iDrive AVRCP-Integration | ✓ aktiv |
| `pidrive_display` | TFT-Display (nur im Auto) | ⚠ optional |

**WebUI:** http://192.168.178.93:8080

### Quellen

| Quelle | Status |
|---|---|
| DAB+ | ✓ laeuft (instabiler Innenraum-Empfang, im Auto OK) |
| FM | ✓ |
| Webradio | ✓ |
| Bluetooth A2DP | ✓ (Pairing noetig) |
| Spotify | ⚠ OAuth-Setup einmalig nötig |

---

## Verzeichnisstruktur (v0.10.70)

```
pidrive/
├── main_core.py / main_display.py
├── ipc.py / status.py / settings.py / log.py / diagnose.py
├── trigger_dispatcher.py / td_nav.py / td_hardware.py / td_radio.py
├── td_scanner.py / td_system.py
├── menu_model.py / menu_state.py / menu_builder.py / station_store.py
├── avrcp_trigger.py / mpris2.py / mpv_meta.py
│
├── cli/                          ← pidrivectl CLI
│   ├── cli.py / service.py / adapters.py / format.py
│
├── modules/
│   ├── bluetooth/                ← UMGEBAUT ✓
│   │   ├── bluetooth.py / bt_agent.py / bt_audio.py / bt_backup.py
│   │   ├── bt_connect.py / bt_devices.py / bt_helpers.py / bt_watcher.py
│   │   └── __init__.py
│   ├── radio/                    ← UMGEBAUT ✓
│   │   ├── dab.py / dab_helpers.py / dab_play.py / dab_scan.py / dab_dls.py
│   │   ├── fm.py / scanner.py / rtlsdr.py / spectrum.py
│   │   └── __init__.py
│   ├── audio.py / wifi.py / favorites.py / source_state.py
│   ├── library.py / system.py / update.py / webradio.py
│   └── bt_*.py / dab_*.py ...    ← DEPRECATED SHIM (→ v0.11)
│
├── web/                          ← UMGEBAUT ✓
│   ├── app.py                    ← Flask-App
│   ├── shared/
│   │   ├── __init__.py / constants.py / files.py
│   │   ├── system.py / audio.py / view_model.py
│   ├── api/routes_audio.py / routes_bt.py / routes_dab.py / routes_webradio.py
│   ├── templates/
│   │   ├── base.html / index.html / bluetooth.html / audio.html
│   │   ├── rf-tools.html / diagnostics.html / avrcp.html / webradio-admin.html
│   └── static/css/ + js/
│
├── config/
│   ├── settings.json / dab_stations.json / fm_stations.json
│   ├── stations.json / favorites.json
│
├── webui.py / webui_shared.py    ← DEPRECATED SHIM
├── cli.py / cli_*.py             ← DEPRECATED SHIM
└── VERSION
```

---

## pidrivectl Kommandoreferenz

```bash
pidrivectl status              # Systemstatus inkl. Volume
pidrivectl now                 # Aktuelle Wiedergabe + DLS
pidrivectl quick               # Schnellübersicht
pidrivectl version             # Version
pidrivectl play dab "ROCK FM"  # DAB (Name oder Nummer)
pidrivectl play dab 27         # DAB per Listennummer
pidrivectl play web "Bayern 1" # Webradio
pidrivectl play fm 104.4       # FM
pidrivectl stop / dab stop     # Stoppen
pidrivectl station list dab|fm|web
pidrivectl favorites list
pidrivectl favorites add       # Aktuellen Sender
pidrivectl bt scan             # Live-Scan + Fortschrittsbalken
pidrivectl bt connect <mac>
pidrivectl volume up           # Zeigt neue Prozentzahl
pidrivectl volume 50           # Direkt setzen (pactl)
pidrivectl audio route klinke|bt|hdmi
pidrivectl dab status          # Lock/PCM/Sync/Fehler
pidrivectl system resources    # RAM, Disk, Uptime, Throttled
pidrivectl log [core|display|avrcp]
pidrivectl debug               # Status/Source/Menu JSON
```

---

## Bekannte offene Punkte

| Thema | Status |
|---|---|
| Display-Treiber | ⚠ Fehlt (LCD-show) |
| Raspotify OAuth | ⚠ Einmalige Browser-Anmeldung nötig |
| BT Pairing | ⚠ Kopfhörer noch nie gepairt |
| Webradio Antenne Bayern URL | ⚠ mpv-Fehler |
| Phase 3 Umbau (core/, menu/, trigger/) | ⏳ Geplant für v0.11 |

---

## Erwartete Warnungen (kein Fehler)

| Meldung | Bedeutung |
|---|---|
| `fbcon not available` | TFT nicht angesteckt |
| `DAB: partial_sync` | Innenraum-Empfang, im Auto besser |
| `bt_state=failed` | Kein BT-Gerät in Reichweite |
| `throttled=0x20002` | Unterspannung: 5V/3A Netzteil empfohlen |
| `Raspotify: nicht aktiv` | OAuth-Setup nötig |
| `usb_claim_interface error -6` | RTL-SDR bereits belegt |

---

## Arbeitsweise mit Claude

1. Claude auditiert Files aus GitHub-Repo
2. Implementiert Patches via Python (str.replace)
3. Verifiziert mit `py_compile.compile()`
4. Bumpt VERSION + PIDRIVE_VERSION in install.sh
5. Erstellt ZIP für manuellen GitHub-Upload
6. Martin deployed per `git pull` + Installer

**Silent-Patch-Risiko:** Immer `assert old_pattern in src` vor replace prüfen.

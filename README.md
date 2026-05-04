# PiDrive 🚗🎵

Raspberry Pi Car Infotainment — Spotify Connect, Webradio, DAB+, FM, MP3 für BMW iDrive und ähnliche Systeme.

[![Version](https://img.shields.io/badge/version-0.10.22-orange.svg)](https://github.com/MPunktBPunkt/pidrive/blob/main/pidrive/VERSION)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python 3](https://img.shields.io/badge/python-3.x-green.svg)](https://www.python.org/)
[![Raspberry Pi](https://img.shields.io/badge/Raspberry%20Pi-3B%2F4-red.svg)](https://www.raspberrypi.org/)

---

## Projektbeschreibung

PiDrive verwandelt einen Raspberry Pi in ein vollwertiges Car-Infotainment-System. Es emuliert einen iPod gegenüber BMW iDrive (oder ähnlichen Systemen) und zeigt auf einem TFT-Display ein eigenes Menü zur Steuerung von:

- 🎵 **Spotify Connect** (via Raspotify) mit Track-Anzeige
- 📻 **Webradio** (via mpv, konfigurierbare Stationen)
- 📡 **DAB+** (RTL-SDR + welle.io, Sendersuche & Speicherung)
- 🔊 **FM Radio** (RTL-SDR, manuelle Frequenzeingabe)
- 💿 **MP3 Bibliothek** mit Album-Art Anzeige
- 📶 **WiFi** Steuerung
- 🔵 **Bluetooth** Kopplung & Audio-Ausgang
- 🔉 **Audioausgang** wählen (Klinke / HDMI / BT / Kombiniert)
- 🔄 **OTA Updates** direkt aus dem Menü

---

## Changelog

### v0.10.0 (2026-05-02)
- Bugfix-Release basierend auf Code-Review v0.9.31
- Kritische Fixes: DAB Resume, BT non-blocking I/O, Scanner source_state
- Mittlere Fixes: DAB session ERR-Files, DLS cleanup, Spectrum Pi 3B Guards

---

## Hardware

| Komponente | Details |
|---|---|
| Raspberry Pi | Pi 3B (getestet), Pi 4 geplant |
| Display | Joy-IT RB-TFT3.5, 480×320, XPT2046 Touch (SPI) |
| Audio-Ausgang | 3.5mm Klinke → Autoradio AUX-IN |
| Stromversorgung | USB-KFZ-Adapter 5V/2A (Micro-USB) |
| Optional | RTL-SDR Stick für DAB+ und FM |

### Verbindung mit dem Auto

```
Pi 3.5mm Klinke ──────────────────── Auto AUX-IN
Pi Micro-USB ──── USB-KFZ-Adapter ── KFZ 12V
Pi WLAN/USB ──── Heimnetz/Tethering ── SSH / http://PI-IP:8080
```

Audio-Ausgang aktivieren: `echo "audio_klinke" > /tmp/pidrive_cmd`

### GPIO-Pinbelegung (Joy-IT RB-TFT3.5)

| Funktion | GPIO |
|---|---|
| DC (Data/Control) | GPIO 24 |
| Reset | GPIO 25 |
| PENIRQ (Touch) | GPIO 17 |
| Key 1 | GPIO 23 |
| Key 2 | GPIO 24 |
| Key 3 | GPIO 25 |

---

## Installation

### Schnellinstallation (ein Befehl)

```bash
curl -sL https://raw.githubusercontent.com/MPunktBPunkt/pidrive/main/install.sh | sudo bash
```

Das Script erledigt in 10 Schritten alles automatisch: Pakete, Repo, rc.local, udev-Regel für TTY3, Service einrichten und starten.

### Manuelle Installation

```bash
git clone https://github.com/MPunktBPunkt/pidrive ~/pidrive
cd ~/pidrive
sudo bash install.sh
```

### Display-Treiber einrichten

```bash
git clone https://github.com/goodtft/LCD-show ~/LCD-show
cd ~/LCD-show && sudo ./LCD35-show
# Pi startet automatisch neu
```

### Spotify OAuth einrichten (einmalig)

```bash
sudo systemctl stop raspotify

# SSH-Tunnel auf PC öffnen (neues Terminal):
ssh -L 5588:127.0.0.1:5588 pi@<PI-IP> -N

# OAuth starten
/usr/bin/librespot --name "PiDrive" --enable-oauth \
  --system-cache /var/cache/raspotify
# Angezeigte URL im Browser öffnen → Spotify Login
```

#
## settings.json — Konfigurationsreferenz (v0.9.6)

| Key | Standard | Erklärung |
|---|---|---|
| `ppm_correction` | `49` | Quarzfehler RTL-SDR Stick (ppm) — gemessen per Kalibrierung |
| `fm_gain` | `30` | FM Gain in dB, `-1` = Auto-AGC |
| `dab_gain` | `-1` | DAB+ Gain, `-1` = Auto-AGC (empfohlen) |
| `scanner_gain` | `-1` | Scanner Gain, `-1` = Auto-AGC |
| `scanner_squelch` | `10` | Rauschunterdrückung, 0=offen, 10=empfindlich, 25=Standard |
| `dab_scan_wait_lock` | `20` | Sekunden pro DAB-Kanal beim Scan (für schwachen Empfang erhöhen) |
| `dab_scan_http_timeout` | `4` | HTTP-Timeout für mux.json-Abruf in Sekunden |
| `dab_scan_port` | `7981` | welle-cli Port beim Scan (getrennt von WebUI-Diagnose Port 7979) |
| `dab_scan_channels` | `["11D","10A","8D","8B","11B"]` | Gezielte Scan-Kanäle, leer = Vollscan aller 38 Kanäle |
| `audio_output` | `"auto"` | Audioausgang: `auto`, `klinke`, `bt`, `hdmi` |
| `volume` | `90` | Startup-Lautstärke in % |
| `last_source` | `""` | Letzte Quelle für Boot-Resume (FM/DAB/Webradio) |


## Update

```bash
curl -sL https://raw.githubusercontent.com/MPunktBPunkt/pidrive/main/install.sh | sudo bash
```

Oder manuell:
```bash
cd ~/pidrive && git pull
# Services: pidrive_core, pidrive_display, pidrive_web, pidrive_avrcp
sudo systemctl daemon-reload && sudo systemctl restart pidrive
```

Oder direkt im Menü: **System → Update → Update installieren**

### Manueller Neustart (Entwicklung)

```bash
sudo systemctl restart pidrive
```

---

## Projektstruktur

```
pidrive/
├── install.sh               # Schnellinstallation + Update (10 Schritte)
├── setup_bt_audio.sh        # PulseAudio BT Audio Setup
├── KontextPiDrive.md        # Vollständige Projektdokumentation
├── README.md
├── systemd/
│   ├── pidrive_core.service    # Headless Core (kein pygame)
│   ├── pidrive_display.service # pygame Display (fb1 direkt)
│   ├── pidrive_web.service     # Flask Web UI Port 8080
│   └── pidrive_avrcp.service   # AVRCP BMW iDrive
└── pidrive/
    ├── main_core.py             # Core: Boot, check_trigger(), main loop
    ├── trigger_dispatcher.py    # Trigger-Dispatcher (aus main_core ausgelagert)
    ├── td_nav.py                # Sub-Dispatcher: Navigation + Menü-Aktionen
    ├── td_hardware.py           # Sub-Dispatcher: Audio, WiFi/BT, Gain, PPM
    ├── td_radio.py              # Sub-Dispatcher: DAB/FM Suchlauf, Webradio
    ├── td_scanner.py            # Sub-Dispatcher: Scanner-Steuerung
    ├── td_system.py             # Sub-Dispatcher: System-Kommandos, Bibliothek
    ├── main_display.py          # Display: pygame auf fb1, 20fps
    ├── ipc.py                   # IPC: atomares JSON /tmp/pidrive_*.json
    ├── menu_model.py            # Facade: MenuNode, MenuState, StationStore, build_tree
    ├── menu_state.py            # MenuNode + MenuState (Navigation)
    ├── station_store.py         # StationStore (Senderdaten, Favoriten)
    ├── menu_builder.py          # build_tree() (Menübaum-Konstruktion)
    ├── mpris2.py                # MPRIS2 D-Bus → BMW-Display Metadaten
    ├── avrcp_trigger.py         # AVRCP 1.5 → File-Trigger Bridge
    ├── webui.py                 # Flask Web UI Port 8080 (+ Blueprint-Registrierung)
    ├── webui_shared.py          # Shared Helpers für alle WebUI-Blueprints
    ├── status.py                # Status-Cache (Hintergrund-Thread)
    ├── log.py                   # Logging (rotierend, max 512KB)
    ├── diagnose.py              # Diagnose-Script (Standalone)
    ├── web/
    │   ├── templates/index.html # WebUI Single-Page-App
    │   ├── static/style.css
    │   └── api/
    │       ├── routes_dab.py       # Blueprint: /api/dab/*
    │       ├── routes_bt.py        # Blueprint: /api/bt/*
    │       ├── routes_audio.py     # Blueprint: /api/audio, /api/gain, /api/volume
    │       └── routes_webradio.py  # Blueprint: /api/webradio/*
    ├── modules/
    │   ├── source_state.py      # Zustandsmaschine (source_current, audio_route, BT)
    │   ├── audio.py             # Audio-Routing (decide/apply/build_player_args)
    │   ├── bluetooth.py         # Facade: alle BT-Funktionen
    │   ├── bt_helpers.py        # BT Basis-Helfer, Konstanten, Adapter-Steuerung
    │   ├── bt_agent.py          # BT-Agent, Pairing
    │   ├── bt_devices.py        # Geräte-Datenbank, Scan
    │   ├── bt_audio.py          # PulseAudio-Sink, A2DP-Management
    │   ├── bt_connect.py        # Connect/Disconnect, Reconnect-State
    │   ├── bt_watcher.py        # Auto-Reconnect Watcher
    │   ├── dab.py               # Facade: alle DAB-Funktionen
    │   ├── dab_helpers.py       # DAB Hilfsfunktionen, Konstanten, Session
    │   ├── dab_dls.py           # DLS-Poller (Dynamic Label Segment)
    │   ├── dab_scan.py          # DAB Suchlauf, Sender-Datenbank
    │   ├── dab_play.py          # DAB Wiedergabe (welle-cli)
    │   ├── fm.py                # FM Radio (RTL-SDR + rtl_fm)
    │   ├── scanner.py           # Funkscanner (PMR446/Freenet/LPD433/VHF/UHF)
    │   ├── spectrum.py          # RTL-SDR Spektrum-Analyse
    │   ├── rtlsdr.py            # RTL-SDR USB-Management + Lock
    │   ├── webradio.py          # Webradio (mpv + PulseAudio)
    │   ├── musik.py             # Spotify Connect (Raspotify)
    │   ├── library.py           # MP3 Bibliothek mit Album-Art
    │   ├── wifi.py              # WiFi Steuerung + Scan
    │   ├── favorites.py         # Favoritenliste
    │   ├── system.py            # System-Info, Neustart
    │   └── update.py            # OTA Update via GitHub
    └── config/
        ├── settings.json        # Einstellungen (Audio, letzte Station)
        ├── dab_stations.json    # DAB+ Sender (nach Scan)
        ├── fm_stations.json     # FM Sender
        ├── stations.json        # Webradio-Stationen
        └── favorites.json       # Favoritenliste

---

## Menü-Struktur

Baumbasiert (v0.8.x) — beliebig tief, iDrive-kompatibel.

```
PiDrive  (v0.9.6 — Baumbasiert, beliebig tief)
├── Jetzt laeuft
│   ├── Quelle / Titel         (info)
│   ├── Spotify An/Aus         (toggle)
│   ├── Audioausgang           (action)
│   ├── Lauter / Leiser        (action)
│   └── Wiedergabe stoppen     (action)
├── Favoriten
│   ├── ★ Bayern 3             (station — FM)
│   ├── ★ BR Klassik           (station — DAB+)
│   └── ★ Radio BOB!           (station — Webradio)
├── Quellen
│   ├── Spotify
│   │   ├── Spotify An/Aus     (toggle)
│   │   └── Status             (info)
│   ├── Bibliothek
│   │   ├── Durchsuchen        (action → Dateiliste)
│   │   └── Stop               (action)
│   ├── Webradio
│   │   ├── Sender             (folder — aus stations.json)
│   │   │   ├── ★ Bayern 3 [Pop/Rock]    (station)
│   │   │   │   └── ★ Zu Favoriten       (action)
│   │   │   └── ...
│   │   └── Sender neu laden   (action)
│   ├── DAB+
│   │   ├── Sender             (folder — aus dab_stations.json)
│   │   │   ├── ★ Bayern 1 [11D]         (station)
│   │   │   │   └── ★ Zu Favoriten       (action)
│   │   │   └── ...
│   │   ├── Suchlauf starten   (action)
│   │   ├── Naechster / Vorheriger Sender (action)
│   ├── FM Radio
│   │   ├── Sender             (folder — aus fm_stations.json)
│   │   │   ├── ★ Bayern 3  99.4 MHz     (station)
│   │   │   │   └── ★ Zu Favoriten       (action)
│   │   │   └── ...
│   │   ├── Suchlauf starten   (action)
│   │   ├── Naechster / Vorheriger / Manuell (action)
│   └── Scanner
│       ├── PMR446 / Freenet / LPD433 / VHF / UHF
│       │   ├── Kanal +/−      (action)
│       │   └── Scan weiter/zurück (action)
├── Verbindungen
│   ├── Bluetooth An/Aus       (toggle)
│   ├── Geraete scannen        (action → 15s)
│   ├── Geraete                (folder — nach Scan)
│   │   ├── HD 4.40BT          (action → bt_connect:MAC)
│   │   └── ...
│   ├── Verbunden mit          (info)
│   ├── WiFi An/Aus            (toggle)
│   ├── Netzwerke scannen      (action)
│   ├── Netzwerke              (folder — nach Scan)
│   │   ├── Heimnetz           (action → wifi_connect:SSID)
│   │   └── ...
│   └── SSID                   (info)
└── System
    ├── IP Adresse             (info)
    ├── System-Info            (action)
    ├── Version                (action)
    ├── Neustart / Ausschalten (action)
    └── Update                 (action, OTA via GitHub)
```

**Knotentypen:**
- `folder` → führt tiefer (▸)
- `station` → spielt ab (♪), Favoriten zuerst mit ★
- `action` → führt Aktion aus (→)
- `toggle` → An/Aus (◉)
- `info` → nur Anzeige (ℹ)

**Navigation:**
- `up/down` — Eintrag wählen
- `enter/right` — tiefer (folder) oder ausführen (station/action/toggle)
- `back/left` — eine Ebene zurück
- `cat:0..3` — direkt zur Hauptkategorie

---

## Steuerung

### Steuerung (File-Trigger / Web)

| Taste | Funktion |
|---|---|
| ↑ / W | Hoch |
| ↓ / S | Runter |
| → / Enter / D | Auswählen |
| ← / ESC / A | Zurück |
| F1 | Audio: Klinke |
| F2 | Audio: HDMI |
| F3 | Audio: Bluetooth |
| F4 | Audio: Alle |

### SSH-Terminal

```bash
# Steuerung via /tmp/pidrive_cmd oder WebUI
```

### File-Trigger (`/tmp/pidrive_cmd`)

```bash
echo "up"           > /tmp/pidrive_cmd
echo "down"         > /tmp/pidrive_cmd
echo "enter"        > /tmp/pidrive_cmd
echo "back"         > /tmp/pidrive_cmd
echo "cat:0"        > /tmp/pidrive_cmd   # Jetzt läuft
echo "cat:1"        > /tmp/pidrive_cmd   # Quellen
echo "cat:2"        > /tmp/pidrive_cmd   # Verbindungen
echo "cat:3"        > /tmp/pidrive_cmd   # System
echo "wifi_on"      > /tmp/pidrive_cmd
echo "spotify_on"   > /tmp/pidrive_cmd
echo "spotify_off"  > /tmp/pidrive_cmd
echo "radio_stop"   > /tmp/pidrive_cmd
echo "reboot"       > /tmp/pidrive_cmd
echo "shutdown"     > /tmp/pidrive_cmd
```

---

## Logging & Debugging

```bash
# Live-Log (launcher.py + main.py, alles in einer Datei)
tail -f /var/log/pidrive/pidrive.log

# Service-Log (journald)
journalctl -u pidrive -f

# Nur Fehler
journalctl -u pidrive -p err

# Launcher-Schritte filtern
grep "LAUNCH" /var/log/pidrive/pidrive.log

# Menü-Navigation
grep "MENU" /var/log/pidrive/pidrive.log
```

---

## /boot/config.txt (wichtige Einstellungen)

```ini
camera_auto_detect=0    # PFLICHT: SPI Display funktioniert sonst nicht
display_auto_detect=0   # PFLICHT
dtoverlay=tft35a:rotate=90
hdmi_force_hotplug=1
hdmi_group=2
hdmi_mode=87
hdmi_cvt=480 320 60 6 0 0 0
hdmi_drive=2
```

Vollständige Konfiguration: `config.txt.example`

---

## Bekannte Probleme

| Problem | Ursache | Lösung |
|---|---|---|
| Display inaktiv | pidrive_display.service nicht gestartet | `systemctl status pidrive_display` |
| "Unable to open console terminal" | `/dev/tty3` nicht lesbar | udev-Regel: `KERNEL=="tty3", MODE="0660"` |
| Service Restart-Schleife | HUP bei TTY-Zuweisung | launcher.py mit setsid+TIOCSCTTY (v0.3.7) |
| Spotify nicht sichtbar | Credential-Cache deaktiviert | `LIBRESPOT_DISABLE_CREDENTIAL_CACHE` auskommentieren |
| Spotify kein Ton | Core ohne PULSE_SERVER | `PULSE_SERVER=unix:/var/run/pulse/native` in pidrive_core.service |
| WLAN nach Reboot aus | rfkill | rfkill-unblock.service |
| Raspotify startet zu früh | falsches network target | `network-online.target` im Service |
| Touch reagiert nicht | Hardware-Defekt (XPT2046) | USB-Tastatur als Alternative |

---

## Abhängigkeiten

```bash
sudo apt install python3-pygame python3-pip git mpv \
  avahi-daemon bluez pulseaudio pulseaudio-module-bluetooth \
  rfkill rtl-sdr sox

pip3 install mutagen --break-system-packages

# Optional für DAB+
sudo apt install welle.io
```

---


> Vollständiger Changelog: `KontextPiDrive.md`

# PiDrive 🚗🎵

Raspberry Pi Car Infotainment — Spotify Connect, Webradio, DAB+, FM, MP3 für BMW iDrive und ähnliche Systeme.

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python 3](https://img.shields.io/badge/python-3.x-green.svg)](https://www.python.org/)
[![Raspberry Pi](https://img.shields.io/badge/Raspberry%20Pi-3B%2F4-red.svg)](https://www.raspberrypi.org/)
[![Version](https://img.shields.io/badge/version-0.6.5-orange.svg)](https://github.com/MPunktBPunkt/pidrive/blob/main/pidrive/VERSION)

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

## Hardware

| Komponente | Details |
|---|---|
| Raspberry Pi | 3B oder 4 |
| Display | Joy-IT RB-TFT3.5, 480×320, XPT2046 Touch |
| Verbindung | SPI (erste 26 GPIO-Pins) |
| Optional | RTL-SDR Stick für DAB+ und FM |

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

### Update

```bash
curl -sL https://raw.githubusercontent.com/MPunktBPunkt/pidrive/main/install.sh | sudo bash
```

Oder manuell:
```bash
cd ~/pidrive && git pull
sudo cp systemd/pidrive.service /etc/systemd/system/pidrive.service
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
├── pidrive/
│   ├── launcher.py      # TTY-Setup (setsid + TIOCSCTTY), startet main.py
│   ├── main.py          # Hauptprogramm & Main-Loop
│   ├── ui.py            # UI-Basisklassen
│   ├── status.py        # System-Status Cache
│   ├── trigger.py       # File-Trigger Handler
│   ├── log.py           # Logging (rotierend, max 512KB)
│   ├── modules/
│   │   ├── musik.py     # Spotify & Wiedergabe
│   │   ├── webradio.py  # Webradio (mpv)
│   │   ├── library.py   # MP3 Bibliothek mit Album-Art
│   │   ├── dab.py       # DAB+ Radio (RTL-SDR + welle.io)
│   │   ├── fm.py        # FM Radio (RTL-SDR + rtl_fm)
│   │   ├── wifi.py      # WiFi Steuerung
│   │   ├── bluetooth.py # Bluetooth Kopplung & Audio
│   │   ├── audio.py     # Audioausgang Steuerung
│   │   ├── system.py    # System-Info, Neustart, etc.
│   │   ├── scanner.py   # Funkscanner (PMR446, Freenet, LPD433, VHF, UHF)
│   │   └── update.py    # OTA Update via GitHub
│   └── config/
│       ├── stations.json      # Webradio-Stationen
│       ├── dab_stations.json  # DAB+ Sender (nach Scan)
│       ├── fm_stations.json   # FM Sender
│       └── settings.json      # Einstellungen
├── systemd/
│   └── pidrive.service  # Systemd Service (User=root, launcher.py)
├── pidrive_ctrl.py      # SSH Tastatur-Steuerung
├── install.sh           # Schnellinstallation (10 Schritte)
├── setup_pidrive.sh     # Vollständiges Setup-Script
├── config.txt.example   # Beispiel /boot/config.txt
├── KontextPiDrive.md    # Vollständige Projektdokumentation
└── README.md
```

---

## Menü-Struktur

```
PiDrive
├── Musik
│   ├── Spotify (Toggle + Track-Anzeige)
│   ├── Wiedergabe (Titel | Artist | Album)
│   ├── Bibliothek (MP3 mit Album-Art)
│   ├── Webradio (konfigurierbare Stationen)
│   ├── DAB+ (RTL-SDR, Sendersuche)
│   ├── FM Radio (UKW, manuelle Frequenz)
│   └── Scanner (PMR446/Freenet/LPD433/VHF/UHF)
├── WiFi
│   ├── WiFi An/Aus
│   ├── Verbunden mit (SSID)
│   └── Netzwerke scannen
├── Bluetooth
│   ├── Bluetooth An/Aus
│   ├── Geräte scannen & koppeln
│   ├── Als Audio-Ausgang setzen
│   └── Alle trennen
└── System
    ├── Audioausgang (Klinke/HDMI/BT/Alle)
    ├── Lauter / Leiser
    ├── IP Adresse
    ├── Hostname
    ├── System-Info (CPU-Temp, Uptime)
    ├── Version
    ├── Neustart / Ausschalten
    └── Update (OTA via GitHub)
```

---

## Steuerung

### USB-Tastatur direkt am Pi

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
python3 ~/pidrive_ctrl.py
```

### File-Trigger (`/tmp/pidrive_cmd`)

```bash
echo "up"           > /tmp/pidrive_cmd
echo "down"         > /tmp/pidrive_cmd
echo "enter"        > /tmp/pidrive_cmd
echo "back"         > /tmp/pidrive_cmd
echo "cat:0"        > /tmp/pidrive_cmd   # Musik
echo "cat:1"        > /tmp/pidrive_cmd   # WiFi
echo "cat:2"        > /tmp/pidrive_cmd   # Bluetooth
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
| Spotify kein Ton | PulseAudio als root | `LIBRESPOT_BACKEND=alsa` + `DEVICE=hw:1,0` |
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

## Changelog

### v0.6.5 — Web UI
- WebUI: Flask-Webinterface auf Port 8080 (`pidrive_web.service`)
- Menü-Vorschau im Browser, Navigation, Log-Viewer, Diagnose
- Auto-Refresh alle 2s ohne Seiten-Reload

### v0.6.4 — Split-Screen Display
- Linke Spalte: Kategorien mit Farbkodierung
- Rechte Spalte: Item-Liste mit Scrolling (7 sichtbar)
- Footer: Now Playing (Spotify/Radio) oder Audio-Ausgang

### v0.6.3
- Service: `StartLimitIntervalSec` in `[Unit]` verschoben (systemd 247 fix)

### v0.6.2 — Stabilisierung (GPT-5.4 Empfehlungen)
- Restart-Limit für Core + Display
- Getrennte Logs: `core.log` + `display.log`
- `menu.json`: vollständige Kategorien- und Item-Listen
- Display-Fallback wenn Core offline
- fbcp dauerhaft entfernt
- fm.py + library.py pygame-frei
- Syntax-Check in install.sh vor Service-Start

### v0.6.1
- Alle Module pygame-frei: wifi, webradio, audio, system, musik
- `ipc.py`: `headless_pick()`, `headless_confirm()` via File-Trigger
- `main_display.py`: vtcon1 unbind direkt vor set_mode()
- `scanner.py` SyntaxError behoben

### v0.6.0 — Architektur-Refactoring
- BREAKING: Core/Display getrennt
- `pidrive_core.service` — headless, kein pygame
- `pidrive_display.service` — pygame direkt auf fb1 (480×320, 16bpp)
- `main_core.py` — Trigger, Status, Audio, Menüzustand
- `main_display.py` — reine Anzeige, liest IPC-JSON
- `ipc.py` — atomares JSON zwischen Core und Display
- fbcp entfernt (nicht mehr nötig)
- rc.local bereinigt

### v0.5.x — TTY/VT Debug-Serie
- TIOCSCTTY, PAMName, VT3, fbcon, SDL_VIDEO_FBCON_KEEP_TTY

### v0.3.x — Erste stabile Version
- DAB+, FM Radio, OTA Updates, Webradio, MP3-Bibliothek, Spotify



### v0.3.6
- log.py: Import-Bug behoben (UnboundLocalError: os)
- main.py: Detailliertes Startup-Logging mit System-Check
- Service: `TTYVHangup=no`, `After=rc-local.service`

### v0.3.5
- System-Check beim Start (fb0, fbcp, tty3, pygame, WLAN, Raspotify)

### v0.3.3
- Bugfix: chvt 3 aus Service entfernt (HUP-Signal Schleife)
- Spotify: ALSA Backend (hw:1,0)
- Raspotify: ProtectHome=false, PrivateUsers=false

### v0.3.0
- DAB+ Radio (RTL-SDR + welle.io)
- FM Radio (RTL-SDR + rtl_fm)
- OTA Updates aus dem Menü
- Logging-Modul (rotierend)

### v0.2.0
- Modulare Struktur
- Spotify Track-Anzeige
- Webradio, MP3 Bibliothek mit Album-Art
- Bluetooth Audio-Ausgang

---

## Lizenz

GPL-v3 — siehe [LICENSE](LICENSE)

---

## Roadmap

- [ ] GPIO-Button Navigation (Key1=GPIO23, Key2=GPIO24, Key3=GPIO25)
- [ ] BMW iDrive ESP32 Integration
- [ ] USB-Tethering Autostart
- [ ] Hotspot-Modus
- [ ] DAB+ Programminfo
- [ ] FM RDS Anzeige
- [ ] Equalizer

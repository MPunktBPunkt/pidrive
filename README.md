# PiDrive 🚗🎵

Raspberry Pi Car Infotainment — Spotify Connect, Webradio, DAB+, FM, MP3 für BMW iDrive und ähnliche Systeme.

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python 3](https://img.shields.io/badge/python-3.x-green.svg)](https://www.python.org/)
[![Raspberry Pi](https://img.shields.io/badge/Raspberry%20Pi-3B%2F4-red.svg)](https://www.raspberrypi.org/)
[![Version](https://img.shields.io/badge/version-0.3.4-orange.svg)](https://github.com/MPunktBPunkt/pidrive/blob/main/pidrive/VERSION)

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

### Spotify Name in Raspotify setzen

```bash
sudo nano /etc/raspotify/conf
# LIBRESPOT_NAME="PiDrive"
sudo systemctl restart raspotify
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

### RTL-SDR für DAB+ und FM

```bash
sudo apt install rtl-sdr sox

# Für DAB+ zusätzlich welle-cli:
sudo apt install welle.io
# oder manuell kompilieren: https://github.com/AlbrechtL/welle.io
```

### Update

```bash
cd ~/pidrive
git pull
sudo systemctl restart pidrive
```

Oder direkt im Menü: **System → Update → Update installieren**

**Manueller Neustart** (beim Entwickeln):
```bash
sudo chvt 3 && sudo systemctl restart pidrive
```

**Hinweis nach Service-Änderungen** (z.B. neue `pidrive.service`):
```bash
cd ~/pidrive && git pull
sudo cp ~/pidrive/systemd/pidrive.service /etc/systemd/system/pidrive.service
sudo systemctl daemon-reload
sudo systemctl restart pidrive
```

---

## Projektstruktur

```
pidrive/
├── pidrive/
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
│   │   └── update.py    # OTA Update via GitHub
│   └── config/
│       ├── stations.json      # Webradio-Stationen
│       ├── dab_stations.json  # DAB+ Sender (nach Scan)
│       ├── fm_stations.json   # FM Sender
│       └── settings.json      # Einstellungen
├── systemd/
│   └── pidrive.service  # Systemd Service
├── pidrive_ctrl.py      # SSH Tastatur-Steuerung
├── install.sh           # Schnellinstallation
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
│   └── FM Radio (UKW, manuelle Frequenz)
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

Einfach USB-Tastatur anschließen — funktioniert sofort nach dem Start:

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

### SSH-Terminal (pidrive_ctrl.py)

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
echo "wifi_off"     > /tmp/pidrive_cmd
echo "bt_on"        > /tmp/pidrive_cmd
echo "bt_off"       > /tmp/pidrive_cmd
echo "audio_klinke" > /tmp/pidrive_cmd
echo "audio_hdmi"   > /tmp/pidrive_cmd
echo "audio_bt"     > /tmp/pidrive_cmd
echo "audio_all"    > /tmp/pidrive_cmd
echo "spotify_on"   > /tmp/pidrive_cmd
echo "spotify_off"  > /tmp/pidrive_cmd
echo "radio_stop"   > /tmp/pidrive_cmd
echo "reboot"       > /tmp/pidrive_cmd
echo "shutdown"     > /tmp/pidrive_cmd
```

---

## Logging & Debugging

```bash
# Live-Log
tail -f /var/log/pidrive/pidrive.log

# Service-Log
journalctl -u pidrive -f

# Nur Fehler
journalctl -u pidrive -p err

# Menü-Navigation
grep "MENU" /var/log/pidrive/pidrive.log

# Trigger-Befehle
grep "TRIGGER" /var/log/pidrive/pidrive.log
```

---

## DAB+ Einrichtung

```bash
# RTL-SDR Stick anschliessen, dann prüfen:
lsusb | grep -i rtl

# welle-cli installieren:
sudo apt install welle.io

# Im Menü: Musik → DAB+ → Sendersuche
# Gefundene Sender werden gespeichert in:
# ~/pidrive/pidrive/config/dab_stations.json
```

---

## FM Radio Einrichtung

```bash
# rtl_fm verfügbar?
which rtl_fm

# Voreingestellte Stationen: pidrive/config/fm_stations.json
# Manuelle Frequenzeingabe: Musik → FM Radio → Manuell
# Pfeiltasten: ±0.1 MHz / Links-Rechts: ±1.0 MHz
```

---

## Webradio Stationen

Bearbeite `pidrive/config/stations.json`:

```json
[
  {
    "name": "Bayern 3",
    "url": "https://dispatcher.rndfnk.com/br/br3/live/mp3/low",
    "genre": "Pop/Rock"
  }
]
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

| Problem | Lösung |
|---|---|
| Display dunkel | `sudo systemctl start pidrive` |
| Spotify nicht sichtbar | `LIBRESPOT_DISABLE_CREDENTIAL_CACHE` auskommentieren |
| WLAN nach Reboot aus | rfkill-unblock.service aktivieren |
| Touch reagiert nicht | Hardware-Defekt; USB-Tastatur als Alternative |
| Raspotify startet ohne Internet | `network-online.target` in Service |
| Spotify spielt nicht | PulseAudio nicht erreichbar | `LIBRESPOT_BACKEND=alsa` + `LIBRESPOT_DEVICE=hw:1,0` |
| PiDrive Restart-Schleife | tty3 nicht aktiv | `After=rc-local.service` im Service; manuell: `sudo chvt 3 && sudo systemctl restart pidrive` |
| Konsole überlagert Display | stdout von Service auf null | `StandardOutput=null` im Service |
| USB-Tastatur reagiert nicht | `sudo chvt 3` (wird automatisch via Service gesetzt) |

---

## Abhängigkeiten

```bash
# System
sudo apt install python3-pygame python3-pip git mpv \
  avahi-daemon bluez pulseaudio pulseaudio-module-bluetooth \
  rfkill rtl-sdr sox

# Python
pip3 install mutagen --break-system-packages

# Optional für DAB+
sudo apt install welle.io
```

---

## Changelog

### v0.3.4
- Startup: 8s Warte-Zeit in main.py (statt ExecStartPre sleep)
- Service: `After=rc-local.service` - chvt 3 laeuft garantiert zuerst
- Mehr Logging beim Start (TTY, Framebuffer, Display-Fehler-Hinweis)
- Manueller Neustart: `sudo chvt 3 && sudo systemctl restart pidrive`

### v0.3.3
- Bugfix: `chvt 3` aus Service entfernt (verursachte HUP-Signal Restart-Schleife)
- chvt 3 läuft weiterhin via rc.local beim Boot
- Spotify: ALSA Backend (`hw:1,0`) statt PulseAudio
- Raspotify: `ProtectHome=false`, `PrivateUsers=false`

### v0.3.2
- Konsole überlagert nicht mehr das Display (`StandardOutput=null`)
- Spotify Name korrekt auf "PiDrive" (statt FakeIpod)
- pidrive.service: `StandardOutput=null`, `StandardError=journal`

### v0.3.1
- UI-Fix: Kategorie-Text läuft nicht mehr in rechte Spalte
- USB-Tastatur: `chvt 3` automatisch beim Service-Start
- `pidrive.service` im `systemd/` Ordner des Repos
- `install.sh` kopiert Service aus Repo

### v0.3.0
- DAB+ Radio (RTL-SDR + welle.io, Sendersuche & Speicherung)
- FM Radio (RTL-SDR + rtl_fm, manuelle Frequenzeingabe)
- OTA Updates direkt aus dem Menü (System → Update)
- Logging-Modul (rotierend, max 512KB)

### v0.2.0
- Modulare Struktur (ui, status, trigger, modules/)
- Spotify Track-Anzeige
- Webradio
- MP3 Bibliothek mit Album-Art
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
- [ ] DAB+ Programminfo (Artist, Titel vom DAB-Stream)
- [ ] FM RDS Anzeige

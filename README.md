# PiDrive 🎵

PiDrive — Raspberry Pi Car Infotainment — für den Einsatz im Auto mit BMW iDrive oder ähnlichen Systemen.

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python 3](https://img.shields.io/badge/python-3.x-green.svg)](https://www.python.org/)
[![Raspberry Pi](https://img.shields.io/badge/Raspberry%20Pi-3B%2F4-red.svg)](https://www.raspberrypi.org/)

---

## Projektbeschreibung

Das Fahrzeug kommuniziert über das iPod-Protokoll mit dem Pi. Der Pi stellt sich als iPod vor und empfängt Steuerbefehle vom iDrive (Vor/Zurück, Menü, Lautstärke). Gleichzeitig läuft auf einem kleinen TFT-Display eine eigene Menüoberfläche zur Steuerung von:

- **Spotify Connect** (via Raspotify)
- **Webradio** (via mpv)
- **MP3 Bibliothek** mit Album-Art Anzeige
- **DAB+ / FM** (in Planung)
- **WiFi** Steuerung
- **Bluetooth** Kopplung & Audio-Ausgang
- **Audio-Ausgang** wählen (Klinke / HDMI / BT / Kombiniert)

---

## Hardware

| Komponente | Details |
|---|---|
| Raspberry Pi | 3B oder 4 |
| Display | Joy-IT RB-TFT3.5, 480×320, XPT2046 Touch |
| Verbindung | SPI (erste 26 GPIO-Pins) |

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

### Schnellinstallation (von GitHub)

```bash
curl -sL https://raw.githubusercontent.com/DEIN-USER/pidrive/main/install.sh | sudo bash
```

### Manuelle Installation

```bash
# Repository klonen
git clone https://github.com/DEIN-USER/pidrive ~/pidrive
cd ~/pidrive

# Installationsscript ausführen
sudo bash setup_pidrive.sh
```

### Display-Treiber einrichten

```bash
cd ~/LCD-show
sudo ./LCD35-show
# Pi startet automatisch neu
```

### Spotify OAuth einrichten (einmalig)

```bash
sudo systemctl stop raspotify

# OAuth starten
/usr/bin/librespot --name "PiDrive" --enable-oauth \
  --system-cache /var/cache/raspotify

# SSH-Tunnel auf PC öffnen (neues Terminal):
# ssh -L 5588:127.0.0.1:5588 pi@<PI-IP>
# Dann angezeigte URL im Browser öffnen → Spotify Login
```

### Update

```bash
cd ~/pidrive
git pull
sudo systemctl restart ipod
```

---

## Projektstruktur

```
pidrive/
├── pidrive/
│   ├── main.py          # Hauptprogramm & Main-Loop
│   ├── ui.py            # UI-Basisklassen (SplitUI, Items, Dialoge)
│   ├── status.py        # System-Status Cache
│   ├── trigger.py       # File-Trigger Handler
│   ├── modules/
│   │   ├── musik.py     # Spotify & Wiedergabe
│   │   ├── webradio.py  # Webradio (mpv)
│   │   ├── library.py   # MP3 Bibliothek mit Album-Art
│   │   ├── dabfm.py     # DAB+/FM (In Planung)
│   │   ├── wifi.py      # WiFi Steuerung
│   │   ├── bluetooth.py # Bluetooth Kopplung & Audio
│   │   ├── audio.py     # Audioausgang Steuerung
│   │   └── system.py    # System-Info, Neustart, etc.
│   └── config/
│       ├── stations.json   # Webradio-Stationen
│       └── settings.json   # Einstellungen
├── ipod_ctrl.py         # SSH Tastatur-Steuerung
├── install.sh           # GitHub Schnellinstallation
├── setup_pidrive.sh    # Vollständiges Setup-Script
├── config.txt.example   # Beispiel /boot/config.txt
└── README.md
```

---

## Menü-Struktur

```
iPod
├── Musik
│   ├── Spotify (Toggle Ein/Aus + Track-Anzeige)
│   ├── Wiedergabe (aktueller Titel/Artist/Album)
│   ├── Bibliothek (MP3 mit Album-Art)
│   ├── Webradio (konfigurierbare Stationen)
│   └── DAB+ / FM (In Planung)
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
    ├── System-Info (CPU-Temp, Uptime, Disk)
    ├── Version
    ├── Neustart
    └── Ausschalten
```

---

## Steuerung

### SSH-Terminal (ipod_ctrl.py)

```bash
python3 ~/ipod_ctrl.py
```

| Taste | Funktion |
|---|---|
| W / ↑ | Hoch |
| S / ↓ | Runter |
| D / Enter / → | Auswählen |
| A / ESC / ← | Zurück |
| 1–4 | Direkt zu Kategorie |
| F1–F4 | Audio: Klinke/HDMI/BT/Alle |
| R | Neustart |
| Q | ipod_ctrl beenden |

### File-Trigger (`/tmp/ipod_cmd`)

```bash
echo "up"           > /tmp/ipod_cmd   # Navigation
echo "down"         > /tmp/ipod_cmd
echo "enter"        > /tmp/ipod_cmd
echo "back"         > /tmp/ipod_cmd
echo "cat:0"        > /tmp/ipod_cmd   # Musik
echo "cat:1"        > /tmp/ipod_cmd   # WiFi
echo "cat:2"        > /tmp/ipod_cmd   # Bluetooth
echo "cat:3"        > /tmp/ipod_cmd   # System
echo "wifi_on"      > /tmp/ipod_cmd   # WiFi ein
echo "wifi_off"     > /tmp/ipod_cmd   # WiFi aus
echo "bt_on"        > /tmp/ipod_cmd   # BT ein
echo "bt_off"       > /tmp/ipod_cmd   # BT aus
echo "audio_klinke" > /tmp/ipod_cmd   # Klinke
echo "audio_hdmi"   > /tmp/ipod_cmd   # HDMI
echo "audio_bt"     > /tmp/ipod_cmd   # Bluetooth
echo "audio_all"    > /tmp/ipod_cmd   # Alle kombiniert
echo "spotify_on"   > /tmp/ipod_cmd   # Spotify starten
echo "spotify_off"  > /tmp/ipod_cmd   # Spotify stoppen
echo "radio_stop"   > /tmp/ipod_cmd   # Radio stoppen
echo "reboot"       > /tmp/ipod_cmd   # Neustart
echo "shutdown"     > /tmp/ipod_cmd   # Ausschalten
```

---

## Webradio Stationen konfigurieren

Stationen in `pidrive/config/stations.json` bearbeiten:

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

## MP3 Bibliothek

MP3-Dateien nach `~/Musik` kopieren (oder Pfad in `settings.json` ändern):

```bash
# Pfad ändern
nano ~/pidrive/pidrive/config/settings.json
# "music_path": "/mnt/usb/Musik"
```

Unterstützte Formate: MP3, M4A, FLAC, OGG, WAV

Album-Art wird automatisch aus ID3-Tags gelesen (APIC-Frame).

---

## /boot/config.txt

Wichtige Einstellungen:

```ini
# PFLICHT: Auto-Detect deaktivieren (blockiert SPI Display!)
camera_auto_detect=0
display_auto_detect=0

# Display-Treiber
dtoverlay=tft35a:rotate=90

# HDMI für fbcp
hdmi_force_hotplug=1
hdmi_group=2
hdmi_mode=87
hdmi_cvt=480 320 60 6 0 0 0
```

---

## Bekannte Probleme

| Problem | Lösung |
|---|---|
| Display dunkel nach Reboot | `sudo systemctl start ipod` |
| Spotify nicht sichtbar in App | `LIBRESPOT_DISABLE_CREDENTIAL_CACHE` auskommentieren |
| pygame border_radius Fehler | pygame 1.9.6 — bereits behoben |
| GIL-Fehler | kein threading verwendet — bereits behoben |
| WLAN nach Reboot aus | rfkill-unblock.service aktivieren |
| Touch reagiert nicht | Hardware-Defekt möglich; GPIO-Buttons als Alternative |

---

## Abhängigkeiten

```bash
# System
sudo apt install python3-pygame python3-pip git mpv \
  avahi-daemon bluez pulseaudio pulseaudio-module-bluetooth

# Python
pip3 install mutagen
```

---

## Lizenz

GPL-v3 — siehe [LICENSE](LICENSE)

---

## Roadmap

- [ ] DAB+ Support (RTL-SDR + welle.io)
- [ ] FM Radio (RTL-SDR)
- [ ] GPIO-Button Navigation (Key1-3)
- [ ] BMW iDrive ESP32 Integration
- [ ] USB-Tethering Autostart
- [ ] OTA Updates via GitHub
- [ ] Hotspot-Modus

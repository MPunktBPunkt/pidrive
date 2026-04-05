# PiDrive 🚗🎵

Raspberry Pi Car Infotainment — Spotify Connect, Webradio, MP3 Bibliothek für BMW iDrive und ähnliche Systeme.

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
curl -sL https://raw.githubusercontent.com/MPunktBPunkt/pidrive/main/install.sh | sudo bash
```

### Manuelle Installation

```bash
git clone https://github.com/MPunktBPunkt/pidrive ~/pidrive
cd ~/pidrive
sudo bash setup_pidrive.sh
```

### Display-Treiber einrichten

```bash
git clone https://github.com/goodtft/LCD-show ~/LCD-show
cd ~/LCD-show
sudo ./LCD35-show
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
cd ~/pidrive
git pull
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
│   │   ├── dabfm.py     # DAB+/FM (In Planung)
│   │   ├── wifi.py      # WiFi Steuerung
│   │   ├── bluetooth.py # Bluetooth Kopplung & Audio
│   │   ├── audio.py     # Audioausgang Steuerung
│   │   └── system.py    # System-Info, Neustart, etc.
│   └── config/
│       ├── stations.json   # Webradio-Stationen
│       └── settings.json   # Einstellungen
├── pidrive_ctrl.py      # SSH Tastatur-Steuerung
├── install.sh           # GitHub Schnellinstallation
├── setup_pidrive.sh     # Vollständiges Setup-Script
├── config.txt.example   # Beispiel /boot/config.txt
└── README.md
```

---

## Menü-Struktur

```
PiDrive
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

### USB-Tastatur direkt am Pi

Eine USB-Tastatur direkt am Pi anschliessen — funktioniert sofort:

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

Gleiche Tasten wie USB-Tastatur + `1`–`4` für direkte Kategoriewahl, `R` für Neustart, `Q` zum Beenden.

### File-Trigger (`/tmp/pidrive_cmd`)

```bash
echo "up"           > /tmp/pidrive_cmd   # Navigation
echo "down"         > /tmp/pidrive_cmd
echo "enter"        > /tmp/pidrive_cmd
echo "back"         > /tmp/pidrive_cmd
echo "cat:0"        > /tmp/pidrive_cmd   # Musik
echo "cat:1"        > /tmp/pidrive_cmd   # WiFi
echo "cat:2"        > /tmp/pidrive_cmd   # Bluetooth
echo "cat:3"        > /tmp/pidrive_cmd   # System
echo "wifi_on"      > /tmp/pidrive_cmd   # WiFi ein
echo "wifi_off"     > /tmp/pidrive_cmd   # WiFi aus
echo "bt_on"        > /tmp/pidrive_cmd   # Bluetooth ein
echo "bt_off"       > /tmp/pidrive_cmd   # Bluetooth aus
echo "audio_klinke" > /tmp/pidrive_cmd   # Klinke
echo "audio_hdmi"   > /tmp/pidrive_cmd   # HDMI
echo "audio_bt"     > /tmp/pidrive_cmd   # Bluetooth
echo "audio_all"    > /tmp/pidrive_cmd   # Alle kombiniert
echo "spotify_on"   > /tmp/pidrive_cmd   # Spotify starten
echo "spotify_off"  > /tmp/pidrive_cmd   # Spotify stoppen
echo "radio_stop"   > /tmp/pidrive_cmd   # Radio stoppen
echo "reboot"       > /tmp/pidrive_cmd   # Neustart
echo "shutdown"     > /tmp/pidrive_cmd   # Ausschalten
```

---

## Logging & Debugging

PiDrive schreibt alle Ereignisse in eine rotierende Logdatei (max 512 KB, 2 Backups):

```bash
# Live-Log verfolgen
tail -f /var/log/pidrive/pidrive.log

# Service-Log (journald)
journalctl -u pidrive -f

# Letzte 50 Zeilen
journalctl -u pidrive -n 50 --no-pager

# Nur Fehler
journalctl -u pidrive -p err

# Menü-Navigation verfolgen
grep "MENU" /var/log/pidrive/pidrive.log

# Trigger-Befehle verfolgen
grep "TRIGGER" /var/log/pidrive/pidrive.log

# Aktionen verfolgen
grep "ACTION" /var/log/pidrive/pidrive.log
```

**Beispiel-Log:**
```
2026-04-05 11:23:01 [INFO] PiDrive gestartet
2026-04-05 11:23:02 [INFO] STATUS  wifi=True bt=False spotify=True audio=Klinke
2026-04-05 11:23:15 [INFO] MENU  Musik -> WiFi | WiFi
2026-04-05 11:23:18 [INFO] TRIGGER  wifi_off
2026-04-05 11:23:18 [INFO] ACTION  WiFi: ausschalten
2026-04-05 11:23:22 [INFO] TRIGGER  cat:0
2026-04-05 11:23:22 [INFO] MENU  -> Kategorie: Musik
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
nano ~/pidrive/pidrive/config/settings.json
# "music_path": "/mnt/usb/Musik"
```

Unterstützte Formate: MP3, M4A, FLAC, OGG, WAV.
Album-Art wird automatisch aus ID3-Tags gelesen (APIC-Frame).

---

## /boot/config.txt

Wichtige Einstellungen (vollständig in `config.txt.example`):

```ini
# PFLICHT: Auto-Detect deaktivieren (blockiert SPI Display!)
camera_auto_detect=0
display_auto_detect=0

# Display-Treiber (wird von LCD35-show gesetzt)
dtoverlay=tft35a:rotate=90

# HDMI für fbcp
hdmi_force_hotplug=1
hdmi_group=2
hdmi_mode=87
hdmi_cvt=480 320 60 6 0 0 0
hdmi_drive=2
```

---

## Bekannte Probleme

| Problem | Lösung |
|---|---|
| Display dunkel nach Reboot | `sudo systemctl start pidrive` |
| Spotify nicht sichtbar in App | `LIBRESPOT_DISABLE_CREDENTIAL_CACHE` auskommentieren |
| pygame border_radius Fehler | pygame 1.9.6 — bereits behoben |
| WLAN nach Reboot aus | rfkill-unblock.service aktivieren |
| Touch reagiert nicht | Hardware-Defekt möglich; USB-Tastatur als Alternative |
| Raspotify startet ohne Internet | `network-online.target` in Service setzen |

---

## Abhängigkeiten

```bash
# System
sudo apt install python3-pygame python3-pip git mpv \
  avahi-daemon bluez pulseaudio pulseaudio-module-bluetooth \
  rfkill wpasupplicant dhcpcd5

# Python
pip3 install mutagen --break-system-packages
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
- [ ] Hotspot-Modus
- [ ] OTA Updates via GitHub

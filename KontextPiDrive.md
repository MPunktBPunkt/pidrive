# PiDrive — Kontext & Projektdokumentation v0.3.2

## Projektbeschreibung

**PiDrive** ist ein Raspberry Pi-basiertes Car-Infotainment-System. Es emuliert einen iPod gegenüber dem BMW iDrive (oder ähnlichen Fahrzeug-Systemen) und zeigt eine eigene Menüoberfläche auf einem TFT-Display.

### GitHub Repository
```
https://github.com/MPunktBPunkt/pidrive
```

**Schnellinstallation:**
```bash
curl -sL https://raw.githubusercontent.com/MPunktBPunkt/pidrive/main/install.sh | sudo bash
```

**Update:**
```bash
cd ~/pidrive && git pull && sudo systemctl restart pidrive
# oder im Menü: System -> Update -> Update installieren
```

---

## Hardware

| Komponente | Details |
|---|---|
| Raspberry Pi | Pi 3 Model B Rev 1.2, Pi 4 geplant |
| Display | Joy-IT RB-TFT3.5, 480x320, XPT2046 Touch |
| Verbindung | SPI (erste 26 GPIO-Pins) |
| Touch | ADS7846/XPT2046 — Hardware-Defekt am Testgeraet |
| RTL-SDR | Fuer DAB+ und FM Radio |

### GPIO-Pinbelegung (Joy-IT RB-TFT3.5)

| Funktion | GPIO | Pin |
|---|---|---|
| DC | GPIO 24 | 18 |
| Reset | GPIO 25 | 22 |
| PENIRQ (Touch) | GPIO 17 | 11 |
| Key 1 | GPIO 23 | 16 |
| Key 2 | GPIO 24 | 18 |
| Key 3 | GPIO 25 | 22 |
| Backlight | GPIO 18 | 12 |

---

## Software-Stack

### Betriebssystem
- Raspbian Bullseye (11), 32-Bit (armhf)
- Kernel: 6.18.20-v7+

### Installierte Pakete

```bash
sudo apt install python3-pygame python3-pip git mpv \
  avahi-utils avahi-daemon evtest fbset \
  bluetooth bluez pulseaudio pulseaudio-module-bluetooth \
  rfkill wpasupplicant dhcpcd5 rtl-sdr sox -y

pip3 install mutagen --break-system-packages

# Optional fuer DAB+
sudo apt install welle.io
```

### Display-Treiber

```bash
git clone https://github.com/goodtft/LCD-show.git
chmod -R 755 LCD-show
cd LCD-show/
sudo ./LCD35-show
```

---

## Projektstruktur

```
~/pidrive/
├── README.md
├── LICENSE                  (GPL-v3)
├── .gitignore
├── install.sh               (Schnellinstallation)
├── setup_pidrive.sh         (vollstaendiges Setup-Script)
├── pidrive_ctrl.py          (SSH Tastatur-Steuerung)
├── config.txt.example
├── KontextPiDrive.md
├── systemd/
│   └── pidrive.service      (Systemd Service-Datei)
└── pidrive/
    ├── main.py
    ├── ui.py
    ├── status.py
    ├── trigger.py
    ├── log.py
    ├── VERSION              (aktuell: 0.3.6)
    ├── config/
    │   ├── stations.json    (Webradio)
    │   ├── dab_stations.json (DAB+ nach Scan)
    │   ├── fm_stations.json  (FM Sender)
    │   └── settings.json
    └── modules/
        ├── musik.py
        ├── webradio.py
        ├── library.py
        ├── dab.py           (DAB+ mit welle.io)
        ├── fm.py            (FM mit rtl_fm)
        ├── wifi.py
        ├── bluetooth.py
        ├── audio.py
        ├── system.py
        └── update.py        (OTA Updates)
```

---

## /boot/config.txt

```ini
dtparam=audio=on
camera_auto_detect=0   # PFLICHT: blockiert sonst SPI Display!
display_auto_detect=0  # PFLICHT
max_framebuffers=2
disable_overscan=1

[pi4]
arm_boost=1

[all]
dtparam=spi=on
dtparam=i2c_arm=on
enable_uart=1
dtoverlay=tft35a:rotate=90
hdmi_force_hotplug=1
hdmi_group=2
hdmi_mode=87
hdmi_cvt=480 320 60 6 0 0 0
hdmi_drive=2
```

---

## Framebuffer-Architektur

```
HDMI Framebuffer (fb0, 640x480)  <- PiDrive zeichnet hierauf
        |
    fbcp (Dienst)
        |
SPI Display Framebuffer (fb1, 480x320)
        |
    Joy-IT TFT3.5
```

### Rotation im Script

```python
virt    = pygame.Surface((320, 480))      # Virtueller Canvas
real    = pygame.display.set_mode((640, 480))  # Framebuffer
rotated = pygame.transform.rotate(virt, 90)    # 480x320
scaled  = pygame.transform.scale(rotated, (640, 480))
real.blit(scaled, (0, 0))
pygame.display.flip()
```

---

## Systemdienste

### pidrive.service (`systemd/pidrive.service`)

```ini
[Unit]
Description=PiDrive - Car Infotainment
After=multi-user.target rc-local.service

[Service]
Type=simple
User=pi
Environment=SDL_FBDEV=/dev/fb0
Environment=SDL_VIDEODRIVER=fbcon
Environment=SDL_NOMOUSE=1
WorkingDirectory=/home/pi/pidrive/pidrive
ExecStartPre=/bin/sleep 5
ExecStart=/usr/bin/python3 /home/pi/pidrive/pidrive/main.py
Restart=always
RestartSec=5
StandardInput=tty
StandardOutput=null             # Kein Konsolen-Overlay auf Display
StandardError=journal           # Fehler weiterhin in journald
TTYPath=/dev/tty3
TTYReset=yes
TTYVHangup=yes

[Install]
WantedBy=multi-user.target
```

### Weitere Services

| Service | Zweck |
|---|---|
| rfkill-unblock.service | WiFi + BT beim Boot entsperren |
| raspotify.service | Spotify Connect |

---

## Spotify OAuth (einmalig)

```bash
sudo systemctl stop raspotify
sudo mkdir -p /var/cache/raspotify

# SSH-Tunnel auf PC (ZUERST!):
ssh -L 5588:127.0.0.1:5588 pi@<IP> -N

/usr/bin/librespot --name "PiDrive" --enable-oauth \
  --system-cache /var/cache/raspotify
```

### raspotify Konfiguration (`/etc/raspotify/conf`)

```bash
LIBRESPOT_NAME="PiDrive"   # Muss PiDrive sein, nicht FakeIpod!
LIBRESPOT_BITRATE=320
LIBRESPOT_DISABLE_AUDIO_CACHE=
#LIBRESPOT_DISABLE_CREDENTIAL_CACHE=   # AUSKOMMENTIERT - sonst kein Login!
LIBRESPOT_BACKEND=alsa
LIBRESPOT_DEVICE=hw:1,0
LIBRESPOT_ENABLE_VOLUME_NORMALISATION=
LIBRESPOT_SYSTEM_CACHE=/var/cache/raspotify
LIBRESPOT_ONEVENT=/usr/local/bin/spotify_event.sh
```

### Timing-Fix (`/lib/systemd/system/raspotify.service`)

```ini
Wants=network-online.target sound.target
After=network-online.target sound.target avahi-daemon.service
```

---

## Spotify Track-Anzeige

`/usr/local/bin/spotify_event.sh` schreibt bei Wiedergabe:
```
track_changed|Titel|Artist|Album  ->  /tmp/spotify_status
```

`status.py` liest `/tmp/spotify_status` alle 6 Sekunden.

---

## DAB+ (RTL-SDR + welle.io)

### Voraussetzungen
- RTL-SDR Stick angeschlossen (USB)
- `welle-cli` installiert (`sudo apt install welle.io`)

### Sendersuche
- Menü: Musik → DAB+ → Sendersuche
- Scannt alle Band-III Kanaele (5A - 13F)
- Ergebnis gespeichert in `config/dab_stations.json`
- Beim naechsten Start sofort verfuegbar

### Wiedergabe
- `welle-cli | mpv` Pipeline
- Automatisch mit gespeicherter Senderliste

---

## FM Radio (RTL-SDR + rtl_fm)

### Voraussetzungen
- RTL-SDR Stick angeschlossen
- `rtl-sdr` Paket installiert (`sudo apt install rtl-sdr`)

### Stationen
- Voreingestellt in `config/fm_stations.json`
- Manuelle Frequenzeingabe: ↑↓ fuer 0.1 MHz, ←→ fuer 1.0 MHz
- Neue Stationen speicherbar

### Wiedergabe
- `rtl_fm | mpv` Pipeline, 200 kHz Bandbreite, WFM Demodulation

---

## Logging

```bash
# Live verfolgen
tail -f /var/log/pidrive/pidrive.log

# Service-Journal
journalctl -u pidrive -f

# Spezifisch filtern
grep "MENU\|TRIGGER\|ACTION\|ERROR" /var/log/pidrive/pidrive.log
```

Log-Rotation: max 512 KB pro Datei, 2 Backups (max 1.5 MB gesamt).

---

## OTA Update

```bash
# Manuell
cd ~/pidrive && git pull && sudo systemctl restart pidrive

# Im Menue
# System -> Update -> Auf Updates pruefen
# System -> Update -> Update installieren
```

Versions-Check via:
```
https://raw.githubusercontent.com/MPunktBPunkt/pidrive/main/pidrive/VERSION
```

---

## Menü-Struktur

```
PiDrive
|-- Musik
|   |-- Spotify (Toggle + Track-Anzeige)
|   |-- Wiedergabe (Titel | Artist | Album)
|   |-- Bibliothek (MP3 mit Album-Art)
|   |-- Webradio (stations.json)
|   |-- DAB+ (RTL-SDR, dab_stations.json)
|   +-- FM Radio (RTL-SDR, fm_stations.json)
|-- WiFi
|   |-- WiFi An/Aus
|   |-- Verbunden mit (SSID)
|   +-- Netzwerke scannen
|-- Bluetooth
|   |-- Bluetooth An/Aus
|   |-- Geraete scannen & koppeln
|   |-- Als Audio-Ausgang setzen
|   +-- Alle trennen
+-- System
    |-- Audioausgang (Klinke/HDMI/BT/Alle)
    |-- Lauter / Leiser
    |-- IP Adresse
    |-- Hostname
    |-- System-Info (CPU-Temp, Uptime)
    |-- Version
    |-- Neustart / Ausschalten
    +-- Update (OTA via GitHub)
```

---

## File-Trigger (`/tmp/pidrive_cmd`)

```bash
echo "up/down/enter/back/left/right" > /tmp/pidrive_cmd
echo "cat:0/1/2/3"                  > /tmp/pidrive_cmd
echo "wifi_on/wifi_off"             > /tmp/pidrive_cmd
echo "bt_on/bt_off"                 > /tmp/pidrive_cmd
echo "audio_klinke/hdmi/bt/all"     > /tmp/pidrive_cmd
echo "spotify_on/spotify_off"       > /tmp/pidrive_cmd
echo "radio_stop/library_stop"      > /tmp/pidrive_cmd
echo "reboot/shutdown"              > /tmp/pidrive_cmd
```

---

## Bekannte Probleme & Loesungen

| Problem | Ursache | Loesung |
|---|---|---|
| Display zeigt nichts | camera/display_auto_detect=1 | In config.txt auf 0 |
| pygame border_radius | pygame 1.9.6 | draw.rect() ohne border_radius |
| GIL-Fehler | pygame 1.9.6 + threading | Kein threading, Popen |
| Raspotify kein Login | DISABLE_CREDENTIAL_CACHE aktiv | Zeile auskommentieren |
| Raspotify zu frueh | network.target | network-online.target |
| WLAN nach Reboot aus | rfkill | rfkill-unblock.service |
| Touch reagiert nicht | Hardware-Defekt | USB-Tastatur |
| Tastatur reagiert nicht | falscher TTY | chvt 3 (im Service) |
| Konsole ueberlagert Display | stdout auf tty3 | StandardOutput=null im Service |
| PiDrive Restart-Schleife | tty3 nicht aktiv | After=rc-local.service + manuell: sudo chvt 3 && systemctl restart pidrive |
| Spotify spielt nicht | PulseAudio nicht erreichbar | LIBRESPOT_BACKEND=alsa + DEVICE=hw:1,0 |
| Spotify zeigt FakeIpod | alter Name in conf | LIBRESPOT_NAME="PiDrive"   # Muss PiDrive sein, nicht FakeIpod! |
| Menue-Text ueberlaeuft | pygame Surface | eigene Surface (_draw_left) |
| DAB+ kein Ton | welle-cli fehlt | sudo apt install welle.io |
| FM kein Ton | rtl_fm fehlt | sudo apt install rtl-sdr |

---

## Changelog

### v0.3.6 (aktuell)
- UI-Fix: eigene Surface fuer linke Spalte (kein Text-Ueberlauf mehr)
- USB-Tastatur: chvt 3 automatisch via Service
- pidrive.service im systemd/ Ordner des Repos
- install.sh kopiert Service-Datei aus Repo

### v0.3.0
- DAB+ Radio (welle.io, Sendersuche & Speicherung)
- FM Radio (rtl_fm, manuelle Frequenzeingabe)
- OTA Updates aus dem Menue
- Logging-Modul (rotierend)

### v0.2.0
- Modulare Struktur
- Spotify Track-Anzeige
- Webradio, MP3 Bibliothek mit Album-Art
- Bluetooth Audio-Ausgang

---

## Roadmap

- [ ] GPIO-Buttons (Key1=GPIO23, Key2=GPIO24, Key3=GPIO25)
- [ ] BMW iDrive ESP32 Integration
- [ ] USB-Tethering Autostart
- [ ] Hotspot-Modus
- [ ] DAB+ Programminfo (RDS-aehnliche Anzeige)
- [ ] FM RDS Text-Anzeige
- [ ] Equalizer

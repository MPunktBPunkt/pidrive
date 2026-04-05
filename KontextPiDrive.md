# PiDrive — Kontext & Projektdokumentation

## Projektbeschreibung

**PiDrive** ist ein Raspberry Pi-basiertes Car-Infotainment-System. Es emuliert einen iPod gegenüber dem BMW iDrive (oder ähnlichen Fahrzeug-Systemen) über den iDrive-iPod-Adapter und zeigt gleichzeitig eine eigene Menüoberfläche auf einem kleinen TFT-Display.

### Grundidee

Das Fahrzeug kommuniziert über das iPod-Protokoll mit dem Pi. Der Pi stellt sich als iPod vor und empfängt Steuerbefehle vom iDrive (Vor/Zurück, Menü). Diese Befehle werden im Pi interpretiert und lösen Aktionen aus über den File-Trigger `/tmp/pidrive_cmd`.

### Sinn des Projekts

Ein vollwertiges Infotainment-System auf Basis eines Raspberry Pi, das:
- Spotify Connect Lautsprecher im Auto darstellt
- Über das originale iDrive bedienbar ist
- Ein eigenes Display mit Menüoberfläche hat
- Webradio, MP3-Bibliothek und DAB+/FM (geplant) unterstützt
- Im Auto über USB-Tethering (Handy-Internet) verbunden ist

### GitHub Repository

```
https://github.com/DEIN-USER/pidrive
```

**Schnellinstallation:**
```bash
curl -sL https://raw.githubusercontent.com/DEIN-USER/pidrive/main/install.sh | sudo bash
```

**Update:**
```bash
cd ~/pidrive && git pull && sudo systemctl restart pidrive
```

---

## Hardware

| Komponente | Details |
|---|---|
| **Raspberry Pi** | Pi 3 Model B Rev 1.2 (Testgerät), Pi 4 geplant |
| **Display** | Joy-IT RB-TFT3.5, 480×320 Pixel, XPT2046 Touch Controller |
| **Verbindung Display** | SPI (GPIO Header, erste 26 Pins) |
| **Touch Controller** | ADS7846/XPT2046 — vermutlich Hardware-Defekt am Testgerät |

### Display GPIO-Pinbelegung (Joy-IT RB-TFT3.5 V3)

| Funktion | GPIO | Pin |
|---|---|---|
| DC (Data/Control) | GPIO 24 | Pin 18 |
| Reset | GPIO 25 | Pin 22 |
| PENIRQ (Touch) | GPIO 17 | Pin 11 |
| Key 1 | GPIO 23 | Pin 16 |
| Key 2 | GPIO 24 | Pin 18 |
| Key 3 | GPIO 25 | Pin 22 |
| Hintergrundbeleuchtung | GPIO 18 | Pin 12 |

---

## Software-Stack

### Betriebssystem

- **Raspbian Bullseye** (11) — 32-Bit (armhf)
- Upgrade von Buster (10) durchgeführt
- Kernel: 6.18.20-v7+

### Installierte Pakete

```bash
sudo apt install python3-pygame python3-pip git mpv \
  avahi-utils avahi-daemon evtest fbset \
  bluetooth bluez pulseaudio pulseaudio-module-bluetooth \
  rfkill wpasupplicant dhcpcd5 -y

pip3 install mutagen --break-system-packages
```

| Paket | Zweck |
|---|---|
| python3-pygame 1.9.6 | UI-Rendering auf Framebuffer |
| python3-evdev | Touch-Input (evdev) |
| mpv | Webradio + MP3 Wiedergabe |
| mutagen | MP3 ID3-Tags + Album-Art lesen |
| avahi-utils | mDNS/Zeroconf (Spotify Discovery) |
| fbset | Framebuffer-Auflösung prüfen |

### Display-Treiber

**LCD-show von goodtft** (empfohlen von Joy-IT):

```bash
git clone https://github.com/goodtft/LCD-show.git
chmod -R 755 LCD-show
cd LCD-show/
sudo ./LCD35-show
```

Dieser Treiber installiert `fb_ili9486`, konfiguriert `fbcp` als Systemdienst,
setzt `/boot/config.txt` automatisch und aktiviert ADS7846 Touch-Treiber.

### Raspotify (Spotify Connect)

```bash
curl -sL https://dtcooper.github.io/raspotify/install.sh | sh
```

---

## Projektstruktur

```
~/pidrive/
├── README.md
├── LICENSE                  (GPL-v3)
├── .gitignore
├── install.sh               (curl | bash Schnellinstallation)
├── setup_pidrive.sh         (vollständiges Setup-Script)
├── pidrive_ctrl.py          (SSH Tastatur-Steuerung)
├── config.txt.example
├── KontextPiDrive.md        (diese Datei)
└── pidrive/
    ├── main.py              (Hauptprogramm & Main-Loop)
    ├── ui.py                (UI-Basisklassen)
    ├── status.py            (System-Status Cache)
    ├── trigger.py           (File-Trigger Handler)
    ├── VERSION
    ├── config/
    │   ├── stations.json    (Webradio-Stationen)
    │   └── settings.json    (Einstellungen)
    └── modules/
        ├── musik.py         (Spotify + Track-Anzeige)
        ├── webradio.py      (Streaming via mpv)
        ├── library.py       (MP3 + Album-Art)
        ├── dabfm.py         (DAB+/FM Platzhalter)
        ├── wifi.py          (WiFi Steuerung)
        ├── bluetooth.py     (BT + Audio-Ausgang)
        ├── audio.py         (Audioausgang)
        └── system.py        (System-Info, Neustart)
```

---

## /boot/config.txt

```ini
dtparam=audio=on

# PFLICHT: Auto-Detect deaktivieren (blockiert SPI Display!)
camera_auto_detect=0
display_auto_detect=0

max_framebuffers=2
disable_overscan=1

[pi4]
arm_boost=1

[all]
dtparam=spi=on
dtparam=i2c_arm=on
enable_uart=1

# Joy-IT TFT3.5 Display Treiber (beinhaltet Touch-Overlay)
dtoverlay=tft35a:rotate=90

# HDMI fuer fbcp Spiegelung
hdmi_force_hotplug=1
hdmi_group=2
hdmi_mode=87
hdmi_cvt=480 320 60 6 0 0 0
hdmi_drive=2
```

**Wichtige Erkenntnisse:**
- `camera_auto_detect=1` und `display_auto_detect=1` blockieren den SPI-Display!
- `dtoverlay=tft35a:rotate=90` enthält den ADS7846 Touch-Treiber
- `dtoverlay=vc4-kms-v3d` / `vc4-fkms-v3d` muss deaktiviert sein

---

## Framebuffer-Architektur

```
HDMI Framebuffer (fb0)  <- PiDrive zeichnet hierauf
640x480 (HDMI-Aufloesung)
        |
    fbcp (Dienst, von LCD-show installiert)
        |
SPI Display Framebuffer (fb1)
480x320 (Display-Aufloesung)
        |
    Joy-IT TFT3.5
```

### Rotation und Skalierung im Script

```python
# Virtueller Surface: 320x480 (Hochformat)
virt = pygame.Surface((320, 480))
# Echter Framebuffer: 640x480
real = pygame.display.set_mode((640, 480))
# Rotation 90 Grad -> 480x320, dann skalieren auf 640x480
rotated = pygame.transform.rotate(virt, 90)
scaled  = pygame.transform.scale(rotated, (640, 480))
real.blit(scaled, (0, 0))
```

---

## Systemdienste

### pidrive.service

```ini
[Unit]
Description=PiDrive - Car Infotainment
After=multi-user.target

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
TTYPath=/dev/tty3
TTYReset=yes
TTYVHangup=yes

[Install]
WantedBy=multi-user.target
```

### raspotify Konfiguration

Wichtige Einstellungen in `/etc/raspotify/conf`:

```bash
LIBRESPOT_NAME="PiDrive"
LIBRESPOT_BITRATE=320
LIBRESPOT_DISABLE_AUDIO_CACHE=
# PFLICHT auskommentiert: sonst kein Login nach Reboot!
#LIBRESPOT_DISABLE_CREDENTIAL_CACHE=
LIBRESPOT_ENABLE_VOLUME_NORMALISATION=
LIBRESPOT_SYSTEM_CACHE=/var/cache/raspotify
LIBRESPOT_ONEVENT=/usr/local/bin/spotify_event.sh
```

**Timing-Fix** in `/lib/systemd/system/raspotify.service`:
```ini
Wants=network-online.target sound.target
After=network-online.target sound.target avahi-daemon.service
```

```bash
sudo systemctl enable systemd-networkd-wait-online.service
```

### Weitere Services

| Service | Zweck |
|---|---|
| `rfkill-unblock.service` | WiFi + BT beim Boot entsperren |
| `wlan-autostart.service` | WLAN automatisch verbinden |
| `raspotify.service` | Spotify Connect |

---

## Spotify OAuth-Einrichtung (einmalig)

```bash
sudo systemctl stop raspotify
sudo mkdir -p /var/cache/raspotify

# SSH-Tunnel auf PC (ZUERST in neuem Terminal!):
# ssh -L 5588:127.0.0.1:5588 pi@<PI-IP> -N

# OAuth starten
/usr/bin/librespot --name "PiDrive" --enable-oauth \
  --system-cache /var/cache/raspotify
```

URL im Browser oeffnen, Spotify Login, Token wird gespeichert.

```bash
sudo systemctl start raspotify
avahi-browse -a | grep -i spotify  # -> PiDrive sollte erscheinen
```

---

## Spotify Track-Anzeige

Via `/usr/local/bin/spotify_event.sh`:

```bash
#!/bin/bash
if [ "$PLAYER_EVENT" = "track_changed" ] || [ "$PLAYER_EVENT" = "playing" ]; then
    echo "${PLAYER_EVENT}|${NAME}|${ARTISTS}|${ALBUM}" > /tmp/spotify_status
fi
```

PiDrive liest `/tmp/spotify_status` (status.py) und zeigt Titel/Artist/Album an.

---

## Menü-Struktur

```
PiDrive
|-- Musik
|   |-- Spotify (Toggle + Track-Anzeige)
|   |-- Wiedergabe (Titel | Artist | Album)
|   |-- Bibliothek (MP3 mit Album-Art)
|   |-- Webradio (konfigurierbare Stationen)
|   +-- DAB+ / FM (In Planung)
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
    |-- Neustart (mit Bestaetigung)
    +-- Ausschalten (mit Bestaetigung)
```

---

## File-Trigger (`/tmp/pidrive_cmd`)

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

## Audio-Architektur

```
Raspberry Pi 3B Audio
|-- HDMI (hw:0,0) -> Karte b1
|-- Klinke 3.5mm (hw:1,0) -> Karte Headphones
+-- Bluetooth (PulseAudio bluez Sink)
        |
    PulseAudio
        |-- Einzelausgang: Klinke / HDMI / BT
        +-- Combined Sink: Alle gleichzeitig
```

---

## Konsolen-Unterdrückung

Damit TTY nicht ueber das Display laeuft:

```bash
echo 0 > /sys/class/vtconsole/vtcon1/bind
echo 0 > /sys/class/graphics/fbcon/cursor_blink
con2fbmap 1 1
```

In `/etc/rc.local` vor `exit 0` fuer Autostart.

---

## Bekannte Probleme & Loesungen

| Problem | Ursache | Loesung |
|---|---|---|
| Display zeigt nichts | camera_auto_detect=1 | In config.txt auf 0 |
| pygame Unable to open console terminal | Ueber SSH gestartet | Als systemd Service auf tty3 |
| No overlays loaded | display_auto_detect=1 | Auf 0 setzen |
| pygame border_radius Fehler | pygame 1.9.6 | draw.rect() ohne border_radius |
| GIL-Fehler mit threading | pygame 1.9.6 + sudo | Kein threading, Popen statt Thread |
| Raspotify verbindet nicht | DISABLE_CREDENTIAL_CACHE aktiv | Zeile auskommentieren |
| Raspotify startet zu frueh | network.target | network-online.target |
| WLAN nach Reboot aus | rfkill blockiert | rfkill-unblock.service |
| Touch reagiert nicht | ADS7846 Hardware-Defekt | GPIO-Buttons als Alternative |
| Menue zu klein | HDMI 640x480 != Display | pygame.transform.scale auf 640x480 |
| Spotify nicht in App sichtbar | Kein Auth-Token | OAuth einrichten |

---

## Roadmap

- [ ] DAB+ Support (RTL-SDR + welle.io)
- [ ] FM Radio (RTL-SDR)
- [ ] GPIO-Button Navigation (Key1=GPIO23, Key2=GPIO24, Key3=GPIO25)
- [ ] BMW iDrive ESP32 Integration (handle_track() Trigger)
- [ ] USB-Tethering Autostart
- [ ] Hotspot-Modus
- [ ] OTA Updates via git pull
- [ ] Lautstaerke-Anzeige im Display

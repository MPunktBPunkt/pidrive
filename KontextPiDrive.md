# PiDrive — Kontext & Projektdokumentation v0.6.2

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
curl -sL https://raw.githubusercontent.com/MPunktBPunkt/pidrive/main/install.sh | sudo bash
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
├── install.sh               (Schnellinstallation, 10 Schritte)
├── setup_pidrive.sh         (vollstaendiges Setup-Script)
├── pidrive_ctrl.py          (SSH Tastatur-Steuerung)
├── config.txt.example
├── KontextPiDrive.md
├── systemd/
│   └── pidrive.service      (User=root, launcher.py)
└── pidrive/
    ├── launcher.py          (TTY-Setup: setsid + TIOCSCTTY, startet main.py)
    ├── main.py
    ├── ui.py
    ├── status.py
    ├── trigger.py
    ├── log.py
    ├── VERSION              (aktuell: 0.6.2)
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
        ├── scanner.py       (PMR446, Freenet, LPD433, VHF, UHF)
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

## PAMName=login — Der entscheidende Fix (v0.6.2)

SDL setzt intern VT_SETMODE(VT_PROCESS). Der Kernel prueft dabei:
"Ist dieser Prozess Session-Leader des aktiven VT?"

Ohne PAMName=login im Service:
- systemd erzeugt KEINE logind-Session
- Kernel betrachtet Prozess nicht als Session-Leader
- VT_SETMODE(VT_PROCESS) schlaegt fehl
- Kernel sendet SIGHUP → Service stirbt → Bootschleife

Mit PAMName=login:
- systemd erzeugt eine echte PAM/logind-Session auf VT3
- Prozess ist Session-Leader
- VT_SETMODE(VT_PROCESS) funktioniert
- kein SIGHUP, kein Haenger, Display zeigt Bild

Diagnose: loginctl zeigt jetzt eine Session auf tty3.

## SDL_AUDIODRIVER=dummy — Erklaerung

pygame.init() ruft intern SDL_Init(SDL_INIT_EVERYTHING) auf.
Ohne Einschraenkung versucht SDL dabei auch ALSA zu oeffnen (hw:1,0).
Wenn raspotify dieses Device bereits belegt, ruft SDL intern exit(0) auf —
komplett an Python vorbei, kein Exception, kein Log, Service stirbt mit "Succeeded".

Loesung (in main.py, vor allen Imports von pygame):
```python
os.environ["SDL_AUDIODRIVER"] = "dummy"
```
SDL nutzt dann einen Dummy-Audio-Treiber, pygame.init() laeuft vollstaendig durch.
Der echte Audio-Output (Spotify, Radio) laeuft weiter ueber mpv/ALSA — nicht ueber pygame.

## TIOCSCTTY — Warum wir es NICHT verwenden (v0.6.2)

SDL fbcon ruft intern VT_SETMODE(VT_PROCESS) auf. Wenn der Prozess ein
Controlling Terminal hat (gesetzt via TIOCSCTTY), sendet der Kernel SIGHUP
bei VT-Events (z.B. wenn VT3 in den Vordergrund kommt). SDL hat keinen
SIGHUP-Handler -> exit(0), kein Python-Fehler, kein Log-Eintrag.

Diagnose (v0.6.2):
- Test MIT TIOCSCTTY: "Aufgelegt" (= SIGHUP) nach pygame.init()
- Test OHNE TIOCSCTTY (stdin=/dev/null): pygame.init() OK
- Loesung: O_NOCTTY beim Oeffnen von tty3, kein setsid(), kein TIOCSCTTY
- chvt 3 reicht: VT3 muss nur foreground sein, nicht Controlling Terminal

## SDL_AUDIODRIVER=dummy — Erklaerung

pygame.init() ruft intern SDL_Init(SDL_INIT_EVERYTHING) auf.
Ohne Einschraenkung versucht SDL dabei auch ALSA zu oeffnen (hw:1,0).
Wenn raspotify dieses Device bereits belegt, ruft SDL intern exit(0) auf —
komplett an Python vorbei, kein Exception, kein Log, Service stirbt mit "Succeeded".

Loesung (in main.py, vor allen Imports von pygame):
```python
os.environ["SDL_AUDIODRIVER"] = "dummy"
```
SDL nutzt dann einen Dummy-Audio-Treiber, pygame.init() laeuft vollstaendig durch.
Der echte Audio-Output (Spotify, Radio) laeuft weiter ueber mpv/ALSA — nicht ueber pygame.

## Framebuffer-Architektur

```
HDMI Framebuffer (fb0, 640x480)  <- PiDrive zeichnet hierauf
        |
    fbcp (Dienst, gestartet via rc.local)
        |
SPI Display Framebuffer (fb1, 480x320)
        |
    Joy-IT TFT3.5
```

### Rotation im Script

```python
virt    = pygame.Surface((320, 480))
real    = pygame.display.set_mode((640, 480))
rotated = pygame.transform.rotate(virt, 90)
scaled  = pygame.transform.scale(rotated, (640, 480))
real.blit(scaled, (0, 0))
pygame.display.flip()
```

---

## /etc/rc.local (Boot-Reihenfolge)

```bash
#!/bin/sh -e
sleep 7          # Warten bis Display bereit
fbcp &           # Framebuffer Copy starten
echo 0 > /sys/class/vtconsole/vtcon1/bind
echo 0 > /sys/class/graphics/fbcon/cursor_blink
con2fbmap 1 1
chvt 3           # VT3 in den Vordergrund (fuer SDL/fbcon)
chmod 660 /dev/tty3   # PFLICHT: pi (tty-Gruppe) braucht Lesezugriff fuer launcher.py
exit 0
```

**Reihenfolge beim Boot:**
1. rc-local.service: `sleep 7` → `fbcp` → `chvt 3` → `chmod 660 /dev/tty3`
2. pidrive.service: `After=rc-local.service` wartet auf rc.local
3. `ExecStartPre=/bin/sleep 3` gibt tty3 Zeit zum Einrichten
4. launcher.py: Berechtigungs-Check → setsid → TIOCSCTTY → exec main.py

---

## udev-Regel (persistent, ueberschreibt kein Reboot)

```bash
# /etc/udev/rules.d/99-pidrive-tty.rules
KERNEL=="tty3", GROUP="tty", MODE="0660"
```

Wird von install.sh automatisch angelegt. Stellt sicher dass `/dev/tty3`
nach jedem Reboot 660-Berechtigungen hat, unabhaengig von rc.local.

---

## Systemdienste

### pidrive.service (`systemd/pidrive.service`)

```ini
[Unit]
Description=PiDrive - Car Infotainment
After=multi-user.target rc-local.service

[Service]
Type=simple
User=root
Environment=SDL_FBDEV=/dev/fb0
Environment=SDL_VIDEODRIVER=fbcon
Environment=SDL_NOMOUSE=1
WorkingDirectory=/home/pi/pidrive/pidrive
# PAMName=login erzeugt logind-Session -> kein ExecStartPre sleep noetig
ExecStart=/usr/bin/python3 /home/pi/pidrive/pidrive/launcher.py
Restart=always
RestartSec=5
StandardOutput=null
StandardError=journal
```

**Warum User=root:** launcher.py braucht root fuer setsid() und TIOCSCTTY.
Kein `StandardInput=tty`, kein TTYPath, kein HUP-Problem.

**Manueller Neustart:**
```bash
sudo systemctl restart pidrive
```

### launcher.py (NEU in v0.3.7)

Laeuft als erstes, richtet den TTY-Kontext ein:

1. Berechtigungs-Check: `/dev/fb0`, `/dev/tty3`, O_RDWR-Test, fgconsole
2. `chvt 3` — VT3 in den Vordergrund
3. `open("/dev/tty3", O_RDWR | O_NOCTTY)` — tty3 oeffnen
4. `os.setsid()` — neue Session (Prozess wird Session-Leader)
5. `fcntl.ioctl(fd, TIOCSCTTY, 1)` — tty3 als Controlling Terminal
6. `os.dup2(fd, 0)` — stdin auf tty3 (fuer USB-Tastatur)
7. `os.execv(python3, [python3, "main.py"])` — main.py erbt Kontext

Danach zeigt `open("/dev/tty")` auf `/dev/tty3` — genau was SDL/fbcon braucht.

Alle Schritte werden nach `/var/log/pidrive/pidrive.log` geloggt (Tag: `[LAUNCH/INFO]`).

### raspotify.service

```bash
LIBRESPOT_NAME="PiDrive"
LIBRESPOT_BITRATE=320
LIBRESPOT_DISABLE_AUDIO_CACHE=
#LIBRESPOT_DISABLE_CREDENTIAL_CACHE=   # AUSKOMMENTIERT - sonst kein Login!
LIBRESPOT_ENABLE_VOLUME_NORMALISATION=
LIBRESPOT_SYSTEM_CACHE=/var/cache/raspotify
LIBRESPOT_ONEVENT=/usr/local/bin/spotify_event.sh
LIBRESPOT_BACKEND=alsa
LIBRESPOT_DEVICE=hw:1,0
```

**Timing-Fix (`/lib/systemd/system/raspotify.service`):**
```ini
Wants=network-online.target sound.target
After=network-online.target sound.target avahi-daemon.service
```

**Raspotify Service Hardening deaktivieren:**
```ini
ProtectHome=false
PrivateUsers=false
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

---

## Spotify Track-Anzeige

`/usr/local/bin/spotify_event.sh` schreibt bei Wiedergabe:
```
track_changed|Titel|Artist|Album  ->  /tmp/spotify_status
```

`status.py` liest `/tmp/spotify_status` alle 6 Sekunden.

---

## DAB+ (RTL-SDR + welle.io)

- Menü: Musik → DAB+ → Sendersuche
- Scannt alle Band-III Kanaele (5A - 13F)
- Ergebnis gespeichert in `config/dab_stations.json`
- Wiedergabe: `welle-cli | mpv` Pipeline

---

## Scanner (RTL-SDR + rtl_fm)

| Dienst | Frequenz | Kanaele | Bandbreite | Modulation |
|---|---|---|---|---|
| PMR446 | 446.006–446.094 MHz | 8 fest | 12.5 kHz | NFM | Kanal waehlen + Scan ↑↓ |
| Freenet | 149.025–149.088 MHz | 4 fest | 12.5 kHz | NFM | Kanal waehlen |
| LPD433 | 433.075–434.775 MHz | 69 fest | 12.5 kHz | NFM | Kanal waehlen + Scan ↑↓ |
| VHF manuell | 136–174 MHz | stufenlos | 25 kHz | NFM | Manuell + Scan ↑↓ |
| UHF manuell | 400–470 MHz | stufenlos | 25 kHz | NFM | Manuell + Scan ↑↓ |

Wiedergabe: `rtl_fm | mpv` Pipeline, identisch mit FM Radio.
Alle lizenzfreien Dienste koennen ohne Genehmigung emfpangen werden.

## FM Radio (RTL-SDR + rtl_fm)

- Voreingestellt in `config/fm_stations.json`
- Manuelle Frequenzeingabe: ↑↓ fuer 0.1 MHz, ←→ fuer 1.0 MHz
- Wiedergabe: `rtl_fm | mpv` Pipeline, 200 kHz Bandbreite, WFM

---

## Logging

```bash
# Live verfolgen (launcher + main, alles in einer Datei)
tail -f /var/log/pidrive/pidrive.log

# Launcher-Schritte filtern
grep "LAUNCH" /var/log/pidrive/pidrive.log

# Service-Journal
journalctl -u pidrive -f

# Spezifisch filtern
grep "MENU\|TRIGGER\|ACTION\|ERROR" /var/log/pidrive/pidrive.log

# Log loeschen
sudo truncate -s 0 /var/log/pidrive/pidrive.log
```

Log-Rotation: max 512 KB pro Datei, 2 Backups.

**Startup-Log Beispiel (erfolgreich, v0.3.7):**
```
[LAUNCH/INFO] PiDrive Launcher gestartet
[LAUNCH/INFO]   UID: 0 (root)
[LAUNCH/INFO]   Gruppen: root, tty, video
[LAUNCH/INFO] --- Berechtigungs-Check ---
[LAUNCH/INFO]   ✓ Framebuffer: /dev/fb0  [crw-rw---- root:video (0660)]
[LAUNCH/INFO]   ✓ Framebuffer: O_RDWR erfolgreich
[LAUNCH/INFO]   ✓ TTY3: /dev/tty3  [crw-rw---- root:tty (0660)]
[LAUNCH/INFO]   ✓ TTY3: O_RDWR erfolgreich
[LAUNCH/INFO]   ✓ Aktives VT: tty3
[LAUNCH/INFO] --- TTY Setup ---
[LAUNCH/INFO]   ✓ chvt 3 OK
[LAUNCH/INFO]   ✓ /dev/tty3 geoeffnet (fd=3)
[LAUNCH/INFO]   ✓ setsid() OK
[LAUNCH/INFO]   ✓ TIOCSCTTY: /dev/tty3 ist jetzt Controlling Terminal
[LAUNCH/INFO]   ✓ stdin → /dev/tty3
[LAUNCH/INFO] Starte: /usr/bin/python3 .../main.py
[INFO] PiDrive gestartet
[INFO] --- System-Check ---
[INFO]   ✓ PiDrive Version: 0.3.7
[INFO]   ✓ /dev/fb0 OK
[INFO]   ✓ fbcp laeuft
[INFO]   ✓ Aktives VT: tty3
[INFO]   ✓ /dev/tty3 O_RDWR: erfolgreich
[INFO] --- System-Check OK ---
[INFO] PiDrive v0.3.7 laeuft!
```

---

## OTA Update

```bash
# Schnellste Methode (install.sh macht alles):
curl -sL https://raw.githubusercontent.com/MPunktBPunkt/pidrive/main/install.sh | sudo bash

# Manuell:
cd ~/pidrive && git pull
sudo cp ~/pidrive/systemd/pidrive.service /etc/systemd/system/pidrive.service
sudo systemctl daemon-reload
sudo systemctl restart pidrive

# Im Menue: System -> Update -> Auf Updates pruefen
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
|   |-- FM Radio (RTL-SDR, fm_stations.json)
|   +-- Scanner (PMR446/Freenet/LPD433/VHF/UHF)
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

## Steuerung

### USB-Tastatur (direkt am Pi)
Pfeiltasten + Enter + ESC — funktioniert nach Reboot automatisch.

### SSH-Steuerung
```bash
python3 ~/pidrive_ctrl.py
```

### Manueller Neustart (Entwicklung)
```bash
sudo systemctl restart pidrive
```

---

## Bekannte Probleme & Loesungen

| Problem | Ursache | Loesung |
|---|---|---|
| Display dunkel | pygame auf fb0+fbcp Architektur — ersetzt durch fb1 direkt | main_display.py + pidrive_display.service (v0.6.2) |
| Display zeigt nichts | camera/display_auto_detect=1 | In config.txt auf 0 |
| Unable to open console terminal | /dev/tty3 nicht lesbar oder kein Controlling Terminal | launcher.py + udev-Regel (v0.3.7) |
| Service Restart-Schleife | HUP bei StandardInput=tty | launcher.py ersetzt TTY-Management (v0.3.7) |
| Service stirbt exit(0) | PAMName+StandardInput+root haengt systemd247 | Core ohne pygame (v0.6.2) |
| set_mode() haengt | SDL wartet auf VT in monolithischem Service | Core/Display Trennung + fb1 direkt (v0.6.2) |
| pygame border_radius | pygame 1.9.6 | draw.rect() ohne border_radius |
| Raspotify kein Login | DISABLE_CREDENTIAL_CACHE aktiv | Zeile auskommentieren |
| Raspotify zu frueh | network.target | network-online.target |
| Raspotify kein Audio | PulseAudio als root | LIBRESPOT_BACKEND=alsa + DEVICE=hw:1,0 |
| Raspotify ProtectHome | Service Hardening | ProtectHome=false, PrivateUsers=false |
| WLAN nach Reboot aus | rfkill | rfkill-unblock.service |
| Touch reagiert nicht | Hardware-Defekt | USB-Tastatur |
| Konsole ueberlagert Display | stdout auf tty3 | StandardOutput=null im Service |
| Menue-Text ueberlaeuft | pygame Surface | eigene Surface (_draw_left) |
| DAB+ kein Ton | welle-cli fehlt | sudo apt install welle.io |
| FM kein Ton | rtl_fm fehlt | sudo apt install rtl-sdr |

---

## Changelog

### v0.6.2 (aktuell)
- BREAKING: Core/Display getrennt (Refactor-Plan umgesetzt)
- pidrive_core.service: headless, kein pygame, kein Display
- pidrive_display.service: pygame direkt auf fb1 (480x320, 16bpp), kein fbcp
- main_core.py: Trigger, Status, Audio, Menuezustand — kein pygame
- main_display.py: reine Anzeige, liest IPC-JSON vom Core
- ipc.py: atomares JSON (/tmp/pidrive_status.json + menu.json)
- Display-Crash stoppt nicht mehr den Core
- fbcp entfernt (nicht mehr noetig)
- rc.local: stark vereinfacht

### v0.4.1
- launcher.py: Diagnose-Version — TIOCSCTTY entfernt, Step-Logging
- main.py: SIGHUP-Handler sichtbar im Log, SDL Umgebungspruefung vor pygame.init()
- Erkenntnis: TIOCSCTTY allein reicht nicht — VT3 muss foreground sein

### v0.4.0
- SDL_AUDIODRIVER=dummy gesetzt vor pygame.init()
- pygame.init() laeuft jetzt vollstaendig durch (kein selektives init mehr noetig)

### v0.3.9
- launcher.py: tcsetpgrp() Fix — SDL fbcon exit(0) bei VT_SETMODE behoben
- scanner.py: Scan aufwaerts/abwaerts fuer PMR446, LPD433, VHF, UHF
- install.sh: Zeitzone Europe/Berlin + fake-hwclock

### v0.3.8
- Kritischer Bugfix: pygame.init() durch pygame.display.init() + pygame.font.init() ersetzt
- SDL exit(0) bei ALSA-Konflikt behoben (raspotify belegte hw:1,0)
- scanner.py: PMR446, Freenet, LPD433, VHF, UHF
- RTL-SDR Check in system_check() und install.sh

### v0.3.7
- launcher.py: Neues TTY-Setup Script (setsid + TIOCSCTTY)
- launcher.py: Berechtigungs-Check mit O_RDWR-Test fuer fb0 und tty3
- launcher.py: Vollstaendiges Logging nach pidrive.log (Tag: LAUNCH)
- Service: User=root, kein StandardInput=tty mehr, kein HUP-Problem
- install.sh: 10 Schritte, Service Stop/Start, udev-Regel, tty-Gruppe
- install.sh: rc.local mit chvt 3 + chmod 660 /dev/tty3
- main.py: system_check() mit uid, groups, stdin-Ziel, O_RDWR-Test

### v0.3.6
- log.py: Import-Bug behoben (UnboundLocalError: os)
- main.py: Detailliertes Startup-Logging mit System-Check
- Service: TTYVHangup=no, After=rc-local.service

### v0.3.5
- System-Check beim Start (fb0, fbcp, tty3, pygame, WLAN, Raspotify)

### v0.3.3
- Bugfix: chvt 3 aus Service (HUP-Signal Schleife)
- Spotify: ALSA Backend (hw:1,0)
- Raspotify: ProtectHome=false, PrivateUsers=false

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

## Aktuell offenes Problem (Stand v0.6.2)

**Display-Test:** Nach Core/Display-Trennung muss fb1-Direktrendering bestätigt werden.

```bash
# Core starten und testen
sudo systemctl start pidrive_core
echo "down" > /tmp/pidrive_cmd
cat /tmp/pidrive_menu.json  # muss item wechseln

# Display direkt testen (ohne Service)
sudo SDL_FBDEV=/dev/fb1 SDL_VIDEODRIVER=fbcon \
     SDL_AUDIODRIVER=dummy SDL_VIDEO_FBCON_KEEP_TTY=1 \
     python3 -c "
import pygame, time
pygame.display.init()
s = pygame.display.set_mode((480, 320), 0, 16)
s.fill((255, 0, 0))
pygame.display.flip()
print('ROT OK')
time.sleep(5)
"
```

## Roadmap

- [ ] GPIO-Buttons (Key1=GPIO23, Key2=GPIO24, Key3=GPIO25)
- [ ] BMW iDrive ESP32 Integration
- [ ] USB-Tethering Autostart
- [ ] Hotspot-Modus
- [ ] DAB+ Programminfo
- [ ] FM RDS Text-Anzeige
- [ ] Equalizer

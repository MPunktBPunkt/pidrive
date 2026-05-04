# PiDrive — Kontext & Projektdokumentation v0.9.30

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
| Display-Verbindung | SPI (erste 26 GPIO-Pins) |
| Touch | ADS7846/XPT2046 — Hardware-Defekt am Testgeraet |
| RTL-SDR | Fuer DAB+ und FM Radio |
| **Audio-Ausgang** | **3.5mm Klinke** (hw:1,0) → Autoradio AUX-IN |
| **Stromversorgung** | USB-A Port im Auto (5V/2A min.) oder KFZ-Adapter |
| **Steuerung** | USB-Tethering / WLAN → SSH / File-Trigger |
| **Audio-Ausgang** | **3.5mm Klinke** (hw:1,0) oder **Bluetooth A2DP** |
| **Steuerung** | BMW iDrive → AVRCP → `/tmp/pidrive_cmd` (pidrive_avrcp.service) |
| **BMW iDrive** | BMW 118d 2017 NBT EVO, AVRCP über Bluetooth |

---

## Physische Verbindung mit dem Auto

### Audioverbindung (aktiv)

```
Raspberry Pi 3.5mm Klinke (hw:1,0)
        │
    Klinke-Kabel (3.5mm auf 3.5mm)
        │
    BMW Aux-IN / Adapter
        │
    Fahrzeug-Lautsprecher
```

**Voraussetzung:** Das Fahrzeug braucht einen AUX-IN Eingang.
Bei BMW typisch: CD-Wechsler-Buchse oder direkter AUX-Eingang je nach Modell.

**Audio-Ausgang setzen:**
```bash
# Klinke aktivieren (ALSA hw:1,0)
echo "audio_klinke" > /tmp/pidrive_cmd
# oder direkt:
amixer -c 0 cset numid=3 1
```

### Stromversorgung

```
KFZ-Stecker 12V
        │
    USB-KFZ-Adapter (5V/2A oder 3A)
        │
    Micro-USB → Raspberry Pi 3B
```

**Empfehlung:** Mindestens 2A Ladestrom. Unterspannungswarnungen
(Blitz-Symbol oben links im Display) deuten auf zu schwaches Netzteil hin.

### Steuerung / Netzwerk

**Option A: USB-Tethering (empfohlen fuer Entwicklung)**
```
Raspberry Pi USB-Port
        │
    USB-Kabel
        │
    PC / Mac → SSH, Browser (http://PI-IP:8080)
```

**Option B: WLAN (aktuell aktiv)**
```
Raspberry Pi WLAN
        │
    Heimnetz / Hotspot
        │
    PC → SSH, Browser (http://192.168.178.92:8080)
```

**Option C: BMW iDrive Integration (Roadmap)**
```
BMW iDrive Drehsteller
        │
    ESP32 (liest CAN-Bus oder USB-HID)
        │
    Pi USB / WLAN
        │
    echo "up/down/enter" > /tmp/pidrive_cmd
```

### iPod-Emulation (iDrive-Adapter)

PiDrive emuliert einen iPod gegenueber dem iDrive-Adapter.
Dafuer wird ein **BMW iPod-Adapter** (z.B. Dension, Connects2) benoetigt,
der am CD-Wechsler-Anschluss des Fahrzeugs sitzt.

**Verbindung:**
```
BMW iDrive Adapter (CD-Wechsler-Port)
        │
    Proprietary Apple-Dock-Connector
        │
    Raspberry Pi GPIO (zukuenftig: libaacs/iap Emulation)
```

**Aktueller Stand:** Steuerung erfolgt noch via File-Trigger (SSH/Web).
Die iPod-Emulation ist noch nicht implementiert.

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
├── config.txt.example
├── KontextPiDrive.md
├── systemd/
│   └── pidrive.service      (User=root, launcher.py)
└── pidrive/
    ├── launcher.py          (SIGHUP=SIG_IGN + execv, startet main_core.py)
    ├── main.py              (veraltet, nur als Referenz)
    ├── main_core.py         (Core: headless, kein pygame, RTL via rtlsdr.py)
    ├── main_display.py      (Display: pygame auf fb1 direkt)
    ├── ipc.py               (IPC: atomares JSON Core↔Display)
    ├── menu_model.py        (Baummenü: MenuNode, MenuState, StationStore)
    ├── mpris2.py            (MPRIS2 D-Bus → BMW-Display Metadaten)
    ├── avrcp_trigger.py     (AVRCP → File-Trigger, BMW iDrive Steuerung)
    ├── webui.py             (Flask Web UI, Port 8080)
    ├── ui.py
    ├── status.py
    ├── trigger.py
    ├── log.py               (getrennte core.log + display.log)
    ├── diagnose.py
    ├── VERSION              (aktuell: 0.8.10)
    ├── config/
    │   ├── stations.json    (Webradio)
    │   ├── dab_stations.json (DAB+ nach Scan)
    │   ├── fm_stations.json  (FM Sender)
    │   └── settings.json
    ├── web/
    │   ├── templates/index.html  (Web UI Template)
    │   └── static/style.css
    ├── mpv_meta.py          (Now-Playing via mpv IPC)
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

## PAMName=login — Warum wir es NICHT verwenden

PAMName=login + StandardInput=tty + User=root haengt auf systemd 247 (Bullseye):
systemd forkt einen internen PAM-Helper der nie fertig wird.
Python startet nie. Loesung: kein PAMName, kein TTYPath, kein StandardInput=tty.
Stattdessen: SDL_VIDEO_FBCON_KEEP_TTY=1 + fb1 direkt.

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

## TIOCSCTTY — Warum wir es NICHT verwenden (v0.7.20)

SDL fbcon ruft intern VT_SETMODE(VT_PROCESS) auf. Wenn der Prozess ein
Controlling Terminal hat (gesetzt via TIOCSCTTY), sendet der Kernel SIGHUP
bei VT-Events (z.B. wenn VT3 in den Vordergrund kommt). SDL hat keinen
SIGHUP-Handler -> exit(0), kein Python-Fehler, kein Log-Eintrag.

Diagnose (v0.7.20):
- Test MIT TIOCSCTTY: "Aufgelegt" (= SIGHUP) nach pygame.init()
- Test OHNE TIOCSCTTY (stdin=/dev/null): pygame.init() OK
- Loesung: O_NOCTTY beim Oeffnen von tty3, kein setsid(), kein TIOCSCTTY
- chvt 3 reicht: VT3 muss nur foreground sein, nicht Controlling Terminal


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


## BMW iDrive Steuerung (AVRCP)

**Fahrzeug:** BMW 118d 2017 (NBT EVO)
**Protokoll:** Bluetooth A2DP (Audio) + AVRCP (Steuerung)

Kein iPod-Adapter, kein ESP32, kein CAN-Bus nötig.
Pi verbindet sich per Bluetooth mit dem Auto — Audio UND Steuerung über ein Kabel.

### AVRCP → File-Trigger Mapping

| BMW iDrive Aktion | AVRCP Befehl | PiDrive Trigger |
|---|---|---|
| Drehsteller rechts | NEXT | `down` |
| Drehsteller links | PREV | `up` |
| Drehsteller drücken | PLAY/PAUSE | `enter` |
| Zurück-Taste | STOP | `back` |
| 2x Drücken (< 0.5s) | 2x PLAY/PAUSE | `cat:0` (Jetzt läuft) |

### Audio-Routing (NICHT parallel!)

```
Bluetooth A2DP:  Pi → BMW Lautsprecher (empfohlen)
Klinke (AUX):   Pi → BMW AUX-IN        (Fallback)
```

Wichtig: Audio läuft immer nur auf EINEM Ausgang.
Wenn BT aktiv: alle mpv-Instanzen nutzen bluealsa/A2DP.
Wenn Klinke: mpv nutzt ALSA hw:1,0.

### Menü-Design für AVRCP

AVRCP hat nur 4 Befehle → Menü muss damit bedienbar sein:

- **up/down** (Drehen): Einträge wählen
- **enter** (Drücken): tiefer / Aktion ausführen
- **back** (Zurück): eine Ebene zurück
- **2x Drücken**: sofort zu "Jetzt läuft"

Maximale sinnvolle Tiefe: 4 Ebenen.
Häufigste Aktionen immer oben im Menü.

### Service

```bash
# Status prüfen
systemctl status pidrive_avrcp

# Log
journalctl -u pidrive_avrcp -f

# Manuell testen (ohne BT)
echo "next" | python3 ~/pidrive/pidrive/avrcp_trigger.py
```

### MPRIS2 — BMW-Display Metadaten

Der Pi sendet über MPRIS2 D-Bus Trackinfo ans BMW-Display:

```
Pi MPRIS2 → Bluetooth AVRCP → BMW iDrive Display
  Jetzt läuft: "Bayern 3"
  Artist:      "FM Radio"
  Album:       "PiDrive Radio"
```

Während der Menünavigation zeigt das BMW-Display den aktuellen Pfad:
```
  Titel:  "FM Radio"
  Artist: "Quellen › FM Radio"
```

**Servicedatei:** `mpris2.py` — wird von `main_core.py` gestartet

### AVRCP Version (BMW NBT EVO Kompatibilität)

BMW 118d 2017 NBT EVO bevorzugt AVRCP 1.4 oder 1.5.
AVRCP 1.6 (Android-Standard) kann Anzeigeprobleme verursachen.

**Fix wird automatisch von install.sh gesetzt:**
```ini
# /etc/bluetooth/main.conf
[AVRCP]
Version = 0x0105   # = AVRCP 1.5 (stabiler als 1.4, kein BIP)
```

### WiFi / Bluetooth Interferenz (Pi 3B)

Der Pi 3B teilt sich eine Antenne für 2.4GHz WLAN und Bluetooth.
Gleichzeitiges Streaming über WLAN + BT-Audio kann zu Rucklern führen.

**Fix in `/etc/bluetooth/main.conf` (von install.sh gesetzt):**
```ini
[LE]
MinConnectionInterval=7
MaxConnectionInterval=9
```

**Alternativen:**
- Pi per LAN-Kabel verbinden (empfohlen im Auto: USB-Tethering)
- Pi 4 nutzen: hat separate Antennen → kein Problem

**Hinweis:** Pi 3B hat **kein 5GHz** WLAN (erst ab Pi 3B+).

### AVRCP Versionsübersicht

| Version | Pi 3B | BMW NBT EVO | Empfehlung |
|---|---|---|---|
| 1.4 | stabil | ✓ | Minimum, Volume-Sync manchmal unzuverlässig |
| **1.5** | **stabil** | **✓** | **Verwendete Version — bester Sweet Spot** |
| 1.6 | komplex | teils ✓ | BIP Cover-Art oft instabil, nicht nötig |

### Warum nicht Mopidy

Mopidy ist ein vollständiger Musikserver der die gesamte Audio-Pipeline ersetzt.
PiDrive nutzt bewusst eigene Module (mpv, raspotify, welle-cli, rtl_fm) —
das passt zur Core/Display/Web-Architektur und bleibt schlank.
Mopidy würde die komplette Architektur ersetzen, nicht ergänzen.

### OBD2 Fahrzeugdaten (Roadmap)

Über USB-ELM327 Adapter am OBD2-Port:
```
OBD2-Port (unter Lenkrad)
    │
ELM327 USB Adapter (~15€)
    │
Pi USB → python-obd
    │
Drehzahl, Geschwindigkeit, Tankfüllung, Temperatur, Gaspedal, Fehlercodes
```

Wichtig: Pi 3B hat nur einen BT-Chip → bei BT für Audio/AVRCP
→ ELM327 per USB verwenden (nicht BT).

### Bluetooth Pairing (einmalig)

```bash
# Am Pi:
bluetoothctl
  power on
  discoverable on
  pairable on

# Am BMW: Bluetooth-Gerät "PiDrive" suchen und koppeln
# PIN falls nötig: 0000

# Danach: automatische Verbindung beim Start
# (pidrive_avrcp.service macht auto_connect beim Start)
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

### pidrive_web.service (`systemd/pidrive_web.service`)

```ini
[Unit]
Description=PiDrive Web UI (Debug/Remote)
After=network-online.target pidrive_core.service

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/pidrive/pidrive
ExecStart=/usr/bin/python3 /home/pi/pidrive/pidrive/webui.py
Restart=always
RestartSec=5
```

Erreichbar unter: `http://<PI-IP>:8080`
Funktionen: Menü-Vorschau, Navigation, Log-Viewer, Diagnose, Service-Status

### pidrive_web.service

```ini
[Unit]
Description=PiDrive Web UI (Debug/Remote)
After=network-online.target pidrive_core.service

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/pidrive/pidrive
ExecStart=/usr/bin/python3 /home/pi/pidrive/pidrive/webui.py
Restart=always
RestartSec=5
```

Erreichbar: `http://<PI-IP>:8080`

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
LIBRESPOT_DEVICE=default
# PULSE_SERVER=unix:/var/run/pulse/native  ← wird von install.sh in raspotify.service gesetzt
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
| pidrive_core.service | Core: headless, Trigger, Menü, IPC |
| pidrive_display.service | Display: pygame auf fb1 |
| pidrive_web.service | Web UI Port 8080 |
| pidrive_avrcp.service | BMW iDrive AVRCP → File-Trigger |
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
| CB-Funk DE/EU | 26.565–27.405 MHz | 80 fest | 10 kHz | FM | Kanal 41-80 + 1-40 |

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

PiDrive  (v0.9.4 — Baumbasiert, beliebig tief)
├── Jetzt laeuft
│   ├── Quelle                (info)
│   ├── Titel/Sender          (info)
│   ├── Spotify               (toggle)
│   ├── Audioausgang          (action)
│   ├── Lauter                (action)
│   └── Leiser                (action)
├── Quellen
│   ├── Spotify
│   │   ├── Spotify An/Aus    (toggle)
│   │   └── Status            (info)
│   ├── Bibliothek
│   │   ├── Durchsuchen       (action → headless_pick)
│   │   ├── Stop              (action)
│   │   └── Pfad              (info)
│   ├── Webradio
│   │   ├── Jetzt laeuft      (info)
│   │   ├── Sender            (folder → dynamisch aus stations.json)
│   │   │   ├── ★ Bayern 3 [Pop/Rock]   (station)
│   │   │   └── ...
│   │   └── Sender neu laden  (action)
│   ├── DAB+
│   │   ├── Jetzt laeuft      (info)
│   │   ├── Sender            (folder → dynamisch aus dab_stations.json)
│   │   │   ├── ★ Bayern 1 [11D]        (station, nach Suchlauf)
│   │   │   └── ...
│   │   ├── Suchlauf starten  (action → scan → merge → sofort sichtbar)
│   │   ├── Naechster Sender  (action)
│   │   └── Vorheriger Sender (action)
│   ├── FM Radio
│   │   ├── Jetzt laeuft      (info)
│   │   ├── Sender            (folder → dynamisch aus fm_stations.json)
│   │   │   ├── ★ Bayern 3  99.4 MHz    (station)
│   │   │   └── ...
│   │   ├── Suchlauf starten  (action → scan → merge → sofort sichtbar)
│   │   ├── Naechster Sender  (action)
│   │   ├── Vorheriger Sender (action)
│   │   └── Frequenz manuell  (action)
│   └── Scanner
│       ├── PMR446
│       │   ├── aktuelle Info (info: live Kanal/Frequenz)
│       │   ├── Kanal +       (action)
│       │   ├── Kanal -       (action)
│       │   ├── Scan weiter   (action)
│       │   └── Scan zurueck  (action)
│       ├── Freenet           (gleiche Struktur)
│       ├── LPD433            (gleiche Struktur)
│       ├── VHF               (gleiche Struktur)
│       └── UHF               (gleiche Struktur)
├── Verbindungen
│   ├── Bluetooth An/Aus      (toggle)
│   ├── Geraete scannen       (action)
│   ├── Verbunden mit         (info)
│   ├── WiFi An/Aus           (toggle)
│   ├── Netzwerke scannen     (action)
│   └── SSID                  (info)
└── System
    ├── IP Adresse            (info)
    ├── System-Info           (action)
    ├── Version               (action)
    ├── Neustart              (action)
    ├── Ausschalten           (action)
    └── Update                (action, OTA via GitHub)
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

## File-Trigger (`/tmp/pidrive_cmd`)

```bash
echo "up/down/enter/back/left/right" > /tmp/pidrive_cmd
echo "cat:0"                       > /tmp/pidrive_cmd   # Jetzt laeuft
echo "cat:1"                       > /tmp/pidrive_cmd   # Quellen
echo "cat:2"                       > /tmp/pidrive_cmd   # Verbindungen
echo "cat:3"                       > /tmp/pidrive_cmd   # System
echo "dab_scan"                    > /tmp/pidrive_cmd   # DAB+ Suchlauf
echo "fm_scan"                     > /tmp/pidrive_cmd   # FM Suchlauf
echo "fm_next"                     > /tmp/pidrive_cmd   # FM Naechster Sender
echo "dab_next"                    > /tmp/pidrive_cmd   # DAB Naechster Sender
echo "reload_stations:dab"         > /tmp/pidrive_cmd   # DAB Stationen neu laden
echo "reload_stations:fm"          > /tmp/pidrive_cmd   # FM Stationen neu laden
echo "reload_stations:webradio"    > /tmp/pidrive_cmd   # Webradio neu laden
echo "scan_up:pmr446"              > /tmp/pidrive_cmd   # PMR446 Kanal hoch
echo "scan_next:pmr446"            > /tmp/pidrive_cmd   # PMR446 Scan weiter
echo "scan_jump:cb:10"             > /tmp/pidrive_cmd   # CB-Funk 10 Kanäle vor
echo "scan_step:vhf:0.025"         > /tmp/pidrive_cmd   # VHF +25 kHz
echo "scan_step:uhf:-1.0"          > /tmp/pidrive_cmd   # UHF -1 MHz
echo "fm_gain:-1"                   > /tmp/pidrive_cmd   # FM Auto-Gain (AGC)
echo "fm_gain:30"                   > /tmp/pidrive_cmd   # FM Gain 30 dB
echo "dab_gain:-1"                  > /tmp/pidrive_cmd   # DAB Auto-Gain (AGC)
echo "dab_gain:35"                  > /tmp/pidrive_cmd   # DAB Gain 35 dB
echo "bt_backup"                     > /tmp/pidrive_cmd   # BT Pairing-Keys sichern
echo "bt_restore"                     > /tmp/pidrive_cmd   # BT Pairing-Keys wiederherstellen
echo "rtlsdr_reset"                  > /tmp/pidrive_cmd   # RTL-SDR USB-Reset (kein Reboot)
echo "ppm:0"                          > /tmp/pidrive_cmd   # PPM-Korrektur deaktivieren
echo "ppm:25"                         > /tmp/pidrive_cmd   # PPM-Korrektur +25 ppm
echo "squelch:15"                     > /tmp/pidrive_cmd   # Scanner Squelch empfindlich
echo "squelch:25"                     > /tmp/pidrive_cmd   # Scanner Squelch Standard
echo "scan_setfreq:vhf:145.500"    > /tmp/pidrive_cmd   # VHF direkt auf 145.5 MHz
echo "scan_inputfreq:vhf"          > /tmp/pidrive_cmd   # VHF manuelle Eingabe
echo "wifi_on/wifi_off"             > /tmp/pidrive_cmd
echo "bt_on/bt_off"                 > /tmp/pidrive_cmd
echo "audio_klinke/hdmi/bt/all"     > /tmp/pidrive_cmd
echo "spotify_on/spotify_off"       > /tmp/pidrive_cmd
echo "radio_stop/library_stop"      > /tmp/pidrive_cmd
echo "reboot/shutdown"              > /tmp/pidrive_cmd
```

---

## Steuerung

### Steuerung via SSH / Web UI
```bash
echo 'down' > /tmp/pidrive_cmd
# oder: http://PI-IP:8080
```

### Manueller Neustart
```bash
sudo systemctl restart pidrive_core
sudo systemctl restart pidrive_display
```

---

## Bekannte Probleme & Loesungen

| Problem | Ursache | Loesung |
|---|---|---|
| Display dunkel | pygame auf fb0+fbcp Architektur — ersetzt durch fb1 direkt | main_display.py + pidrive_display.service (v0.7.20) |
| Display zeigt nichts | camera/display_auto_detect=1 | In config.txt auf 0 |
| Unable to open console terminal | /dev/tty3 nicht lesbar oder kein Controlling Terminal | launcher.py + udev-Regel (v0.3.7) |
| Service Restart-Schleife | HUP bei StandardInput=tty | launcher.py ersetzt TTY-Management (v0.3.7) |
| Service stirbt exit(0) | PAMName+StandardInput+root haengt systemd247 | Core ohne pygame (v0.7.20) |
| set_mode() haengt | SDL wartet auf VT in monolithischem Service | Core/Display Trennung + fb1 direkt (v0.7.20) |
| pygame border_radius | pygame 1.9.6 | draw.rect() ohne border_radius |
| Raspotify kein Login | DISABLE_CREDENTIAL_CACHE aktiv | Zeile auskommentieren |
| Raspotify zu frueh | network.target | network-online.target |
| Raspotify kein Audio | PulseAudio als root | LIBRESPOT_BACKEND=alsa, LIBRESPOT_DEVICE=default, PULSE_SERVER in Service (v0.8.11+) |
| Raspotify ProtectHome | Service Hardening | ProtectHome=false, PrivateUsers=false |
| WLAN nach Reboot aus | rfkill | rfkill-unblock.service |
| Touch reagiert nicht | Hardware-Defekt | USB-Tastatur |
| Konsole ueberlagert Display | stdout auf tty3 | StandardOutput=null im Service |
| Menue-Text ueberlaeuft | pygame Surface | eigene Surface (_draw_left) |
| DAB+ kein Ton | welle-cli fehlt | sudo apt install welle.io |
| DAB '-o' Fehler | welle-cli 2.2 kennt -o nicht | dab.py: -p PROGRAMMNAME Syntax — behoben v0.8.11 |
| Kein Ton auf Klinke | Pi-Ausgang physisch auf HDMI (amixer numid=3) | audio.py: _set_pi_output_klinke() — behoben v0.8.14 |
| BT Agent No agent is registered | _btctl() subprocess stirbt sofort | bluetooth.py: persistenter bluetoothctl-Prozess — behoben v0.8.14 |
| BT AuthenticationFailed nach Reboot | Pairing-Keys verloren, Kopfhörer hat alte Keys | bluetooth.py: Paired:no → auto-remove + Neu-Pairing (v0.8.15) |
| RTL-SDR Stick verschwindet aus USB | libusb-Aufhänger nach unsauber gestopptem Scanner | rtlsdr.py: usb_reset() + WebUI-Button (v0.8.16) |
| FM kein Ton | rtl_fm fehlt | sudo apt install rtl-sdr |

---

## Changelog

### v0.10.22 — JS-Fehlerdiagnose: globaler Error-Handler + console.log

**Problem noch nicht gelöst — Diagnose-Stufe eingebaut:**

Die Buttons reagieren nicht, Tabs wechseln nicht. Da `WebUI CMD:` nie im Log erscheint
(obwohl die Buttons `sendCmd()` aufrufen sollten), muss ein JS-Fehler alle Handlers
lahmlegen. Das ist nach dem ersten `throw` in JS der Fall.

Eingebaute Diagnose-Stufen:
- `window.onerror` → zeigt JS-Fehler sichtbar in der Statusleiste (nicht nur Konsole)
- `sendCmd()` → `console.log('[PiDrive] sendCmd:', cmd)` beim Aufruf
- `showTab()` → `console.log('[PiDrive] showTab:', id)` beim Aufruf
- `vmLast = {{ vm | tojson }}` → try/catch, Fehler in Statusleiste
- `build_view_model()` → Exception-Fallback mit leerem vm statt Server-Error

**Nächster Schritt:** Browser-Konsole öffnen (F12 → Console) und PiDrive WebUI
neu laden. Dort sollten sichtbar sein:
- Etwaige Syntax/Runtime-Fehler mit Zeilennummer
- `[PiDrive] showTab: t1` beim Klick auf einen Tab
- `[PiDrive] sendCmd: down` beim Klick auf ↓

---

### v0.10.22 — sendCmd Timing-Fix: Browser-Navigation funktioniert jetzt

**ROOT CAUSE des Browser-Problems:**

Die Shell-Tests (`echo down > /tmp/pidrive_cmd`) funktionierten schon seit v0.10.19/20
korrekt — `MENU_NAV down before=0 after=1` war im Log sichtbar. Aber der Browser zeigte
trotzdem keine Änderung.

Ursache: `sendCmd()` rief `refreshCore()` **synchron direkt nach** dem POST zurück.
Der Pi-Core-Loop läuft mit 30ms-Intervall, braucht aber durch GPIO-/BT-Checks realistisch
~50-150ms bis das cmd-File verarbeitet ist. `refreshCore()` fetcht `/api/core` sofort
nach dem POST-Return (~2ms) → liest noch das alte `menu.json` → zeigt alten Cursor.

Der 1500ms `setInterval` würde zwar den aktualisierten Zustand zeigen, aber erst
1.5 Sekunden später — was wie "keine Reaktion" wirkt.

Fix: `sendCmd()` feuert `refreshCore` jetzt **zweimal verzögert**:
- nach 100ms (erster Versuch, meist ausreichend)
- nach 350ms (Fallback, garantiert nach Core-Verarbeitung)

Kein `refreshCore()` mehr direkt nach POST.

**Zusätzlich:** `git config core.fileMode false` nach `git pull` — verhindert dass git
Dateiberechtigungen im Repo verwaltet, was die wiederkehrenden 664→644 Korrekturen
in Schritt 9 reduziert.

---

### v0.10.22 — Menü-Fix komplett, Debug-Logging, Display-Guard

**ZWEITER TEIL DES NAVIGATIONS-FIX:**

Das eigentliche Problem war zweiteilig:
1. v0.10.19: `trigger_dispatcher.py` gab für nav-Commands `rebuild=False` zurück ✓
2. v0.10.22: `main_core.py` schrieb `menu.json` nur bei `needs_rebuild=True` — daher
   war der Cursor-Wechsel trotzdem nie sichtbar

Fix: `ipc.write_menu()` wird jetzt bei **jeder** `menu_state.rev`-Änderung aufgerufen,
unabhängig von `needs_rebuild`. Das deckt Navigation (cursor ändert sich → rev steigt)
und Rebuild (Baumstruktur ändert sich) gleichermaßen ab.

**Debug-Logging:**
- `webui.py /api/cmd`: `WebUI CMD: 'down' von 192.168.x.x` — sieht man im Log
  ob der Browser-Request ankommt
- `main_core.py check_trigger`: `CMD_READ: 'down'` — sieht man ob die Datei gelesen wird
- Zusammen mit `MENU_NAV down before=0 after=1 n=5` aus v0.10.19 ist der
  gesamte Pfad jetzt lückenlos loggbar

**Display-Service: Absturz-Schleife reduziert**
`ConditionPathExists=/sys/class/graphics/fb1` hilft nicht weil fb1 immer existiert.
Neuer Ansatz: `ExecStartPre` prüft `virtual_size` — schlägt fehl wenn Display nicht
initialisierbar. `StartLimitBurst=2` begrenzt Neustarts auf 2 pro 120s.

---

### v0.10.22 — Navigation-Fix (Hauptfehler), DAB-Status, Display-Guard, Sudoers

**ROOT CAUSE BEHOBEN: Menünavigation funktionierte nie (seit Dispatcher-Refactoring)**

Diagnose durch Tests auf dem Pi (v0.10.18):
- `TRIGGER down` kam im Core an ✓
- direkt danach: `MENU_REBUILD path=PiDrive cursor=0` → Cursor immer 0
- `rev` stieg ständig, aber `cursor` blieb immer `item=Jetzt laeuft`

Ursache: `trigger_dispatcher.handle_trigger()` setzte `rebuild=True` für NAV-Commands
(`up/down/enter/back/left/right`). `main_core.py` rief sofort `rebuild_tree()` auf,
das den Stack/Cursor auf Root/0 zurücksetzte. Jede Navigation war damit neutralisiert.

| Datei | Fix |
|---|---|
| `trigger_dispatcher.py` | rebuild=True nur für Strukturänderungen (scan/fav/reload), NICHT für nav |
| `menu_state.py` | `MENU_NAV down before=0 after=1 n=5` — Cursor-Logging |
| `dab_play.py` | no_lock setzt nicht mehr `radio_playing=True` — ehrlicher Status |
| `pidrive_display.service` | `ConditionPathExists=/sys/class/graphics/fb1` — kein Crash ohne Display |
| `install.sh` | `/etc/sudoers.d/pidrive` — NOPASSWD für Wartungsbefehle (Bookworm) |

---

### v0.10.22 — Root Cause Fix: PA-Setup ausserhalb Raspotify-Block, Diagnose-Kontext-Tests

**Root Cause: PulseAudio-Unit wurde nie geschrieben wenn Raspotify schon installiert war**

Das gesamte PA-Setup (asound.conf, system.pa, pulseaudio.service Unit) lag seit mehreren
Versionen INNERHALB des `if [ -f /etc/raspotify/conf ]; then`-Blocks. Wenn Raspotify bereits
installiert war (`conf` existierte), aber der Installer das PA-Setup schon einmal durchgeführt
hatte und die Unit dann manuell oder durch Cleanup entfernt wurde, wurde sie nie neu geschrieben.

Warum nie erkannt? Weil:
- Der Installer prüfte `systemctl is-active pulseaudio` — aber wenn die Unit fehlt, schlägt das
  mit "Unit could not be found" fehl, was in einem `|| true` verloren geht
- Diagnose prüfte bisher nur `systemctl is-active`, nicht ob die Unit-Datei physisch existiert
- Der Installer-Output zeigte "✓ Raspotify installiert" und ließ keinen Hinweis auf den
  fehlenden PA-Setup

Fix v0.10.22:
- PA-Setup (asound.conf, system.pa, PA Unit schreiben, systemctl enable/start) läuft jetzt
  **IMMER** — in eigenem Abschnitt, unabhängig von Raspotify
- Installer prüft nach dem Schreiben ob `/etc/systemd/system/pulseaudio.service` tatsächlich
  existiert und gibt ✓ oder ✗ aus
- Diagnose hat neuen Abschnitt `BENUTZER / KONTEXT / RECHTE` mit:
  - Service-User je Dienst (core=root, web=pi, ...)
  - Socket-Berechtigungen (/var/run/pulse/native, /tmp/pidrive_cmd)
  - PA Unit-Datei Existenz + --system Flag
  - User-PA noch aktiv? PipeWire aktiv?
  - /etc/systemd/user/ null-masking korrekt?

---

### v0.10.22 — Code Review Fixes (P1/P2): BT, Dispatcher, Rebuild, Stale-State

**Umsetzung aus vollständigem Code-Review v0.10.16 (P1 + P2):**

| # | Prio | Datei | Problem | Fix |
|---|---|---|---|---|
| 1 | P1 | `bt_devices.py` | `os` nicht importiert → `NameError: name 'os' is not defined` beim BT-Scan | `import os` ergänzt |
| 2 | P1 | `bt_devices.py` | `paired-devices` ungültiger bluetoothctl-Befehl | → `devices Paired` (wie avrcp_trigger.py) |
| 3 | P1 | `td_radio.py` | `build_tree` verwendet aber nicht importiert → NameError nach DAB/FM-Scan | `from menu_model import build_tree` ergänzt |
| 4 | P1 | `td_system.py` | `return False` auch bei erfolgreich behandeltem Command → Dispatcher dachte Befehl sei unbekannt | `return True` am Ende |
| 5 | P1 | `td_system.py` | `rebuild_tree(...)` nicht definiert → crash bei fav_toggle | Lazy import via `main_core._mc` |
| 6 | P1 | `trigger_dispatcher.py` | `rebuild` blieb immer False → Menü aktualisierte sich nach nav/scan nicht | rebuild=True für NAV + Scan-Commands |
| 7 | P1 | `main_core.py` | `LIST_FILE active=True` konnte hängenbleiben → WebUI scheinbar tot | Stale-Reset nach 60s |
| 8 | P2 | `trigger_dispatcher.py` | `bg()` ohne Exception-Handling → Fehler verschwanden still | Wrapper mit `log.error()` |
| 9 | P2 | `main_core.py` | PA-Socket fehlt → keine Warnung bis Audio versucht wird | Check bei `boot_phase=steady` |

---

### v0.10.22 — Debug-Tab Redesign, System-Diagnose, DAB Errfile, Webradio Metadaten

**Debug-Tab (t4): Checkboxen statt Buttons**

Neues UI: Checkbox-Auswahl welche Komponenten diagnostiziert werden sollen,
ein einzelner "▶ Diagnose starten"-Button. Verfügbare Checkboxen:
- Core Log, Display Log, App Log, AVRCP Log
- Core Status, Web Status  
- Diagnose (py) — volle Python-Diagnose (~30s)
- System (lsusb, Prozesse, Audio) — neues System-Diagnose-Panel
- DAB Fehler-Datei — welle-cli stderr farblich aufbereitet
- Grep (Fehler)

**Neues System-Diagnose Panel:**
- lsusb (USB-Geräte inkl. RTL-SDR, BT-Dongle)
- Relevante Prozesse mit User/PID/CPU/MEM
- Audio-Pfad: PA-Mode (System/User/none), Sinks, Default Sink, aktive Inputs
- asound.conf + ALSA-Karten
- Parallel-Instanzen: main_core.py, welle-cli, rtl_fm (erkennt Doppelinstanzen)
- Berechtigungen: /var/run/pulse/native, /tmp/pidrive_cmd

**DAB Fehler-Datei Panel:**
- Liest /tmp/pidrive_dab_<session>.err direkt aus
- Farbkodiert: Sync-Erfolg (grün), Sync-Verlust (rot), DLS (gelb), PCM (lila)
- Zeigt alle vorhandenen Session-Dateien
- Button "Nur Erfolge" filtert auf Superframe-sync-Nachrichten

**Neue WebAPI-Endpunkte:**
- `/api/diag/system` — lsusb, Prozesse, Audio-Pfad, Parallel-Instanzen, Rechte
- `/api/dab/errfile?session=<id>&n=<zeilen>` — welle-cli stderr mit Parsing

**Webradio Tab: Metadaten-Anzeige repariert**
- Zweite Zeile "Stream-Info" zeigt Interpret + Radio-Typ
- wrNowMeta wird in refreshWebradioTab() befüllt (war bisher nicht gesetzt)

---

### v0.10.22 — Installer-Reihenfolge Fix, Log-Tab Fix, Diagnose-PA-Check

**Installer: Car-Only Cleanup mit automatischem Exit + Reboot-Hinweis**

Problem in v0.10.14: Cleanup lief nach der Diagnose am Ende des Installers, aber ohne
anschliessenden Reboot. PulseAudio System-Mode greift erst nach Reboot — daher immer
noch User-PA aktiv bei der Diagnose.

Fix v0.10.22: Bei Erstinstallation läuft Cleanup am Ende, gibt expliziten Hinweis
`→ sudo reboot` und endet mit `exit 0`. Beim nächsten Install (nach Reboot) ist
`/etc/pidrive_car_cleanup_done` gesetzt → normaler Ablauf ohne Cleanup-Schleife.

**Debug Log-Tab: "Lädt..." hängt nicht mehr**

`loadAllLogs()` wartete per `Promise.all` auf 4 parallele Fetches inkl. `/api/diagnose`.
`/api/diagnose` ruft `diagnose.py` auf → ~30 Sekunden → ganzer Tab hängt.
Fix: Diagnose aus `loadAllLogs` entfernt, nur noch Core/Display/App-Log geladen.
Diagnose läuft weiterhin über eigenen Button.

**Diagnose: PA-Check erkennt System- vs User-Mode**

Verbesserte Erkennung: prüft `pgrep -a pulseaudio` auf `--system` Flag.
Zeigt klar ob System-PA oder User-PA läuft und gibt gezielten Fix-Hinweis.

---

### v0.10.22 — Code Review Fixes, Installer Car-Only Cleanup, DAB ALSA-Direkt

**Code Review (externer Review v0.10.13) — umgesetzte Fixes:**

| # | Problem | Datei | Status |
|---|---|---|---|
| 1 | `import socket`, `import subprocess` fehlten → Diagnose-Tab komplett kaputt | `webui_shared.py` | ✓ behoben |
| 2 | `handle_trigger` nicht definiert in `td_nav.py` → System-Menüpunkte (Reboot, Version, Info) crashten | `td_nav.py` | ✓ behoben |
| 3 | `PULSE_SERVER` in welle-cli Umgebung → DAB lief mit falschem PA-Kontext (anders als manuell) | `dab_play.py` | ✓ behoben |
| 4 | `diagnose.py` zeigte hardcoded `v0.9.30` statt aktueller Version | `diagnose.py` | ✓ behoben |
| 5 | `dabfm.py` — dead code (referenziert `Item` das nicht mehr existiert) | `modules/dabfm.py` | ✓ entfernt |

**Installer: Car-Only Cleanup automatisch bei Erstinstallation**

Bis v0.10.13 wurde der Car-Only Cleanup optional angeboten (15s Prompt). Das Problem:
User-PulseAudio bleibt aktiv wenn der Cleanup nicht ausgeführt wird → kein Ton in PiDrive.

Fix v0.10.22:
- **Erstinstallation** (kein `/etc/pidrive_car_cleanup_done`): Cleanup läuft **automatisch**
- **Folge-Installation**: optionaler Prompt wie bisher (15s Timeout)
- Checkpoint-Datei `/etc/pidrive_car_cleanup_done` verhindert ungewollte Wiederholungen

**DAB-Fix: PULSE_SERVER aus welle-cli Umgebung entfernt**

Seit v0.10.5 behielt `dab_play.py` `PULSE_SERVER` in der welle-cli Umgebung, damit
ALSA→PA-Plugin→System-PA funktioniert. Wenn aber User-PA statt System-PA läuft, war
`PULSE_SERVER=unix:/var/run/pulse/native` kontraproduktiv → welle-cli lief in einem anderen
Kontext als der manuelle Start → instabiler Lock, keine DLS, kein Ton.

Fix: `PULSE_SERVER` wird jetzt **entfernt** — welle-cli läuft ALSA-direkt wie beim manuellen
Konsolenstart. Audio über `/etc/asound.conf` Card 1 (bcm2835 Headphones).

---

### v0.10.8 — Code Review, DAB-Pfad-Analyse, Spectrum-UI, Bug-Fixes

**Code Review Ergebnisse:**

| # | Problem | Schwere | Behoben |
|---|---|---|---|
| 1 | `dab_helpers.py`: 10 Globals doppelt definiert | KRITISCH | ✓ |
| 2 | `install.sh`: Version noch `v0.10.0` | MITTEL | ✓ |
| 3 | `main_display.py`: hardcoded `v0.9.30` | MITTEL | ✓ |
| 4 | `webui.py` Blueprint-Fallback-Meldung irreführend | NIEDRIG | ✓ |
| 5 | `audio.py _pa_ok()` socket-check fehlte (v0.10.5-Fix nie angewendet) | MITTEL | ✓ (in v0.10.8) |
| 6 | `audio.py get_alsa_device()` totes Code | NIEDRIG | ✓ (entfernt) |
| 7 | `audio.py volume_up()` cap bei 150 statt 100 | NIEDRIG | ✓ |
| 8 | Flask Blueprint-Routen P1: 17 Duplikate → WebUI-Crash | KRITISCH | ✓ (in v0.10.8) |

**DAB Boot-to-Klinke Pfad-Analyse:**

Vollständige Sequenz nach Reboot bis Ton auf Klinke:

1. `systemd` startet `pidrive_core.service`
2. `main_core.startup_tasks()`:
   - **Readiness-Wait** (max 12s): PulseAudio + BT-Adapter bereit?
   - **BT-Reconnect**: `bluetooth.reconnect_known_devices()` → versucht gepairte Geräte
   - **Audio-Basis**: `audio._set_pi_output_klinke()` → amixer -c 1 sset PCM 85% unmute
   - **Startup Volume**: `audio.apply_startup_volume()` → pactl set all sinks
   - **Source-Resume**: `last_source=="dab"` → `dab_play.play_station(last_dab, S, settings)`

3. **`dab_play.play_station()`**:
   - `stop(S)` → pkill welle-cli
   - `audio.get_mpv_args(settings, source="dab")`:
     - `decide_audio_route()` → `requested="bt"`, kein BT-Sink → `effective="klinke"`
     - `apply_audio_route()` → `set_default_sink("alsa_output.1.stereo-fallback")` + amixer
   - `_welle_env = os.environ.copy()`, PULSE_SINK entfernt, PULSE_SERVER bleibt
   - `/etc/asound.conf` geprüft → `defaults.pcm.card 1`
   - welle-cli gestartet: `welle-cli -c 11B -g -1 -p 'SENDER' 2>session_err_file`
   - Lock-Wait (max 12s): "found sync" + "superframe sync succeeded" + "pcm name:"
   - `source_state.commit_source("dab")` + DLS-Poller-Thread

4. **Audio-Pfad welle-cli → Klinke**:
   - welle-cli erbt `PULSE_SERVER=unix:/var/run/pulse/native`
   - welle-cli öffnet ALSA "default" PCM
   - `/etc/asound.conf` `defaults.pcm.card 1` → Karten-Default = Card 1
   - ABER PulseAudio ALSA-Plugin überschreibt `pcm.!default {type pulse}`
   - PA verbindet sich via PULSE_SERVER an System-PA
   - PA default sink = `alsa_output.1.stereo-fallback` (von `set_default_sink` gesetzt)
   - → **Ton auf Klinke (Card 1 = bcm2835 Headphones) ✓**

**Neue WebUI-Funktion: Spektrum-Analyzer**

Im Scanner-Tab (Tab 4) neues Panel "🔭 Spektrum-Analyzer":
- Modi: Snapshot (Einzelfrequenz), Band-Sweep, PMR446, Freenet
- Parameter: Center-MHz, Samplerate, PPM, Gain
- Visueller Trace: Canvas-Liniengrafik mit dB-Skala und Peak-Markierungen
- Peak-Liste mit Frequenz und dB-Wert

---

### v0.10.8 — dab.py + trigger_dispatcher.py Split, Blueprint-Bug-Fix, Analyse

**Bug-Fix: 17 duplizierte Flask-Routen (kritisch)**
Routes existierten in webui.py UND in Blueprint-Dateien → Flask `AssertionError` beim Start.
Fix: Doppelte Routes aus webui.py entfernt.

**dab.py (1041 Zeilen) → 5 Dateien:**
- `dab_helpers.py` — Konstanten, Globals, Session-Management, Hilfsfunktionen, Gain-Tabelle
- `dab_dls.py` — DLS-Poller (Dynamic Label Segment), Thread-Management
- `dab_scan.py` — DAB Suchlauf, Sender-Datenbank (load/save_stations, scan_dab_channels)
- `dab_play.py` — Wiedergabe (play_station, play_by_name, stop, play_next/prev)
- `dab.py` — Facade (30 Zeilen), re-exportiert alle öffentlichen Funktionen

**trigger_dispatcher.py (909 Zeilen) → 6 Dateien:**
- `td_nav.py` — Navigation (up/down/enter/back), _execute_node, _fm_manual
- `td_hardware.py` — Spotify, Audio, WiFi/BT, Gain, PPM, Squelch, RTL-SDR Reset
- `td_radio.py` — DAB/FM Suchlauf, Webradio Play, FM/DAB next/prev, Reload
- `td_scanner.py` — Scanner-Steuerung (scan_up/down/step/jump/setfreq)
- `td_system.py` — Bibliothek, System-Kommandos, radio_stop
- `trigger_dispatcher.py` — Haupt-Dispatcher, delegiert an Sub-Dispatcher (97 Zeilen)

**Cross-File Analyse abgeschlossen:**
- P1 (kritisch): Duplizierte Flask-Routen — BEHOBEN
- P2: bt_watcher Dict-Import (mutable, OK)
- P3: bt_devices _scan_stop_flag (lokal, kein Cross-Module-Problem)
- P4: trigger_dispatcher Guards — _init_dispatcher() in startup_tasks() ✓
- P5: webui_shared.py kein Flask-App-Objekt ✓
- P6: menu_model.py Import-Pfade ✓
- P7: bluetooth.py Facade vollständig ✓

---

### v0.10.7 — bluetooth.py + menu_model.py Split

**bluetooth.py (1952 Zeilen) → 7 Dateien:**
- `bt_helpers.py` — Basis-Helfer, Konstanten, Adapter-Steuerung (261 Zeilen)
- `bt_agent.py` — BT-Agent-Session, Pairing (323 Zeilen)
- `bt_devices.py` — Geräte-Datenbank, Scan (429 Zeilen)
- `bt_audio.py` — PulseAudio-Sink, A2DP-Management (125 Zeilen)
- `bt_connect.py` — Connect/Disconnect, Reconnect-State (692 Zeilen)
- `bt_watcher.py` — Auto-Reconnect Watcher (226 Zeilen)
- `bluetooth.py` — Facade (88 Zeilen), alle Aufrufer unverändert

Import-Hierarchie ohne Zirkularbezug:
`bt_helpers ← bt_agent, bt_devices, bt_audio ← bt_connect ← bt_watcher ← bluetooth.py`

**menu_model.py (896 Zeilen) → 4 Dateien:**
- `menu_state.py` — MenuNode + MenuState (186 Zeilen)
- `station_store.py` — StationStore (348 Zeilen)
- `menu_builder.py` — build_tree() (385 Zeilen)
- `menu_model.py` — Facade (17 Zeilen)

---

### v0.10.6 — AVRCP Debug, trigger_dispatcher.py, webui.py Blueprint-Start

**AVRCP verbose Debug für Autotest:**
- Dedicated Raw-Log `/var/log/pidrive/avrcp_raw.log` (alle D-Bus + btctl Zeilen)
- dbus-monitor mit `--system` + 3 Interfaces: MediaPlayer2.Player, bluez.MediaPlayer1, bluez.MediaControl1
- Verboses Logging bei jedem Event: Raw-Linie, Kontext, Mapping, Latenz
- Heartbeat alle 60s, Doppelklick-Detection, Event-Zähler

**trigger_dispatcher.py** aus main_core.py ausgelagert (main_core.py: 1457→636 Zeilen)

**webui.py Blueprint-Architektur gestartet:**
- `webui_shared.py` — alle Shared Helpers
- `web/api/routes_dab.py`, `routes_bt.py`, `routes_audio.py`, `routes_webradio.py`
- NOTE: Bug in dieser Version (doppelte Routen) → in v0.10.8 behoben

---

### v0.10.5 — State Machine + audio.py verbessert

**source_state.py:**
- `previous_source` — letzte Quelle für Recovery/Fallback
- Stale-Transition-Watchdog: _check_stale_transition() in commit/end
- `commit_source(auto_end=True)` — erspart vergessenes end_transition()
- `force_end_transition(reason)` — für except-Blöcke
- `transition_count` + `stale_cleared` Diagnostik-Zähler
- `in_transition()` meldet Stale-Transitions direkt als False

**audio.py:**
- `decide_audio_route()` — Pure Policy, keine Side-Effects
- `apply_audio_route()` — Side-Effects getrennt (PA, amixer, source_state)
- `build_player_args()` — Player-Argumente ohne Side-Effects
- `get_mpv_args()` — Wrapper, rückwärtskompatibel
- Sink-Cache (2s TTL): `_list_sinks()` + `invalidate_sink_cache()`
- `_pa_ok()` Socket-Check statt systemctl (~10x schneller)
- DAB-toten Code entfernt (build_player_args source="dab" war nie genutzt)

### v0.9.30 — DAB: PULSE_ENV entfernt, Scanner: --ao=alsa

**Root Cause DAB kein Ton auf BT:**
`PULSE_SERVER`/`PULSE_SINK` im welle-cli Env verursachen einen RTL2838-Timing-Fehler:
- PulseAudio-Backend initialisiert den SDR anders → PLL-Lock kommt zu spät
- OFDM-Sync bricht ab: `SyncOnPhase failed`
- Manueller Start (ohne PULSE_*) → sofort Sync → Ton

**Beweis:** Manuelle Test `welle-cli -c 10A -p "ROCK ANTENNE BAY"` funktionierte.
PiDrive-Start mit PULSE_ENV → `Lost coarse sync`. Ohne PULSE_ENV → Audio.

**Fix:** welle-cli ohne jegliche PulseAudio-Env-Variablen starten.
ALSA → PulseAudio funktioniert automatisch. BT-Routing übernimmt PulseAudio Default-Routing.

**Scanner kein Ton:** Identisches Problem — `--ao=pulse` ohne PULSE_SERVER,
mpv findet System-Daemon nicht → ALSA Card 0 (HDMI). Fix: `--ao=alsa hw:1,0`.

| # | Datei | Fix |
|---|---|---|
| 1 | `modules/dab.py` | PULSE_SERVER/PULSE_SINK aus welle-cli-Befehl entfernt |
| 2 | `modules/scanner.py` | `--ao=pulse` → `--ao=alsa --alsa-device=hw:N,0` |

**Geänderte Dateien:** `modules/dab.py`, `modules/scanner.py`, `VERSION`

---

### v0.9.21 — DAB: welle-cli -p ALSA-direkt, BT-Scan fix

| # | Datei | Fix |
|---|---|---|
| 1 | `modules/dab.py` | `welle-cli -p "NAME"` → ALSA-direkt (kein PulseAudio, kein HTTP-Modus) |
| 2 | `modules/bluetooth.py` | BT Scan: `scan on`/`scan off` statt printf-Pipe (findet jetzt neue Geräte) |
| 3 | `modules/dab.py` | Scan: `url_mp3` nicht mehr befüllen (HTTP-Modus obsolet) |

**Geänderte Dateien:** `modules/dab.py`, `modules/bluetooth.py`, `VERSION`

---

### v0.9.20 — WebUI Tabs, DLS-Fix, HTTP-Timeout 15s

**WebUI in 4 Tabs:**
- Tab 1 Steuerung: Menü-Baum, Now Playing, Nav-Buttons, Rohdaten — 1.5s Poll
- Tab 2 Audio: Lautstärke, Gain, PPM, Squelch, BT Backup, Audio Debug — 5s Poll aktiv
- Tab 3 DAB/FM: RTL-SDR, AVRCP, DAB Scan, Spektrum — 5s Poll aktiv
- Tab 4 Log & Debug: Logs, Runtime Settings, Source State — 5s Poll aktiv

**Fixes:** `_time.sleep(8)` → `_tm.sleep(8)` (NameError); HTTP-Timeout 8s → 15s.

**Geänderte Dateien:** `web/templates/index.html`, `modules/dab.py`, `VERSION`

---

### v0.9.19 — FM/DAB: --ao=alsa direkt (PulseAudio-Pipe-Problem)

PulseAudio `--system` resampled raw PCM aus Pipes nicht zuverlässig → stille Ausgabe trotz Sink-Input.
Fix: `--ao=alsa --alsa-device=hw:N,0` für FM; DAB noch im HTTP-Modus (erst v0.9.21 korrekt).

**Geänderte Dateien:** `modules/audio.py`, `modules/fm.py`, `modules/dab.py`, `VERSION`

---

### v0.9.21 — FM/DAB: --ao=alsa direkt (PulseAudio-Pipe-Problem)

**Root Cause FM/DAB kein Ton:**
PulseAudio `--system` Mode hat Resampling-Probleme mit raw PCM aus stdout-Pipes
(rtl_fm 32kHz mono → PA 44.1kHz stereo). Sink-Input war vorhanden (mpv verbunden),
aber PulseAudio produzierte kein hörbares Audio.

Webradio nutzt HTTP-URL → mpv verarbeitet fertiges MP3 → kein Resampling-Problem.

**Fix: `--ao=alsa --alsa-device=hw:N,0` für FM und DAB (Klinke)**

```
# Vorher (PulseAudio -- stille Ausgabe trotz Sink-Input):
mpv --ao=pulse --demuxer=rawaudio --demuxer-rawaudio-rate=32000 ...

# Jetzt (ALSA direkt -- immer Ton):
mpv --ao=alsa --alsa-device=hw:1,0 --demuxer=rawaudio --demuxer-rawaudio-rate=32000 ...
```

BT (A2DP) nutzt weiterhin PulseAudio (muss durch PA für BT-Routing).

| # | Datei | Fix |
|---|---|---|
| 1 | `modules/audio.py` | `get_mpv_args()` gibt `["", "--ao=alsa", "--alsa-device=hw:N,0"]` für FM/DAB Klinke zurück |
| 2 | `modules/fm.py` | Leeren env-prefix herausfiltern |
| 3 | `modules/dab.py` | Leeren env-prefix herausfiltern |

**Geänderte Dateien:** `modules/audio.py`, `modules/fm.py`, `modules/dab.py`, `VERSION`

---

### v0.9.18 — NameError VERSION fix (Core-Crash)

**Bug:** In v0.9.16 wurde `log.info(f"PiDrive Core v{VERSION} gestartet")` eingeführt.
`VERSION` wird aber erst in `system_check()` (Zeile ~868) aus der Datei gelesen —
der Banner-Aufruf steht in `main()` davor → `NameError` → Core crasht sofort beim Start.

**Fix:** `VERSION` am Anfang von `main()` aus Datei lesen (vor dem Banner).

| Datei | Fix |
|---|---|
| `main_core.py` | `VERSION = open(...VERSION).read().strip()` ganz am Anfang von `main()` |

**Geänderte Dateien:** `main_core.py`, `VERSION`

---

### v0.9.17 — DAB Ton: welle-cli HTTP-Server + mpv URL (wie Webradio)

**Root Cause DAB kein Ton:**
`welle-cli` gibt bei stdout-Pipe **raw PCM** aus (keine Datei-Header, kein Container).
mpv liest stdin ohne `--demuxer=rawaudio`-Flags → kann Format nicht erkennen → kein Ton.
Webradio funktionierte weil mpv direkt eine HTTP-URL bekommt (fertig dekodiertes MP3).

**Fix — neue DAB-Architektur:**
1. `welle-cli -c CHANNEL -g GAIN` startet als HTTP-Server im Hintergrund
2. PiDrive wartet bis HTTP-Server antwortet (max 8s, poll alle 1s)
3. `mpv http://localhost:7981/mp3/<sid_dec>` — identisch zu Webradio-Ansatz

```
# Vorher (v0.9.15-v0.9.16 — raw PCM, kein Ton):
welle-cli -c 11B -g -1 -p 'NAME' | mpv --ao=pulse -

# Jetzt (v0.9.17 — MP3 via HTTP, Ton wie Webradio):
welle-cli -c 11B -g -1 &
warte bis http://localhost:7981/ antwortet
mpv http://localhost:7981/mp3/4874 --ao=pulse
```

**Geänderte Dateien:** `modules/dab.py`, `VERSION`

---

### v0.9.16 — DLS-Fix, Version-Konsistenz

| # | Datei | Bug | Fix |
|---|---|---|---|
| 1 | `modules/dab.py` | `NameError: SCAN_PORT not defined` in `_dls_poller` (Closure-Scope) | Port als Default-Arg `_port=_dls_port` übergeben |
| 2 | `main_core.py` | Erster Log-Banner zeigte hardcodiert `v0.9.14 gestartet` | Dynamisch: `f"PiDrive Core v{VERSION} gestartet"` |
| 3 | `diagnose.py` | Versions-Header zeigte `v0.9.14-final` | Dynamisch auf aktuelle VERSION |

**Geänderte Dateien:** `modules/dab.py`, `main_core.py`, `diagnose.py`, `VERSION`

---

### v0.9.15 — PULSE_SERVER-Fix: Ton auf Klinke für DAB/FM + DLS-Metadaten

**Root Cause kein Ton DAB/FM (endgültig):**
Webradio nutzt `Popen(["mpv", ..., url])` — funktionierte.
DAB/FM nutzen `shell=True, "welle-cli ... | mpv ... -"` — mpv als root-Prozess
kennt nur `/run/user/0/pulse/native` (existiert nicht), nicht `/var/run/pulse/native`.
→ mpv fiel auf ALSA Card 0 (HDMI) zurück → kein Ton.

Fix: `PULSE_SERVER=unix:/var/run/pulse/native PULSE_SINK=<klinke_sink>` als Shell-Env-Prefix.

| # | Datei | Fix |
|---|---|---|
| 1 | `modules/dab.py` | PULSE_SERVER+PULSE_SINK vor mpv in welle-cli Pipe |
| 2 | `modules/fm.py` | PULSE_SERVER+PULSE_SINK vor mpv in rtl_fm Pipe |
| 3 | `modules/audio.py` | `get_mpv_args()` gibt `["PULSE_SERVER=... PULSE_SINK=...", "--ao=pulse"]` zurück |
| 4 | `modules/dab.py` | DLS-Poller: pollt mux.json alle 8s → `S["track"]` + `S["artist"]` |
| 5 | `menu_model.py` | DAB Sender nach Kanal gruppiert (★ Favoriten + 11D/10A/11B als Unterordner) |
| 6 | `webui.py` | `api_volume()`: parst aus `pactl list sinks` statt `get-sink-volume` |
| 7 | `web/templates/index.html` | Menü-Baum live via `renderMenuTree()` statt statischem Jinja |

**Keylearning:**
- `PULSE_SERVER` muss für alle root-Prozesse explizit gesetzt werden
- `PULSE_SINK` ersetzt `set-default-sink` (Permissions-Problem) und `--audio-device` (mpv <0.35 Bug)
- DLS-Format: meist `Artist - Titel`, manchmal frei (Nachrichten, Promo-Texte)

**Geänderte Dateien:** `modules/dab.py`, `modules/fm.py`, `modules/audio.py`,
`menu_model.py`, `webui.py`, `web/templates/index.html`, `VERSION`

---

### v0.9.14 — Persistenter BT-Agent, Bekannte Geräte, DAB dict.strip Fix

**Motivation:** v0.9.13 aus externem Patch-Prozess erhalten.
v0.9.14 enthielt persistenten BT-Agent-Lifecycle und Known-Devices-Verwaltung.
Nachträglich korrigiert (v0.9.14_fixed2):

| # | Datei | Fix |
|---|---|---|
| 1 | `modules/dab.py` | `svc.get("label",{})` → `.strip()` auf Dict → `AttributeError` behoben |
| 2 | `modules/audio.py` | `get_alsa_sink()` + `_sink_is_hdmi()` Card-Index-Prüfung |
| 3 | `install.sh` | `KLINKE_SINK` per `awk '$2 ~ /alsa_output\.1\./'` statt `-v hdmi` |
| 4 | `ipc.py` | `bt_on` + `bt_status` in `write_status()` geschrieben |
| 5 | `web/templates/index.html` | BT-Icon dreistufig (grau/blau/grün) + `knownBtDevicesBox` |
| 6 | `setup_bt_audio.sh` | `pulse-access` Gruppe; `auth-group=pulse-access` in system.pa |
| 7 | `pidrive/VERSION` | Konsistent auf 0.9.14 (war 0.9.13 bei 0.9.14-final in main_core) |

**Geänderte Dateien:** `modules/dab.py`, `modules/audio.py`, `install.sh`,
`ipc.py`, `setup_bt_audio.sh`, `web/templates/index.html`, `VERSION`

---

### v0.9.13 — Diagnose erkennt Klinken-Fehler zuverlässig

**Motivation:** diagnose.py zeigte ✓ ALSA Sink auch wenn der Sink HDMI war.
`check_audio()` prüft jetzt die vollständige Kette: system.pa → ALSA → amixer → PA-Sinks → Routing.

**Geändert: `diagnose.py`**
- Prüft `/etc/pulse/system.pa` auf `device_id=1` (Klinke) — zeigt Fix-Kommando wenn fehlend
- Prüft `aplay -l` auf bcm2835 Headphones
- Prüft `amixer -c 1 sget PCM` auf Mute-Status
- `_sink_is_hdmi()`: erkennt HDMI per Name UND Card-Index (`.0.` = Card 0 = HDMI)
- Warnt + Fix-Kommando wenn Klinken-Sink in PulseAudio fehlt
- Warnt wenn Default Sink HDMI ist
- Kreuzvalidiert: `effective=klinke` vs. tatsächlicher Sink-Name

**Geänderte Dateien:** `diagnose.py`, `VERSION`

---

### v0.9.13 — Diagnose + v0.9.10 Root Cause Kein Ton: PulseAudio lud nur HDMI (device_id=0)

**Root Cause (endgültig):**
`setup_bt_audio.sh` schrieb `/etc/pulse/system.pa` mit nur `module-alsa-card device_id=0`
(= HDMI). Card 1 (bcm2835 Headphones = Klinke) existierte NIE als PulseAudio-Sink.

| # | Datei | Fix |
|---|---|---|
| 1 | `setup_bt_audio.sh` | `system.pa` lädt jetzt `device_id=0` (HDMI) + `device_id=1` (Klinke) |
| 2 | `install.sh` | Patcht laufendes `system.pa` falls `device_id=1` fehlt; setzt Default Sink |
| 3 | `modules/audio.py` | `_ensure_klinke_sink()` lädt Card 1 dynamisch via `pactl load-module` |
| 4 | `modules/audio.py` | `get_alsa_sink()` erkennt `.1.stereo-fallback` und `klinke_sink` |

**Geänderte Dateien:** `setup_bt_audio.sh`, `install.sh`, `modules/audio.py`, `VERSION`

---

### v0.9.9 — ALSA-Karten-Root-Cause

**Root Cause:**
Card 0 = HDMI, Card 1 = Headphones. Alle amixer-Befehle trafen HDMI.
Fix: `/etc/asound.conf` + `_get_headphone_card()` + `get_alsa_sink()` filtert HDMI.
*(Unvollständig — PulseAudio hatte immer noch keinen Card-1-Sink)*

---

### v0.9.8 — PCM-Unmute, BT-Connect-Lock, Scan-Polling

**Motivation:** Trotz korrektem Audio-Routing kein Ton. BT-Pairing schlägt bei jedem
Versuch fehl mit "not available". Beide Probleme sind durch Live-Logs eindeutig
diagnostiziert.

**Bugs behoben:**

| # | Datei | Root Cause | Fix |
|---|---|---|---|
| 1 | `modules/audio.py` | `numid=2` (PCM Playback **Switch**) war 0 = gemuted — Ton physisch abgeschaltet | `amixer sset 'PCM' 85% unmute` (name-basiert, alle Kernelversionen) |
| 2 | `modules/audio.py` | `numid=3` existiert auf Kernel ≥5.x nicht mehr (separate HDMI/Klinke-Karten) — Fehler in `/dev/null` versteckt | Name-basierte Befehle statt numid |
| 3 | `modules/bluetooth.py` | Nach `remove` ist Gerät in BlueZ unbekannt → 10s Mini-Scan oft zu kurz → trust/pair/connect sofort mit "not available" | Polling alle 2s bis 20s max; Abort wenn Gerät nach Scan nicht gefunden |
| 4 | `modules/bluetooth.py` | `repair()` + User "Verbinden" starten parallel 2× `connect_device()` → Race Condition in BlueZ | `threading.Lock()` (`_bt_connect_lock`) blockiert parallele Calls |
| 5 | `install.sh` | Boot-Schritt setzte nur `numid=3=1` (Routing), nicht PCM-Volume/Mute | `amixer sset 'PCM' 85% unmute` beim Installieren |

**Keylearning:**
- `amixer numid=X` ist instabil über Kernelversionen — immer name-basierte `sset`-Befehle verwenden
- Nach `bluetoothctl remove` muss das Gerät neu in BlueZ discovered werden bevor pair/trust/connect möglich ist
- Parallele BT-Connect-Threads durch fehlenden Lock waren latenter Bug seit v0.8.x

**Geänderte Dateien:** `modules/audio.py`, `modules/bluetooth.py`, `install.sh`, `VERSION`

---

### v0.9.7 — Audio-Fix krit., BT-Agent, Icon, Menü

**Motivation:** Kein Ton auf Klinke trotz korrekt gesetztem Routing. BT-Symbol immer grau.
Mehrere stille Bugs gefunden und behoben.

**Bugs behoben:**

| # | Datei | Bug | Fix |
|---|---|---|---|
| 1 | `modules/audio.py` | `set_default_sink()` verschob keine laufenden Streams → mpv auf altem Sink, kein Ton | `pactl move-sink-input` nach jedem Sink-Wechsel |
| 2 | `modules/audio.py` | ALSA PCM-Volume (numid=1) nie gesetzt → Hardware stumm | `amixer numid=1=340` in `_set_pi_output_klinke()` |
| 3 | `modules/audio.py` | `@DEFAULT_SINK@` leer wenn kein Default gesetzt → `volume_up/down` wirkungslos | Echten Sink-Namen via `_get_current_sink()` |
| 4 | `modules/audio.py` | `apply_startup_volume()` war definiert aber nie aufgerufen | Aufruf in `main_core.py` startup_tasks() |
| 5 | `main_core.py` | `audio_select` Trigger → `select_output_interactive()` existiert nicht → Crash | Ersetzt durch `menu_state.navigate_to("audio_out")` |
| 6 | `modules/bluetooth.py` | `_ensure_agent()` mit `communicate()` → bluetoothctl endet nie → Timeout → WARNING | `printf ... | bluetoothctl` Shell-Pipe |
| 7 | `modules/bluetooth.py` | BT-Scan 15s zu kurz für Kopfhörer im Pairing-Modus | 25s |
| 8 | `status.py` | `bt_on` (Adapter UP) nicht im S-Dict exportiert | `bt_on` ergänzt |
| 9 | `main_display.py` | BT-Icon nur grün wenn verbunden, kein Feedback für "Adapter AN" | Dreistufig: grau/blau/grün |
| 10 | `menu_model.py` | `bt_geraete` nach Info-Nodes → Cursor landet falsch nach Scan | `bt_geraete` direkt nach `bt_scan` |

**Neue Funktion:**
- `_get_current_sink()` in `audio.py` — ermittelt aktiven Sink (BT > ALSA)

**Geänderte Dateien:** `modules/audio.py`, `main_core.py`, `modules/bluetooth.py`,
`status.py`, `main_display.py`, `menu_model.py`, `VERSION`

---

### v0.9.6 — source_state shared, DAB-Debug persistent, BT-Mirrors vollständig

**Motivation:** Scan lieferte 0 Sender bei SNR 1–2 dB Innenraumempfang.
Log-Analyse: WAIT_LOCK=8s zu kurz; keine FIC-Diagnosedaten; fester Port 7979 (Konflikt mit Webdiagnose).

**modules/dab.py:**
- `scan_dab_channels()` vollständig konfigurierbar via settings.json:
  - `dab_scan_wait_lock` (Standard 20s): pro Kanal — bei SNR 3–5 dB werden 15–25s benötigt
  - `dab_scan_http_timeout` (Standard 4s): mux.json HTTP-Timeout
  - `dab_scan_port` (Standard 7981): getrennt von WebUI-Diagnose-Port 7979
  - `dab_scan_channels`: gezielte Kanäle z.B. `["11D","10A","8D"]`
- Neue Debug-Metriken pro Kanal: `ficcrc`, `lastfct0`, `rx_gain`
- `LOCK_KANDIDAT`-Warnung wenn SNR≥2 aber keine Services (WAIT_LOCK erhöhen)
- `_last_scan_diag` dict + `get_last_scan_diag()` für WebUI-Diagnose
- `_normalize_station()`: fehlende Felder ergänzen
- `play_by_name(name, S, service_id="")`: service_id-Matching vor Name-Matching
- Vollscan-Fallback nur bei Standard-Scan (nicht bei gezielten Kanälen)

**settings.py + config/settings.json:**
- Neue Defaults: `dab_scan_wait_lock=20`, `dab_scan_http_timeout=4`,
  `dab_scan_port=7981`, `dab_scan_channels=["11D","10A","8D","8B","11B"]`
- settings.json: ppm_correction=49 (aus Messung), dab_gain=-1 (AGC stabil)

**main_core.py:**
- Doppelter SCAN_START-Log entfernt
- `dab_scan`: `control_context="radio_dab_scan"` (trennt Scan von Wiedergabe)
- `dab_scan`: `source_state.begin/commit/end_transition` vollständig
- Neuer Trigger `dab_scan_channels:11D,10A,8D` für gezielten Scan
- DAB-Playback: `service_id` an `play_by_name()` übergeben

**modules/spectrum.py — NEU:**
- Prototyp für FM/Scanner-FastScan (Grundlage Phase 4)
- `capture_spectrum()`: rtl_sdr IQ-Snapshot → numpy FFT → dB → Peak-Erkennung
- `sweep_fm_band()`: FM-Band-Sweep 87.5–108 MHz, Peak-Kandidatenliste
- Nutzt RTL-SDR-Locking aus rtlsdr.py
- Kein Eingriff in DAB/FM/Scanner-Wiedergabe
- Voraussetzung: numpy (install.sh ergänzt)

**webui.py:**
- `GET /api/dab/scan/last`: letzte Scan-Metriken (snr, ficcrc, services pro Kanal)
- `GET/POST /api/dab/scan/settings`: DAB-Scan-Parameter lesen/speichern
- `POST /api/dab/scan/custom`: gezielten Scan per API starten
- `GET /api/spectrum/last`: letzten Spectrum-Snapshot laden
- `POST /api/spectrum/capture`: Spektrum aufnehmen (mode=single|fm_sweep)
- `dab_scan_channels:` in ALLOWED prefixes

**index.html:**
- Neues Panel "DAB+ Scan Einstellungen": WAIT_LOCK, HTTP Timeout, Port, Kanäle
- Gezielter Scan-Button mit direktem Channel-Input
- DAB-Scan-Diagnose: snr, ficcrc, services pro Kanal mit ✓/~/- Marker
- Neues Panel "Spektrum / FM FastScan (Prototyp)": Einzelmessung + FM-Sweep
- Peaks werden als Frequenz+dB aufgelistet

**install.sh:** numpy Installation ergänzt

---

**Scan-Empfehlung für Innenraum-/Fensterempfang:**
```bash
# Gezielte Kanäle mit erhöhter Wartezeit:
echo "dab_gain:-1" > /tmp/pidrive_cmd
echo "dab_scan_channels:11D,10A,8D,8B,11B" > /tmp/pidrive_cmd
# Im Log auf LOCK_KANDIDAT achten — zeigt welche Kanäle Signal haben
```

**Empfohlene settings.json Werte (Innenraum/schwach):**
- `dab_scan_wait_lock: 20` (oder 25–30 bei sehr schwachem Signal)
- `dab_gain: -1` (AGC — stabiler als manueller Wert)
- `dab_scan_channels: ["11D", "10A", "8D", "8B", "11B"]`

### v0.9.3 — DAB-Gain-Index-Fix, mux.json-Scan, State-Machine vollständig, Aufräumen

**Kritische Erkenntnis aus welle-cli Quellcode (rtl_sdr.cpp):**
- `welle-cli -g N` erwartet einen **GAIN-INDEX (0–28)**, KEIN dB-Wert!
- `"Unknown gain count40"` = Index 40 out-of-range (max Index=28)
- v0.9.2-Fix (`"40.2"`) war ebenfalls falsch — erst v0.9.3 übergibt Index 22 für 40 dB
- `-P` ist **kein PPM-Flag** in welle-cli, sondern Carousel/PAD-Verhalten → entfernt

**modules/dab.py:**
- `_RTL_GAIN_TABLE`: 29 Einträge, Index 0=0.0 dB bis Index 28=49.6 dB
- `_get_dab_gain()`: konvertiert dB → nächsten Index (40 dB → Index 22)
- `-P ppm` aus welle-cli-Kommando entfernt (falsches Flag)
- `scan_dab_channels()`: komplett neu via welle-cli Webserver + `mux.json`
  - startet `welle-cli -c CH -g IDX -C 1 -w 7979` pro Kanal
  - holt `http://127.0.0.1:7979/mux.json` nach 8s Lock-Zeit
  - strukturierte JSON-Daten: ensemble.label/id, service.sid/label/url_mp3, SNR
  - Regionalscan (7 Kanäle) + Vollscan-Fallback wenn < 3 Sender
  - service_id und ensemble werden in dab_stations.json gespeichert

**main_core.py — State-Machine vollständig:**
- `radio_stop` → `source_state.begin/commit/end_transition("idle")`
- `scan_up/down` → `source_state.begin/end_transition("scanner")`
- `scan_next/prev` → `source_state.begin/end_transition("scanner")`
- `dab_scan` übergibt `settings=settings` an scan_dab_channels()

**ipc.py — Audio-State aus Datei:**
- `_get_audio_effective()` + `_get_audio_reason()` lesen aus `/tmp/pidrive_audio_state.json`
- Beseitigt In-Prozess-Inkonsistenz zwischen Core und WebUI

**webui.py:**
- `get_source_state_debug()` + `source_state` in `/api/state` Response

**diagnose.py:**
- `check_source_state()`: zeigt source_current, bt_state, audio_route, boot_phase, transition

**install.sh:**
- Log-Verifikation mit Zeitstempel-Filter (verhindert alte Einträge als "neu")

**Aufräumen:**
- `Error_v0.8.25.md` entfernt (Debug-Analyse, kein Release-Dokument)
- `pidrive_debug.sh` (v0.6.0) entfernt — ersetzt durch pidrive_boot_debug.sh
- `systemd/pidrive.service` (alter monolithischer Service) entfernt
- `.gitignore`: settings.json kommentiert (Default-Datei bleibt im Repo)

---

**Screenshots welle-cli Webdiagnose (20.04.2026):**
- Kanal 12B: SNR=0.0, FIC CRC=45 → kein Lock, schlechter Empfang
- Kanal 15A: SNR=29.7, Freq corr=9 → Signal, aber kein Ensemble-Sync
- Kanal 13F: Gain=-1 (AGC), Freq corr=433 Hz → sichtbares Spektrum

PPM-Kalibrierung: interner Coarse-Corrector von welle-cli übernimmt Frequenz-Korrektur,
kein direkter CLI-Parameter nötig oder möglich.

### v0.9.2 — Settings-Migration, DAB-Gain-Fix, Diagnose-Bugfixes, DAB-Webdiagnose

**Motivation:** Code-Review v0.9.1 (externe GPT-Analyse + eigene Prüfung) ergab vier kritische Restprobleme.

---

**settings.py — vollständige Defaults (Checkliste Punkt 1+10):**
- `_DEFAULTS` jetzt vollständig: device_name, display_brightness, theme, spotify/webradio/dab enabled,
  fm_freq, fm_gain, dab_gain, scanner_gain, ppm_correction, scanner_squelch, scanner_vhf/uhf_freq,
  bt_last_mac/name/sink/pa_sink, last_source, last_fm/dab/web_station
- `ensure_settings_file()`: neue Funktion — schreibt settings.json beim Boot auf vollständige Defaults
- `save_settings()`: schreibt immer vollständigen Satz (Defaults + aktuelle Werte)

**config/settings.json — vollständige Initialdatei:**
- Alle 34 Keys vorhanden
- Startwerte: ppm_correction=55 (gemessen), scanner_squelch=10, fm_gain=30, dab_gain=40
- Verhindert dass Runtime-Panel im WebUI "–" zeigt

**main_core.py:**
- `ensure_settings_file()` beim Start aufgerufen — settings.json wird beim ersten Boot normalisiert

**modules/dab.py — DAB-Gain-Fix (Checkliste Punkt 9):**
- Kernproblem: welle-cli/RTL-SDR erwartet exakte diskrete Gain-Stufen (0.0, 0.9, 1.4, ... 49.6)
- `"Unknown gain count40"` im Log war klares Symptom: `40` ist keine gültige Stufe
- `_RTL_VALID_GAINS` Liste der 29 gültigen R820T Gain-Stufen
- `_get_dab_gain()` quantisiert auf nächste gültige Stufe: 40→40.2, 35→36.4, 49→49.6
- Format jetzt `"40.2"` statt `"40"`

**diagnose.py — Diagnose-Bugfixes (Checkliste Punkt 11):**
- Default-Sink: Fallback auf `pactl info` wenn `pactl get-default-sink` leer
- amixer numid=3: Parse mit `int(raw, 0)` — versteht 1, 0x1, 0x00000001 korrekt
- Behebt: `Pi Audio-Ausgang (amixer numid=3): Unbekannt (0x00])`

**webui.py — Runtime-Panel + DAB-Webdiagnose (Checkliste Punkt 2+6):**
- `get_settings_debug()` + `get_process_debug()`: neue Hilfsfunktionen
- `GET /api/runtime`: gibt aktive Settings + laufende rtl_fm/mpv Parameter zurück
- `GET /api/dab/diag?channel=11D&port=7979`: startet `welle-cli -c <CH> -C 1 -w <PORT>`
  Webserver-Diagnosemodus — Browser zeigt Ensemble, Signal, DLS, Slides
- `GET /api/dab/diag/stop`: stoppt welle-cli Webserver

**index.html — DAB Diagnose Button:**
- 🔍 DAB Diagnose Button: fragt nach Kanal, startet Webserver, öffnet Browser-URL
- ⏹ DAB Diag Stop: beendet Webserver
- `refreshRuntime()` JS jetzt backend-gestützt via `/api/runtime`

---

**Abgleich Checkliste (externe Prüfung) — was gefixt wurde:**

| # | Prüfpunkt | Vorher | Nachher |
|---|---|---|---|
| 10 | settings.json vollständig | ✗ nur 9 Keys | ✓ 34 Keys |
| 9 | DAB Gain korrekt | ✗ `Unknown gain count40` | ✓ quantisiert auf 40.2 |
| 11 | amixer Diagnose | ✗ `Unbekannt (0x00])` | ✓ int-Parse |
| 2 | Default Sink in Diagnose | ✗ leer | ✓ pactl info Fallback |
| 2 | Runtime-Panel WebUI | ✗ zeigt –  | ✓ /api/runtime |
| 6 | welle-cli Webdiagnose | ✗ nicht vorhanden | ✓ /api/dab/diag |

---

**Noch nicht gefixt (Folgeversionen):**
- Installer zeigt alte Version im Log (install.sh greift zu früh in Logfile)
- BT praktisch noch nicht verifiziert (Kopfhörer war aus)
- BT-Agent "default-agent nicht bestätigt" Warnung bleibt
- Sink-Input App/Binary/PID-Auflösung teilweise leer (webui.py pactl list sink-inputs parsing)

### v0.9.1 — Source-State vollständig, BT-Reconnect schneller

**main_core.py — source_state voll integriert:**
- `_run_station_switch()`: `begin_transition()` vor Quellenwechsel, `commit_source()` nach FM/DAB/Webradio-Start, `end_transition()` im finally
- `_stop_all_sources()`: `source_state.commit_source("idle")` am Ende

**bluetooth.py — source_state aware + schnellerer Reconnect:**
- Connect-Start: prüft `in_transition()` — bricht ab wenn Quellenwechsel läuft
- Erfolg/Fehler: setzt `bt_state = connected/failed`, `audio_route = bt`
- Auto-Reconnect Watcher: Startpause 15s → 6s (schneller nach Boot)
- Intervall 30s → 12s getrennt / 20s verbunden
- Watcher überspringt Reconnect-Versuch wenn Quellen-Transition läuft

**scanner.py — source_state aware:**
- Scan-Schleifen brechen ab wenn `in_transition()` True
- `play_freq()` setzt `commit_source("scanner")` nach erfolgreichem Start

**webui.py:**
- `scanner_gain` in `/api/gain` Response ergänzt

### v0.9.0 — Audio-Fix PULSE_SERVER, Source-State-Machine, Scanner-PPM, Boot-Debug

**Hauptmotivation:** Log-Analyse v0.8.25 zeigte `pactl sink-inputs: leer` trotz laufendem mpv.
Root-Cause: `pidrive_core.service` ohne `PULSE_SERVER` → mpv als root landet nicht am System-PulseAudio.

**systemd/pidrive_core.service — KRITISCHER FIX:**
- `Environment=PULSE_SERVER=unix:/var/run/pulse/native` eingetragen
- Alle PulseAudio-Quellen (Webradio, Spotify, BT) nutzen System-PulseAudio-Socket.
  DAB/FM/Scanner laufen ALSA-direkt — kein PulseAudio.
- `After=bluetooth.service` ergänzt

**modules/source_state.py — NEU:**
- Zentrale Source-State-Machine: verhindert gleichzeitige FM+Scanner+BT-Aktivität
- Drei getrennte State-Ebenen: source_current, audio_route, bt_state
- `begin_transition()` / `commit_source()` / `end_transition()` — serialisierte Quellenwechsel
- Timeout-Guard gegen hängende Transitions (8s)
- boot_phase: cold_start → restore_bt → restore_source → steady

**scanner.py — PPM/Gain/Squelch vollständig verdrahtet:**
- `_get_ppm()` / `_get_gain()` aus settings.json
- `_detect_signal_fast()` + `_detect_signal_confirm()` + `play_freq()` nutzen alle drei Werte
- Scanner-mpv jetzt mit `--ao=pulse` (war ohne, kein Ton über PulseAudio)
- `scanner_gain:-1` Trigger in main_core.py

**settings.py:**
- `scanner_gain: -1` als neues Default
- Kommentar: gemessener RTL2838-PPM ~52

**modules/audio.py:**
- `apply_startup_volume()` — liest `settings["volume"]` beim Boot und setzt Default-Sink
- `volume_up()` speichert Lautstärke persistent nach settings.json

**main_core.py:**
- `source_state` Import + Initialisierung beim Boot
- `startup_tasks()`: apply_startup_volume() vor Boot-Resume
- `_stop_all_sources()`: `source_state.commit_source("idle")`
- `scanner_gain:N` Trigger

**webui.py:**
- `get_settings_debug()` / `get_process_debug()` — neue Hilfsfunktionen
- `GET /api/runtime` — aktive Settings + laufende rtl_fm/mpv Parameter
- Audio Debug: Warnung wenn PulseAudio aktiv aber keine Sink-Inputs + laufende Player

**diagnose.py:**
- `check_processes()` — zeigt alle relevanten Prozesse
- Warnung wenn mpv läuft aber keine PulseAudio Sink-Inputs → PULSE_SERVER-Hinweis

**index.html:**
- Runtime-Panel mit allen aktiven Settings + laufenden Prozessparametern
- Scanner Gain Schnellbuttons (Auto / 30dB)
- `refreshRuntime()` JS-Funktion

**pidrive_boot_debug.sh — NEU:**
- Boot-Debug-Snapshot: Services, PULSE_SERVER-Check, Prozesse, PulseAudio, BT, RTL-SDR, Settings
- Speichert nach `/tmp/pidrive_boot_debug_DATUM.log`

**systemd/pidrive_boot_debug.service — NEU:**
- Oneshot-Service: startet pidrive_boot_debug.sh nach pidrive_core
- Optional: `systemctl enable pidrive_boot_debug.service`

---

**NICHT implementiert (Dokumentation):**

| Patch | Grund |
|---|---|
| bluetooth.py Vollrewrite | GPT-Patch nicht mit existierender bt_backup-Logik kompatibel; BT-Verbesserungen folgen in v0.9.1 |
| audio.py Vollrewrite | Zu riskant ohne vollständigen Kontext; gezielte Patches stattdessen |
| main_core.py source_state voll integriert | Nur Boot-Phase + _stop_all_sources; vollständige Integration in v0.9.1 |
| BT Auto-Reconnect State-Events | Folgt nach Praxistest mit PULSE_SERVER-Fix |

### v0.8.25 — BT-Pairing-Backup, PPM-Fix
**Probleme aus Log v0.8.24:**
- BT `not available` nach Reboot — BlueZ-DB leer, Pairing verloren
- PPM-Kalibrierung: Regex fand kumulativen PPM-Wert nicht (`cumulative PPM: N` in rtl_test-Ausgabe)

**modules/bt_backup.py — NEU:**
- `backup()`: kopiert /var/lib/bluetooth/ → config/bt_pairs/
- `restore()`: kopiert zurück + `systemctl restart bluetooth`
- `has_backup()` / `backup_info()`: Status-Abfrage
- BlueZ-Datenbank enthält alle Pairing-Keys (Link Keys, UUIDs, Profile)

**bluetooth.py — Auto-Backup nach Connect:**
- Nach erfolgreichem BT-Connect: automatisches Backup der Pairing-Daten
- Einmal verbunden → Keys gesichert → Restore nach Reboot möglich

**main_core.py — Auto-Restore beim Boot:**
- Wenn `bluetoothctl paired-devices` leer + Backup vorhanden → automatisches Restore
- bluetoothd wird neu gestartet → Pairing sofort verfügbar
- Triggers: `bt_backup` + `bt_restore` (manuell per WebUI)

**webui.py — BT-Backup API:**
- `GET /api/bt/backup`: Status, Datum, gesicherte Geräte
- `bt_backup` + `bt_restore` in ALLOWED_COMMANDS

**index.html — BT-Backup Panel:**
- Zeigt Backup-Status, Datum, gesicherte Geräte
- 💾 Jetzt sichern + 🔄 Wiederherstellen Buttons
- Erklärung: wann sichern (nach Pairing), wann restore (nach Reboot)

**webui.py — PPM-Kalibrierung Fix:**
- rtl_test gibt `current PPM: N` und `cumulative PPM: N` aus
- Methode 1: `cumulative PPM` (stabilster Wert nach 30s)
- Methode 2: Median der `current PPM` Werte
- Methode 3: Samplerate-Berechnung als Fallback
- Korrekte Hinweise wenn Wert nicht erkannt

### v0.8.24 — amixer Boot-Fix, Diagnose erweitert
**Log-Analyse v0.8.23:**
- Klinke kein Ton: `get_mpv_args()` wurde beim Boot-Resume nicht aufgerufen → kein `amixer numid=3 1` → Pi-Ausgang blieb auf HDMI
- BT `not available`: BlueZ-Datenbank leer nach Reboot — manuelles Neu-Pairing nötig
- Diagnose zeigte Audio/BT/RTL-SDR nicht → jetzt ergänzt

**main_core.py — amixer explizit beim Boot:**
- Vor Boot-Resume: `_set_pi_output_klinke()` wenn audio_output != bt/hdmi
- Verhindert „kein Ton auf Klinke" wenn play_station() ohne vorherigen get_mpv_args()-Aufruf startet
- Log: `Boot: amixer Klinke aktiviert (audio_output=...)`

**diagnose.py — drei neue Sektionen:**
- `check_audio()`: PulseAudio-Status, Sinks, Default-Sink, Sink-Inputs, amixer numid=3 Wert, Audio-State-File
- `check_bluetooth()`: bluetooth.service, hci0, gepaarte Geräte, BT-Agent, A2DP-Sink
- `check_rtlsdr()`: USB-Erkennung, Tools (rtl_fm/rtl_test/welle-cli), RTL-State, PPM/Squelch aus settings

**Sofort-Fix bei BT `not available` (manuell per SSH):**
```bash
bluetoothctl
  power on; agent on; default-agent; scan on
  # warten bis HD 4.40BT erscheint
  pair 00:16:94:2E:85:DB
  trust 00:16:94:2E:85:DB  
  connect 00:16:94:2E:85:DB
```

### v0.8.23 — WebUI HTML/JS Bugfixes (Gemini-Review)
**Nach Gemini-Code-Review — verifizierte echte Bugs:**

**index.html — ID-Mismatch behoben:**
- HTML hatte `id="debugBar"`, JS suchte `getElementById('statusBar')`
- getElementById('statusBar') gibt `null` zurück → Status-Bar wurde nicht aktualisiert
- Fix: HTML-ID auf `id="statusBar"` geändert

**index.html — copyLogToClipboard event.target behoben:**
- `onclick="copyLogToClipboard()"` ohne event-Übergabe
- Funktion nutzte globales `event.target` — in modernen Browsern deprecated/undefined
- Fix: `onclick="copyLogToClipboard(event)"` + `function copyLogToClipboard(evt)` + `evt.target`

**Gemini-Punkte die KEIN echtes Problem sind:**
- Issue 2 (HTML-Struktur): `</section>`+`<section>` sind korrekte Schachtelung, kein Bug
- Issue 5 (nodeClick): `await` in `for`-Schleife garantiert sequentielle Ausführung
- Issue 6 (listOverlay): display:none ist korrekt — das Overlay wird per Jinja2 und Core-IPC gesteuert

### v0.8.22 — WebUI JavaScript Bugfix (Block 1 Syntax Error)
**Ursache:**
- Die `loadAllLogs()` Funktion (v0.8.17 eingebaut) enthielt echte Zeilenumbrüche
  in JavaScript Single-Quoted-String-Literalen statt `\n` Escape-Sequenzen
- JavaScript-Syntax: `'text\n'` (Escape) ✓ vs `'text` + Newline + `'` (Literal) ✗
- Dieser Syntax-Fehler deaktivierte den gesamten ersten `<script>`-Block
- Betroffen: `sendCmd()`, `loadLogs()`, `runDiagnose()`, alle Steuerungsbuttons
- Nicht betroffen: Blöcke 2–4 (Audio, Gain, RTL-Reset) — diese liefen weiter

**Symptom:** Steuerungsbuttons taten nichts, Diagnose-Buttons reagierten nicht,
RTL-Reset und PPM-Kalibrierung funktionierten noch (eigene Script-Blöcke).

**Fix:**
- `loadAllLogs()` komplett neu geschrieben — kein String-Literal mit Newline mehr
- Alle 4 Script-Blöcke mit Node.js `--check` verifiziert: Syntax OK

**v0.8.21 Fix (Icons) ist ebenfalls enthalten:**
- Jinja2 icons-Dict: HTML-Entities (`&#x25B8;`) → direkte Unicode-Zeichen (`▸`)

### v0.8.21 — Display-Vorschau Bugfix (HTML-Entity-Double-Escape)
**Bug:** Jinja2-Template zeigte `&#x25B8;Jetzt läuft` statt `▸Jetzt läuft` in der Display-Vorschau.
**Ursache:** `{% set icons = {"folder":"&#x25B8;",...} %}` — Jinja2 auto-escaped `&` → `&amp;`, Browser zeigte Literal-Text.
**Fix:** Direkte Unicode-Zeichen `▸♪→◉ℹ±` statt HTML-Entity-Strings in der icons-Dict.

### v0.8.20 — PPM-Kalibrierung verbessert
**Problem in v0.8.18:** rtl_test -p gibt keinen direkten "X ppm"-Wert aus,
Kalibrierungsbutton fand deshalb oft nichts und zeigte keine Hilfe.

**webui.py — /api/rtlsdr/calibrate verbessert:**
- Methode 1: Samplerate-Messung aus rtl_test ("real sample rate: XXXXXXX")
  → Formel: ppm = (gemessen - 2048000) / 2048000 * 1e6
- Methode 2: direkter ppm-Wert aus Ausgabe (neuere rtl-sdr Versionen)
- Gibt jetzt `method` + `hints` zurück — erklärt was gefunden wurde
- Hinweise bei nicht erkanntem Wert: manuell ±10 ppm schrittweise testen

**index.html — Kalibrierungsbutton und Panel:**
- Kalibrierungsergebnis zeigt jetzt: Wert + Messmethode + Hinweisliste
- Panel-Text erklärt Was/Wie/Wann der PPM-Wert wirkt
- Klarer: "0 = deaktiviert", "nach Übernehmen neu abspielen"

### v0.8.19 — GPIO-Tasten, Boot-Resume Webradio
**Offen seit langem, jetzt umgesetzt:**
- GPIO-Tasten am Joy-IT Display waren komplett nicht implementiert
- Boot-Resume startete nur FM/DAB, nicht Webradio
- Beim Einschalten im Auto: keine automatische Wiederaufnahme der letzten Webradio-Station

**modules/gpio_buttons.py — NEU:**
- Neues Modul für Key1 (GPIO23), Key2 (GPIO24), Key3 (GPIO25)
- Key1 → `up`, Key2 → `enter`, Key3 → `back` (File-Trigger)
- Polling-Loop (50ms) in Daemon-Thread — keine Interrupt-Konflikte mit SPI-Display
- 200ms Debounce verhindert Mehrfachauslösung
- Graceful Fallback wenn RPi.GPIO nicht installiert (kein Absturz)
- `start()` / `stop()` / `is_active()` API

**main_core.py — GPIO-Start + erweiterter Boot-Resume:**
- `_gpio_buttons.start()` beim Core-Start — Log zeigt ob Tasten aktiv
- Boot-Resume nutzt jetzt `last_source` (fm/dab/webradio) als primäres Kriterium
- Webradio: `last_web_station` mit name + url + genre wird beim Start wiederhergestellt
- Fallback-Logik: wenn `last_source` fehlt → FM → DAB → nichts

**settings.py — neue Felder:**
- `last_source: ""` — letzte aktive Quelle (fm/dab/webradio)
- `last_web_station: null` — dict mit name/url/genre der letzten Webradio-Station

**fm.py / dab.py / webradio.py — Persistenz:**
- Alle drei schreiben `last_source` nach settings.json bei erfolgreichem Play
- webradio.py speichert zusätzlich `last_web_station` mit name + url

**install.sh:**
- `pip3 install RPi.GPIO` wird automatisch mit installiert

### v0.8.18 — PPM-Korrektur, Squelch-Einstellung, Empfangsoptimierung
**Hintergrund:**
- RTL2838-Stick hat typisch 20–100 ppm Quarzfehler → FM-Stereo unstabil, DAB-Sync schlechter
- Scanner Squelch war fest auf 25 (nicht konfigurierbar)
- Kein WebUI-Weg zur Frequenzkorrektur oder Squelch-Anpassung

**settings.py — neue Felder:**
- `ppm_correction: 0` — Frequenzkorrektur in ppm (0 = aus)
- `scanner_squelch: 25` — Squelch-Schwelle (0=offen, 25=Standard, 10=empfindlich)

**fm.py — PPM-Korrektur:**
- `rtl_fm` bekommt `-p PPM` Parameter wenn `ppm_correction != 0`
- Log: "FM play: PPM-Korrektur aktiv: N ppm"

**dab.py — PPM-Korrektur:**
- `welle-cli` bekommt `-P PPM` Parameter wenn `ppm_correction != 0`
- Verbesserter DAB-Empfang bei PPM-Fehler des Sticks

**scanner.py — dynamischer Squelch:**
- `_get_squelch()`: liest `scanner_squelch` aus settings.json
- Fast-Detection: squelch = max(5, configured_squelch//2) — halbe Schwelle für Erstdetektion
- Confirm-Detection: squelch = configured_squelch — volle Schwelle zur Bestätigung

**main_core.py — Trigger:**
- `ppm:N` → setzt `ppm_correction=N`, speichert, Progress-Feedback
- `squelch:N` → setzt `scanner_squelch=N` (0–50), speichert

**webui.py:**
- `/api/gain` gibt jetzt auch `ppm_correction` + `scanner_squelch` zurück
- `/api/rtlsdr/calibrate`: 30s `rtl_test -p` → schlägt PPM-Wert vor

**index.html — PPM + Squelch Karten im Gain-Panel:**
- PPM-Karte: Schnellbuttons (0/±10/±25/±50), Custom-Input, 🔬 Kalibrieren-Button
- Kalibrieren: startet rtl_test, zeigt empfohlenen Wert mit "Übernehmen"-Link
- Squelch-Karte: Buttons 0/10/15/20/25/35 mit Erklärungen

### v0.8.17 — WebUI-Kompakt, Phase 2 State, PulseAudio Switch-on-Connect
**Aus WebUI-Feedback und Phase 2 Planung:**
- Steuerungs-Buttons belegten zu viel Platz (4 Spalten, großes Padding)
- Kein "Alle Logs auf einmal" Button mit Copy-to-Clipboard
- Phase 2 `control_context` State Machine noch nicht gestartet
- PulseAudio BT-Auto-Routing benötigte manuelles Sink-Wechseln

**style.css — Button-Grid kompakter:**
- `button-grid`: 4 → 6 Spalten, Padding 12px → 8px, font-size 15px → 13px
- `tab-buttons`: flex-wrap statt grid, 6px/10px Padding → kompakte Log-Buttons
- Responsive: 1100px→4 Spalten, 700px→3 Spalten (war 2/1)

**index.html — "📋 Alle" + "⎘ Copy" Buttons:**
- `📋 Alle`: lädt Core Log + App Log + Core Status + Diagnose parallel (Promise.all)
  Zusammengefasst mit Timestamps in einem Block, fertig zum Kopieren
- `⎘ Copy`: kopiert logOutput-Inhalt in Zwischenablage
  Fallback auf `execCommand('copy')` für ältere Browser
  Button zeigt "✓ Kopiert!" kurz als Bestätigung

**ipc.py + main_core.py + webradio/fm/dab.py — Phase 2 control_context:**
- Neues Feld `control_context` in `write_status()`: idle | radio_web | radio_fm | radio_dab | radio_scanner | spotify | library
- Wird in `_stop_all_sources()` auf `idle` zurückgesetzt
- Wird in webradio/fm/dab beim Start auf den jeweiligen Kontext gesetzt
- Grundlage für Phase 2 explizite Zustandsmaschine
- Sichtbar in WebUI Status-JSON und per AVRCP-Trigger lesbar

**setup_bt_audio.sh — module-switch-on-connect:**
- `load-module module-switch-on-connect` in system.pa ergänzt
- PulseAudio wechselt automatisch auf BT-Sink wenn A2DP verbunden wird
- Fallback auf Klinke wenn BT trennt — kein manuelles Routing-Script nötig
- Entspricht der empfohlenen Zielarchitektur: BT = Primary, Klinke = Fallback

### v0.8.16 — RTL-SDR USB-Reset, BT-Auto-Reconnect aktiv, Lautstärke-Fix
**Analyse aus v0.8.15 Log:**
- RTL-SDR Stick nach Scanner/Gain-Nutzung aus USB-Subsystem verschwunden (lsusb leer)
- Reboot war nötig — jetzt per WebUI behebbar ohne Reboot
- Lautstärke-Anzeige zeigte „–" bei BT-Sink (pactl get-sink-volume gab leere Ausgabe)
- Doppeltes Gain-Log (custom log.info + generischer TRIGGER-Handler)
- BT Auto-Reconnect Watcher läuft stabil im Hintergrund

**rtlsdr.py — `usb_reset()`:**
- Neue Funktion `usb_reset()`: RTL-SDR USB-Reset ohne Reboot
- Ablauf: alle rtl_fm/welle-cli killen → Lock/State bereinigen → sysfs authorized=0/1 Cycle
- Fallback auf `usbreset 0bda:2838` wenn sysfs-Path nicht gefunden
- Prüft nach Reset ob Stick wieder erkannt wird, schreibt Diagnosedatei neu

**main_core.py — `rtlsdr_reset` Trigger:**
- Neuer Trigger `rtlsdr_reset`: startet `usb_reset()` im Hintergrund
- Progress-Feedback: "USB-Reset läuft..." → "Reset OK — Stick erkannt ✓" oder Warnung
- Doppeltes Gain-Log entfernt (custom log.info + TRIGGER-Handler waren redundant)

**webui.py — `/api/rtlsdr/reset` + Lautstärke-Fix:**
- `POST /api/rtlsdr/reset`: schreibt `rtlsdr_reset` Trigger, gibt sofort Antwort
- `rtlsdr_reset` in ALLOWED_COMMANDS eingetragen
- `/api/volume`: Fallback auf `pactl list sinks` wenn `get-sink-volume` leer (BT-Sink)

**index.html — RTL-SDR Reset Button:**
- Roter „⚡ RTL-SDR Reset" Button neben „🔄 Passive Diagnose"
- Button disabled während Reset läuft, zeigt Status-Feedback
- Nach 7s automatisch Passive Diagnose neu laden

### v0.8.15 — BT-AuthFix, Gain-WebUI, Auto-Reconnect
**Analyse aus v0.8.14 Log:**
- `Paired: no` + `org.bluez.Error.AuthenticationFailed` bei jedem pair-Versuch
- Pi hat nach Reboot keine Pairing-Keys mehr, Kopfhörer aber noch alte Keys
- connect() schlug deshalb strukturell immer fehl
- Gain (FM/DAB) und Lautstärke waren im WebUI nicht sichtbar/steuerbar
- BT Auto-Reconnect (Kopfhörer später einschalten) fehlte komplett

**bluetooth.py — AuthenticationFailed strukturell beheben:**
- Vor connect: `bluetoothctl info <mac>` prüft `Paired: no` → automatisches `remove` + frisches Pairing
- Bei `org.bluez.Error.AuthenticationFailed` im pair-Schritt: `remove` + Hinweis "Pairing-Modus nötig"
- Verhindert endlose Fehlversuche mit inkompatiblen Keys

**bluetooth.py — BT Auto-Reconnect Watcher:**
- `start_auto_reconnect()`: Hintergrund-Thread startet mit Core, prüft alle 30s
- Wenn letztes Gerät erreichbar (`Connected: no` aber BlueZ kennt es) → `connect` versuchen
- Bei Erfolg: Audio-Routing auf BT umschalten, Status aktualisieren
- Phase 3 Feature: "Kopfhörer wird nach PiDrive-Start eingeschaltet → verbindet automatisch"

**settings.py + fm.py — FM Gain:**
- `fm_gain: -1` als Default (Auto AGC) in settings
- `rtl_fm` Befehl nutzt `-g GAIN` wenn fm_gain != -1
- Separate Einstellung von `dab_gain` — FM und DAB brauchen unterschiedliche Werte

**main_core.py — Gain-Trigger:**
- `fm_gain:-1` / `fm_gain:30` → setzt settings.fm_gain, speichert, Progress-Feedback
- `dab_gain:-1` / `dab_gain:35` → analog für DAB

**webui.py — /api/gain + /api/volume:**
- `/api/gain`: gibt fm_gain + dab_gain aus settings zurück
- `/api/volume`: gibt PulseAudio Default-Sink-Lautstärke zurück

**index.html — Gain & Lautstärke Panel:**
- Neues Panel "🎚️ Lautstärke & Empfang (Gain)"
- Lautstärke: aktueller Wert + ▲/▼ Buttons (+5%/-5%)
- FM Gain: Auto/10/20/30/40/49 dB Buttons mit Erklärung
- DAB Gain: gleiche Buttons + Hinweis (DAB braucht oft mehr als FM)
- Auto-Refresh beim Laden

### v0.8.14 — Klinke-Audio-Fix, BT-Agent-Fix
**Analyse aus v0.8.13 Log:**
- mpv lief korrekt mit --ao=pulse auf alsa_output.0.stereo-fallback
- Kein Ton weil Pi-Ausgang physisch auf HDMI statt Klinke stand
- BT-Agent "No agent is registered" bei JEDEM Connect-Versuch (struktureller Bug)
- Kopfhörer war nicht erreichbar (not available = ausgeschaltet)

**audio.py — Pi-Klinke physisch aktivieren (amixer):**
- `_set_pi_output_klinke()`: `amixer -c 0 cset numid=3 1` → Klinke
- `_set_pi_output_hdmi()`: `amixer -c 0 cset numid=3 2` → HDMI
- `get_mpv_args()`: ruft je nach effective klinke/hdmi den passenden amixer-Befehl
- `set_output()`: setzt amixer synchron beim manuellen Ausgabewechsel
- Erkannte Probleme in install.sh: Audio-Ausgang auch beim Install aktivieren

**bluetooth.py — BT-Agent strukturell gefixt:**
- Problem: _btctl() startet pro Befehl eigenen Subprocess → Agent stirbt sofort
- Fix: _ensure_agent() nutzt jetzt einen einzigen `bluetoothctl`-Prozess mit stdin-pipe
- agent + default-agent werden in einem Aufruf abgesetzt → Agent bleibt registriert
- Fallback auf "agent on" wenn "NoInputNoOutput" nicht klappt

**install.sh — Klinke beim Install aktivieren:**
- `amixer -c 0 cset numid=3 1` wird nach Raspotify-Konfiguration gesetzt
- Stellt sicher dass Pi beim ersten Start korrekt auf Klinke routet

### v0.8.13 — Audio State File, Scanner-Guard, BT-Fix, Status-Sync
**Probleme aus v0.8.12 Log-Review:**
- Audio Debug Cockpit zeigte leere Werte (`Default Sink –`, `keine Inputs`)
  obwohl `mpv --ao=pulse` real lief (WebUI las falschen Prozesszustand)
- Quellenstatus lief auseinander: RTL-Diagnose zeigte DAB, Status zeigte SCANNER
- BT-Connect scheiterte während laufendem Scanner-Betrieb
- Scanner überschrieb Status nach Quellenwechsel weiter

**audio.py — Audio-State-File (`/tmp/pidrive_audio_state.json`):**
- `_write_audio_state()`: schreibt letzte Entscheidung atomar nach `/tmp/pidrive_audio_state.json`
- `read_last_decision_file()`: liest shared state prozessübergreifend
- WebUI kann jetzt echte Core-Audio-Entscheidung lesen, nicht eigenen Modulzustand

**webui.py — Audio Debug liest aus Datei statt Modulzustand:**
- `get_audio_debug()` nutzt `read_last_decision_file()` statt `get_last_decision()`
- `pactl get-default-sink` Fallback: bei leerer Ausgabe wird `pactl info` ausgewertet
- Audio Debug Cockpit zeigt jetzt korrekte Core-Entscheidung

**scanner.py — Scan-Abort-Flag:**
- `_scan_abort` Flag: wird in `stop()` gesetzt, in `scan_next()`/`scan_prev()` zurückgesetzt
- Guards in `_scan_list()` und `_scan_range()`: brechen Scan ab wenn `radio_type` wechselt
- Scanner-Scan kollidiert nicht mehr mit FM/DAB/Webradio-Wechsel

**bluetooth.py — Scanner stoppen + Disconnect vor Connect:**
- `connect_device()`: stoppt Scanner wenn aktiv, bevor BT-Connect startet
- `disconnect` vor neuen Connect-Versuchen: saubererer Verbindungsaufbau
- BT-Connect-Fehler durch parallelen RTL-SDR-Betrieb reduziert

**main_core.py — Status-Felder nach Quellenwechsel leeren:**
- `_stop_all_sources()`: setzt `radio_playing`, `radio_station`, `radio_name`, `radio_type` auf `""`
- Verhindert stale State: alter Quellstatus bleibt nicht mehr nach Wechsel stehen

**install.sh — WebUI Import-Smoke-Test:**
- Nach main_core-Import-Test jetzt auch `import webui` geprüft
- Verhindert dass stille Strukturfehler wie der v0.8.12-WebUI-Bug unentdeckt bleiben

### v0.8.12 — Audio Debug Cockpit, Versionsstrings, Diagnose-Fix
**diagnose.py — Versionsstring gefixt:**
- War noch `v0.7.10` → jetzt `v0.8.12`
- Diagnose-Ausgabe im Installer und manuell korrekt

**main_core.py / main_display.py — Versionsstrings:**
- Beide bereits in v0.8.11 auf v0.8.11 gesetzt, jetzt auf v0.8.12

**webui.py — Audio Debug Cockpit (`get_audio_debug()`):**
- Neue Funktion `get_audio_debug()` mit vollständiger Audio-Sicht
- PulseAudio-Status, Default-Sink, alle Sinks (Typ: bt/alsa/hdmi/other)
- Sink-Inputs kurz (`pactl list sink-inputs short`)
- Sink-Input Details (`pactl list sink-inputs`): Application Name, Process Binary, PID, Media Name
- `/api/audio` delegiert jetzt komplett an `get_audio_debug()`
- `build_view_model()` enthält `audio_debug` für Server-Side-Rendering
- **Bugfix: `def build_view_model():` fehlte → WebUI-Absturz behoben**

**index.html — Audio Debug Cockpit Panel:**
- Panel umbenannt: "Audio Routing Debug" → "Audio Debug Cockpit"
- Neue rechte Spalte: Sink-Inputs-Tabelle mit App/Binary/PID (mpv/librespot hervorgehoben)
- Neue Sinks-Liste mit Default-Sink-Marker (◀ default)
- JS `refreshAudio()` vollständig neu: rendert Tabellen dynamisch, kein JSON-Dump mehr

**audio.py — Strict Mode (kein ALSA-Fallback):**
- `get_mpv_args()`: bei inaktivem PulseAudio kein stiller Fallback auf `--ao=alsa` mehr
- `effective="none"`, `reason="pulseaudio_inactive"` → klar sichtbar in WebUI/Log
- Zielarchitektur Option B damit wirklich hart: ein Pfad, kein zweiter

**fm.py / dab.py / webradio.py — Strict Mode Guards:**
- Alle drei prüfen nach `get_mpv_args()` die letzte Audio-Entscheidung
- Bei `pulseaudio_inactive` oder `effective=none`: Abbruch statt blindem Start
- Log: `FM/DAB/WEB strict-mode: Abbruch ... reason=pulseaudio_inactive`

**pidrive_car_only_cleanup.sh — gehärtet:**
- User-PulseAudio/PipeWire werden jetzt wirklich beendet: `pkill -9` nach `systemctl --user stop`
- `loginctl disable-linger` verhindert Auto-Start der User-Session
- User-Unit-Overrides: `/home/pi/.config/systemd/user/` mit maskierten Overrides
- `XDG_RUNTIME_DIR` und `DBUS_SESSION_BUS_ADDRESS` korrekt gesetzt für `--user` Befehle

**install.sh — Raspotify auf zentralen PulseAudio-Pfad:**
- `LIBRESPOT_DEVICE=default` statt `hw:1,0` — nutzt PulseAudio Default-Sink
- `PULSE_SERVER=unix:/var/run/pulse/native` in `raspotify.service` eingetragen
- Spotify läuft jetzt auf demselben zentralen Audio-Pfad wie FM/DAB/Webradio

### v0.8.11 — Audio-Architektur Option B, DAB Fix, Car-Only Cleanup
**Zielarchitektur Option B — Einheitliches Audio über systemweiten PulseAudio:**
- Alle Audioquellen (FM, DAB, Webradio, Scanner) laufen nun über denselben Pfad
- Kein Mischbetrieb mehr: kein aplay direkt, kein rtl_fm|aplay Sonderpfad
- Klinke / BT / HDMI sind ab jetzt nur noch PulseAudio-Sink-Entscheidungen

**audio.py — Komplettes Rewrite:**
- Zentraler Audio-Routing-Entscheider für alle Quellen
- `get_mpv_args()` gibt immer `["--ao=pulse"]` zurück
- Sink-Auswahl via `set_default_sink()` im systemweiten PulseAudio
- `get_bt_sink()` / `get_alsa_sink()` / `get_hdmi_sink()` — Sink-Erkennung
- `get_last_decision()` — letzte Routing-Entscheidung für WebUI-Debug
- Fallback auf ALSA wenn PulseAudio inaktiv

**fm.py — aplay-Sonderpfad entfernt:**
- `play_station()`: kein `if _is_bt` mehr, immer `mpv --ao=pulse`
- FM läuft jetzt gleich wie Webradio und DAB
- Entscheidung Klinke/BT liegt jetzt sauber in audio.py

**dab.py — welle-cli `-o -` Bug gefixt:**
- welle-cli 2.2 kennt `-o -` nicht → `invalid option -- 'o'`
- Korrekte Syntax: `-p PROGRAMMNAME` (gibt Audio nach stdout)
- DAB funktioniert jetzt mit welle-cli 2.2-1

**webui.py + index.html — Audio Routing Debug Panel:**
- Neuer API-Endpoint `/api/audio`: PulseAudio-Status, Sinks, letzte Entscheidung
- Neues "Audio Routing Debug" Panel in der WebUI
- Zeigt: PulseAudio aktiv?, Default Sink, BT A2DP Sink, ALSA Sink
- Zeigt: requested / effective / reason / source der letzten Routing-Entscheidung

**Versionsstrings gefixt:**
- `main_core.py`: war `v0.8.6` → jetzt `v0.8.11`
- `main_display.py`: war `v0.8.9` → jetzt `v0.8.11`

**pidrive_car_only_cleanup.sh — Neues System-Cleanup-Script:**
- Deaktiviert Desktop-Dienste: ModemManager, ofono, dundee, cups, cups-browsed, snapd
- Deaktiviert User-Audio-Stack: PipeWire + User-PulseAudio für Benutzer pi
- Nur systemweiter PulseAudio-Daemon bleibt aktiv
- Beendet Altprozesse: rtl_fm, welle-cli, mpv, aplay, bluetoothctl scan
- Bereinigt RTL-SDR-State, Python-Cache, Temp-Dateien
- Startet PiDrive-Dienste sauber neu

**install.sh — Optionaler Car-Only Cleanup:**
- Nach Installation: "Car-Only Cleanup jetzt ausführen? [j/N]" mit 15s Timeout
- Führt pidrive_car_only_cleanup.sh bei Zustimmung aus
- Sonst: Hinweis auf manuelle Ausführung

### v0.8.10 — FM Race-Fix, DAB Gain, BT Agent, Cleanup
**rtlsdr.py — `wait_until_free()` (FM Race Condition Fix):**
- Neue Funktion wartet aktiv bis RTL-SDR wirklich frei ist (Prozesse + Lock)
- Verhindert Race Condition beim schnellen FM→FM Senderwechsel
- Timeout 2.5s mit 50ms Intervall — kurz genug für UX, lang genug für sichere Freigabe

**fm.py — deterministischer stop() + wait_until_free in play_station():**
- `play_station()`: ruft `reap_process()` auf, dann `wait_until_free()` vor Start
- Zweistufig: erst warten, bei Timeout harter Cleanup, dann nochmal warten
- `stop()`: nutzt jetzt `wait_until_free()` statt pauschaler `sleep(0.25)` → deterministisch
- `WARNING: FM: RTL-SDR belegt vor play ...` sollte damit behoben sein

**main_core.py — globaler Source-Switch-Lock:**
- `_SOURCE_SWITCH_LOCK` serialisiert alle Quellenwechsel — nur ein Wechsel gleichzeitig
- `_run_station_switch()`: Stop → Play läuft atomar im Background-Thread
- `_stop_all_sources()`: jetzt mit Fehlerlogging statt stummem `pass`

**bluetooth.py — `_ensure_agent()` (BT Agent Fix):**
- `_ensure_agent()`: initialisiert BlueZ Agent sauber: `NoInputNoOutput` → `default-agent`
- Fallback auf ältere BlueZ-Variante wenn nötig
- Ersetzt das bisherige `agent on` / `default-agent` Muster in scan/connect/repair
- Behebt: `default-agent rc=1 out=No agent is registered`

**dab.py — konfigurierbarer DAB Gain + besseres Logging:**
- `_get_dab_gain()`: liest `dab_gain` aus settings.json, Default -1 (Auto AGC)
- `welle-cli -g GAIN` Parameter jetzt gesetzt: `-g -1` = Auto, `-g 35` = 35 dB manuell
- `shlex.quote()` für sicheres Shell-Quoting von Sendernamen
- welle-cli Startausgabe wird nach `/tmp/pidrive_dab_welle.err` + Log geschrieben
- Empfehlung: `dab_gain: 35` in settings.json für schlechte Antenne / Auto

**settings.py — `dab_gain` Default:**
- `dab_gain: -1` in `_DEFAULTS` eingetragen

**wifi.py / webradio.py / musik.py — Altlasten entfernt:**
- `wifi.py`: komplett neu, `log` korrekt importiert, `_has_nmcli()` Check
- `webradio.py`: `load_stations()` dict/list-robust, keine `build_items()` Reste
- `musik.py`: komplett neu, Alt-UI-Reste (`Item`) entfernt

### v0.8.9 — Statusfix, AVRCP Debug, RTL-SDR Lock
**main_display.py — Versionsstring fix:**
- Hardcodierter `v0.8.6` String → jetzt `v0.8.9` (Log zeigte falsche Version)

**status.py — robuste BT-Statusprüfung:**
- BT-Status wird jetzt via `bluetoothctl info <mac>` geprüft statt nur `hciconfig`
- `bt_device` ist jetzt konsistent mit `bt_status` (kein `bt: true` + `bt_device: ""` mehr)
- `bt_status`: verbunden / getrennt / verbindet / aus — klar unterscheidbar

**settings.py — Default-Merge:**
- `load_settings()` mergt jetzt immer Defaults — fehlende Keys wie `bt_last_mac` immer vorhanden
- `save_settings()` nutzt Defaults als Basis, atomares Schreiben via tmp + os.replace

**menu_model.py — BT-Status konsistent:**
- `_bt_is_on` → `_bt_on` (war undefined wenn `bt_status` genutzt wurde)
- BT-State-Label nutzt jetzt `bt_status` direkt: verbunden / verbindet / getrennt / aus
- Labels: "Geraet:" / "Letztes:" statt überlanger Strings

**avrcp_trigger.py — Debug-JSON sofort vorhanden:**
- `write_debug()` wird jetzt direkt beim Start aufgerufen
- WebUI zeigt kein "fehlt (–)" mehr nach Service-Start
- Initial-JSON enthält: ts, last_event, context=startup, source=service_start

**rtlsdr.py — Stale Lock aufräumen:**
- `clear_stale_lock()`: prüft beim Startup ob Lock-Owner-PID noch existiert
- Wenn PID tot → Lock-Datei + State werden bereinigt
- Verhindert `RTL-SDR belegt` nach Core-Neustart (Lock von altem PID blieb stehen)
- Wird automatisch in `log_startup_check()` aufgerufen

### v0.8.8 — Bluetooth Fix & Scanner Optimierung
**bluetooth.py — kritischer NameError fix:**
- `_btctl()` Funktion war vollständig fehlend → jeder `bt_connect` / `bt_repair` Aufruf crashte mit `NameError: name '_btctl' is not defined`
- `_btctl()` jetzt korrekt als Wrapper für `bluetoothctl` implementiert: Timeout, Logging, rc+output Rückgabe
- `connect_device()`: Trust→Pair→Connect mit 3 Verbindungsversuchen + Verify via `bluetoothctl info`
- `repair_device()`: nutzt jetzt `_btctl` korrekt, kein Crash mehr
- `disconnect_current()`: setzt Audio-Routing zurück auf Klinke
- BT Scan Zombie-Fix: `Popen/terminate` statt `kill %1`

**Robuste stop() Funktionen:**
- `dab.stop()`: `welle-cli` + `mpv --title=pidrive_dab` + `rtlsdr.stop_process()` + `time.sleep(0.25)` + Logging
- `fm.stop()`: zusätzlich `pkill -f aplay` (Klinke-Pipe) + Logging
- `scanner.stop()`: `rtl_fm` + `mpv --title=pidrive_scanner` + Logging

**main_core.py — Quellenwechsel-Cleanup:**
- `_stop_all_sources()`: stoppt webradio/dab/fm/scanner vor jedem Quellenwechsel (vermeidet `RTL-SDR belegt`)
- wird in `_execute_node()` bei `node.type == "station"` aufgerufen
- `radio_stop` Trigger stoppt jetzt auch `scanner.stop(S)` (vorher fehlend)

**Scanner Fast-Scan (zweistufig):**
- `_detect_signal_fast()`: schneller Grobtest (0.22s, Squelch=12, breitere BW) → Kandidatenerkennung
- `_detect_signal_confirm()`: Bestätigungstest (0.65s, Squelch=20) → nur bei Kandidaten
- `_scan_bw_fast()`: bandabhängige Fast-Scan-Bandbreite (PMR/LPD=25kHz, CB=20kHz, VHF/UHF=50kHz)
- `_scan_list()`: merkt Scanposition (`scan_idx`) für Fortsetzung statt immer von vorn
- `_scan_range()`: grober Schritt (`_range_step_fast`) für Fast-Pass, Confirm auf Treffer
- `scan_next/prev`: übergeben `band_id` an Scan-Funktionen

### v0.8.7 — Phase 1 Bugfixes & Abschluss
**FM-Bug fix (kritisch):**
- `fm_next` / `fm_prev`: `FM play: keine Frequenz` repariert
- `play_station()` liest jetzt `station.get("freq", station.get("freq_mhz", ""))` — beide Feldnamen kompatibel
- `play_next()` / `play_prev()` matchen nach Name **und** nach Frequenz-String (robust)
- Doppelstart-Schutz: gleicher Sender innerhalb 2s → ignorieren (`_station_key` + `_last_station_key`)

**systemd Ordering-Cycle fix:**
- `pidrive_avrcp.service`: `After=pidrive_core.service` entfernt → kein Shutdown-Zyklus mehr
- Muster entspricht jetzt `pidrive_web.service` (nur `bluetooth.target`)

**Doppelstart-Entprellung in `main_core.py`:**
- `_debounced(cmd)`: globale Entprellung für `enter`, `fm_next/prev`, `dab_next/prev` (0.35–0.5s)
- `_execute_node()`: Guard gegen doppelte Ausführung desselben Menüknotens innerhalb 0.5s
- Verhindert `RTL-SDR belegt` durch schnelle Doppeldrücker oder WebUI+Trigger-Parallelauslösung

### v0.8.6 — Phase 1 Final: Bugfixes
**mpris2.py — kritischer Bugfix:**
- `_get_prop()` Methode fehlte → RuntimeError bei jedem DBus-Property-Abruf des BMW-Displays
- Implementierung delegiert sauber an `GetAll()` (kein Code-Duplikat)

**avrcp_trigger.py — D-Bus Matching repariert:**
- `monitor_dbus()` hatte kaputte String-Literale `'"\'Next\'"'` → wurden nie gematcht
- AVRCP über D-Bus funktionierte nicht; jetzt `'"Next"' in line_s` (korrekt)

**scanner.py — Label-Fix:**
- scan_next/scan_prev: doppeltes " MHz" bei VHF/UHF Range-Scans verhindert
- `ch['name']` für Range-Scans enthält bereits "VHF 145.500 MHz" — kein Append mehr

### v0.8.5 — Phase 1 WebUI abgeschlossen
**index.html:**
- AVRCP / BMW Debug Panel: Service-Status, letztes Event, Kontext, Trigger, Quelle, Debug-JSON
- Scanner-Buttons: VHF/UHF ±25kHz, CB ±10 (scan_step/scan_jump)
- BT-Buttons: BT Trennen (bt_disconnect), BT Reconnect (bt_reconnect_last)
- AVRCP Log Tab + AVRCP Status Tab in Tab-Leiste
- `refreshAvrcp()` JavaScript: /api/avrcp + /api/service polling
- refreshState() koppelt AVRCP automatisch mit

### v0.8.4 — Phase 1 Scanner-Trigger vollständig
**scanner.py — neue Funktionen:**
- `_set_scanner_label()`: zentraler Label-Setter für S-State
- `_play_band_freq()`: zentraler Frequenz-Abspieler VHF/UHF
- `set_freq(band_id, freq_mhz)`: direkte Frequenzwahl mit Bereichsprüfung
- `freq_input_screen(band_id)`: manuelle Frequenzeingabe via up=1/down=0/right=./enter
- `scan_next/scan_prev(settings=None)`: settings-Parameter + Label-Update
- `freq_step`: refactored zu _play_band_freq

**main_core.py:**
- `scan_jump:<band>:<delta>` → scanner.channel_jump()
- `scan_step:<band>:<delta_mhz>` → scanner.freq_step()
- `scan_setfreq:<band>:<freq>` → scanner.set_freq()
- `scan_inputfreq:<band>` → scanner.freq_input_screen()

**webui.py:** scan_jump/step/setfreq/inputfreq/bt_repair in erlaubten Prefixen

### v0.8.3 — Phase 1 AVRCP kontextsensitiv
**avrcp_trigger.py — kompletter Rewrite:**
- Kontextbasiertes Mapping aus status.json + menu.json + list.json
- Kontexte: list_overlay → Navigation | scanner FM/DAB → Senderwechsel | menu → down/up/enter/back
- Scanner VHF/UHF: scan_step ±0.025 MHz (fein) / ±1.0 MHz (grob)
- Scanner Kanal-Bänder: scan_up/down + scan_jump:N
- Volume global: vol_up / vol_down
- Doppelklick Play/Pause → cat:0 (Jetzt läuft)
- Debug-JSON /tmp/pidrive_avrcp.json (last_event, context, trigger, source)

**mpris2.py:** differenzierte BMW-Display Metadaten je Quelle:
- FM: Frequenz als Artist | DAB: Kanal | WEB: Stream-Track | Scanner: Band+Frequenz | Menü: Breadcrumb

**webui.py:** AVRCP_FILE, /api/avrcp, Log-Target "avrcp", pidrive_avrcp in Service-API

### v0.8.2 — BT-Fixes, Senderlisten Memmingen
**Kritische Bugfixes (aus GPT-5.4 Analyse):**
- `bt_connect:MAC` Trigger fehlte im Core → Kopfhörer-Verbindung unmöglich
- `wifi_connect:SSID` Trigger fehlte
- `favorites` nicht importiert → Crash bei Favoriten-Toggle
- StationStore `_fm_file`/_dab_file`/_web_file`/webradio` nicht in __init__ → Crash

**Bluetooth:** _btctl() Wrapper, connect_device Rewrite (Trust→Pair→Connect×2→Verify),
  disconnect_current(), repair_device(), reconnect_last()

**BT-Menü:** Status verbunden/nicht verbunden/aus, Verbundenes Gerät,
  Letztes Gerät, → Verbinden, → Neu koppeln, → Bluetooth trennen

**DAB-Scan:** Regionalscan 7 Kanäle (5C,5D,8D,10A,10D,11D,12D) Standard, scan_dab_channels_full()

**Senderlisten:** fm_stations.json (24 Sender), dab_stations.json (15 Sender) für Memmingen/Allgäu

### v0.8.1 — Scan-Bugfixes
- `NameError: _scan_begin not defined` — Guard-Funktion war in handle_trigger statt Modulebene
- `log.warning` → `log.warn` in rtlsdr.py
- DAB Scan Race Condition: is_busy() nur einmal vor dem Scan (nicht per Kanal)
- FM Scan: timeout 0.4s→1.5s, Squelch 70→30, Schrittweite 0.1→0.2 MHz

### v0.8.0
**RTL-SDR Architektur (Breaking Change):**
- Neues Modul `modules/rtlsdr.py`: zentrale RTL-SDR Verwaltung
- Passive Erkennung (lsusb) — öffnet Device NICHT mehr beim Start
- DVB-Treiber-Check via lsmod
- Unterspannungs-Check via vcgencmd get_throttled
- Busy-Check: laufende rtl_test/rtl_fm/welle-cli Prozesse
- Exklusives Locking via flock() für DAB/FM/Scanner
- Aktive Smoke-Tests (nur manuell: `python3 modules/rtlsdr.py --active`)
- Debug-JSON: `/tmp/pidrive_rtlsdr.json`

**Startup-Log (kein Device-Blockieren mehr):**
- `rtlsdr.log_startup_check()` ersetzt alle direkten rtl_test-Aufrufe
- DAB, FM, Scanner prüfen RTL-SDR Verfügbarkeit vor Zugriff

**DAB+ Parser gehärtet:**
- Nur noch `Service label:` Zeilen als echte Sender
- Alle Debug-/Log-/Frequenzzeilen von welle-cli werden verworfen
- usb_claim_interface error wird erkannt und geloggt

**FM:**
- aplay für Klinke (kein mpv Pipe-Timeout), mpv für BT A2DP

**Install:**
- DVB-Treiber Blacklist automatisch
- Throttling/Unterspannung im Installer ausgegeben
- rtlsdr.py Passive-Diagnose nach Installation


### v0.7.26
**Audio & Stabilität:**
- Hotfix: `from ui import Item` aus bluetooth.py entfernt (Crash bei Core-Start)
- `settings.py`: neues neutrales Modul für `load_settings()`/`save_settings()` (thread-safe)
- audio.py: importiert nicht mehr `main_core` → kein `signal.signal`-Crash in Threads
- audio.py: `_last_decision` startet leer statt `auto`; WebUI zeigt jetzt konkretes `bt`/`klinke`
- audio.py: RADIO_SOURCES + `is_radio_source()` für saubere Quellenunterscheidung
- webradio.py, fm.py, dab.py nutzen `audio.get_mpv_args()` statt hardcoded `hw:1,0`
- **FM Fix: rtl_fm -r 32000 + mpv rate=32000** (vorher Rate-Mismatch → kein Ton)

**Bluetooth:**
- `get_bt_sink()` nutzt PulseAudio `pactl` statt `bluealsa-aplay`
- bluetooth.py: dead `build_items()` entfernt
- **BT Scan Zombie-Fix**: `bluetoothctl scan on` wird jetzt per `Popen/terminate` beendet
  statt `kill %1` (das in `subprocess.run(shell=True)` nicht funktioniert)
- BT Auto-Reconnect: 3 Versuche (0s/5s/12s), letztes Gerät hat Priorität
- `bt_last_mac` + `bt_last_name` in settings.json gespeichert

**DAB+:**
- DAB+ Scan Timeout auf 6s erhöht (RTL-SDR braucht Zeit zum Tunen)
- welle-cli 2.2 Syntax korrigiert: `-c KANAL` statt ungültigem `--programmes`
- Robusteres Parsen der Senderausgabe (verschiedene welle-cli Versionen)

**Neue Features:**
- `mpv_meta.py`: Now-Playing Metadaten für Webradio via mpv JSON-IPC Socket
  → `track` / `artist` in status.json + WebUI sichtbar
- Scanner: CB-Funk DE/EU (80 Kanäle: 41-80 + 1-40, 10 kHz FM)
- Scanner: BANDS-Dict + `_current_ch` definiert (fehlten komplett → NameError)
- RTL-SDR: Startup-Check nur via lsusb+lsmod (kein rtl_test — würde Device blockieren)
- Unterspannungs-Check via vcgencmd get_throttled im Startup-Log

**Install:**
- install.sh: Alt-Import-Check + Import-Smoke-Test vor Service-Start

### v0.7.22
- Favoriten: FM/DAB+/Webradio, config/favorites.json
- ★ Zu Favoriten bei jedem Sender navigierbar
- Neue Kategorie "Favoriten" im Hauptmenü
- BT/WiFi Scan → Submenu fix (menu_rev rebuild)
- BT Scan: 15s für bessere Erkennung
- Vollständiger Startup-Log: USB, Netzwerk, BT, Dienste
- WebUI IPC-State vollständig JS-gesteuert
- Dead files (main.py etc.) werden beim Install gelöscht

### v0.7.21
- Non-blocking Status-Thread (status.py)
- Display: 20fps statt 10fps
- IPC-Schreibintervall: 0.1s statt 0.3s (~50ms Menü-Latenz)
- Dead code entfernt: main.py, trigger.py, ui.py, launcher.py, dabfm.py (1040 Zeilen)
- BT Disconnect in Background-Thread (blockiert nicht mehr den Loop)

### v0.7.20
- BT/WiFi Scan → Submenu (navigierbar): Verbindungen > Geraete / Netzwerke
- Geraet/Netzwerk im Baum auswaehlen = direkt verbinden
- BT Auto-Reconnect beim Boot (alle gepaarten Geraete)
- FM/DAB: letzte Station wird in settings.json gespeichert + beim Boot wiederhergestellt
- Hotfix: _run() NameError in system_check() (crash v0.7.19)

### v0.7.19
- PulseAudio System-Daemon fuer BT A2DP Audio (bluealsa nicht in Bullseye)
- setup_bt_audio.sh: pulse-User in BT-Gruppe, DBus-Policy, system.pa, PULSE_SERVER
- install.sh ruft setup_bt_audio.sh automatisch auf
- bluetooth.py: _set_pulseaudio_sink() statt bluealsa-Device-String
- main_core.py: BT-Disconnect setzt PA-Sink zurueck auf ALSA

### v0.7.18
- BT Audio Fix: Audio-Routing-Code fehlte im if ok: Block (audio=auto Bug)
- audio.py: prueft ob PulseAudio laeuft, Fallback auf Klinke
- install.sh: bluealsa-Erkennung mit PulseAudio-Fallback

### v0.7.17
- Service-Files Fix: install.sh kopiert jetzt ALLE 4 Service-Dateien
  (pidrive_core, pidrive_display, pidrive_web, pidrive_avrcp)
- Ordering-Cycle dauerhaft geloest: alte Datei auf Pi hatte After=pidrive_core

### v0.7.16
- Raspotify Auto-Routing: bei BT-Connect wechselt raspotify auf BT A2DP-Sink
- Bei BT-Trennung: raspotify zurueck auf hw:1,0 (Klinke)
- _set_raspotify_device() in bluetooth.py: patcht /etc/raspotify/conf + restart
- main_core.py: ueberwacht BT-Status, loest Fallback automatisch aus
- install.sh: setzt LIBRESPOT_BACKEND=alsa + LIBRESPOT_DEVICE=default
# PULSE_SERVER=unix:/var/run/pulse/native  ← wird von install.sh in raspotify.service gesetzt als Standard

### v0.7.15
- Systemd Ordering-Cycle Fix: After=pidrive_core aus pidrive_web.service entfernt
- pidrive_display.service: After=pidrive_core → After=multi-user.target
- StartLimitIntervalSec=120 / Burst=10 in pidrive_web
- install.sh: __pycache__ loeschen + reset-failed vor Web-Neustart
- from ui import Item (pygame) aus allen 10 Modulen entfernt (WebUI Crash Fix)

### v0.7.14
- BT Audio-Routing: nach BT-Connect wird audio_output="bt" gesetzt
- WebUI Overlay Fix: listOverlay immer im DOM (vorher: nur wenn list_active=True)
- JS baut BT/WiFi-Liste dynamisch

### v0.7.13
- BT Scan: race condition fix (headless_pick race)
- BT Connect: 2s statt 15s Timeout-Problem geloest

### v0.7.10 — v0.7.12
- WebUI: Single-Column Baumnavigation mit Icons
- Ordering-Cycle Fix (pidrive_web After=pidrive_core entfernt)
- Version-Strings bereinigt

### v0.7.7 — v0.7.9
- action=None NameError Fix (alle Actions fehlgeschlagen)
- StationStore: Senderlisten hot-reload
- Suchlauf-Pipeline: DAB/FM → JSON → Menü sofort sichtbar

### v0.7.3 — v0.7.6
- Core/Display getrennt (headless Core + pygame Display)
- pidrive_core.service + pidrive_display.service
- ipc.py: atomares JSON (status.json + menu.json)
- fbcp entfernt, fb1 direkt

### v0.7.0 — v0.7.2
- Baumbasiertes Menumodell (menu_model.py, MenuNode, MenuState)
- StationStore mit JSON hot-reload
- Altlasten build_items() aus allen Modulen entfernt

### v0.4.x — v0.6.x
- launcher.py: setsid + TIOCSCTTY (v0.3.7)
- SDL_AUDIODRIVER=dummy (v0.4.0)
- scanner.py: PMR446, Freenet, LPD433, VHF, UHF (v0.3.8)
- fbcp-Architektur → direkt fb1 (v0.6.0)

### v0.3.0 — v0.3.6
- DAB+ Radio (welle.io), FM Radio (rtl_fm)
- OTA Updates aus dem Menue
- Logging-Modul (rotierend)
- Bluetooth Audio-Ausgang
- Webradio, MP3 Bibliothek mit Album-Art


## Aktueller Stand (v0.9.30)

**System läuft stabil** — 26.04.2026:

```
✓ pidrive_core.service      v0.9.30 — BT Ghost-Connect, DAB/BT-Pause, PPM-Calibrate
✓ pidrive_display.service   v0.9.30, 20fps
✓ modules/dab.py            welle-cli -p → ALSA direkt (kein HTTP-Modus)
✓ modules/fm.py             rtl_fm | mpv --ao=alsa hw:1,0
✓ modules/bluetooth.py      BT Scan: scan on/off; BT Agent persistent
✓ modules/audio.py          get_mpv_args: ALSA für FM/DAB, PulseAudio für Webradio/BT
✓ webui.py                  4-Tab WebUI, 1.5s Poll Tab 1
✓ web/templates/index.html  Tabs: Steuerung / Audio / DAB+FM / Log
✓ config/dab_stations.json  32 Sender (11D/10A/11B, MHT-Import)
✓ config/settings.json      ppm=49, fm_gain=30, dab_gain=-1, squelch=10
```

**Hardware:** Raspberry Pi 3B, Joy-IT RB-TFT3.5 (480×320, fb1),
RTL2838 DVB-T (0bda:2838), Cambridge Silicon Radio BT-Dongle.

**Aktuelle Quellen-Architektur:**

| Quelle | Befehl | Audio-Routing |
|---|---|---|
| FM | `rtl_fm ... \| mpv --ao=alsa hw:1,0` | ALSA direkt (kein PulseAudio) |
| DAB | `welle-cli -p "NAME"` OHNE PULSE_ENV (bewusst!) | ALSA hw:1,0 direkt — NICHT PulseAudio, NICHT BT-routingfähig |
| Webradio | `mpv --ao=pulse http://url` | PulseAudio (BT-fähig) |
| Spotify | librespot → PulseAudio | PulseAudio (BT-fähig) |

**Bekannte Einschränkungen:**
- Volume-Anzeige zeigt "–" wenn kein PulseAudio Default Sink gesetzt
- BT Pairing muss manuell via bluetoothctl erfolgen (PiDrive kann nur verbinden)
- DAB Frequenzkorrektur (PPM) wird von welle-cli intern gehandhabt (coarseCorrector)


## Entwicklungs-Phasen & Roadmap

---

### Phase 1 — BMW iDrive AVRCP Integration (✅ Code abgeschlossen v0.8.7)

**Ziel:** PiDrive vollständig per BMW iDrive Drehsteller bedienbar.

- [x] AVRCP-Service + avrcp_trigger.py
- [x] AVRCP 1.5 Versionspinning BMW NBT EVO
- [x] MPRIS2-Metadaten → BMW-Display
- [x] Kontextabhängiges Mapping: menu/radio/scanner/list_overlay
- [x] Scanner über AVRCP bedienbar
- [x] AVRCP Debug-JSON + WebUI Debug Panel
- [ ] **BMW iDrive Praxistest im Auto** — code-seitig fertig, Feldtest ausstehend

---

### Phase 2 — AVRCP Single-Path & Zustandsmaschine (🔄 in Arbeit, v0.9.x)

**Ziel:** Saubere, wartbare Architektur mit einem zentralen Eingabepfad, konsistentem
Status und serialisierten Quellenwechseln.

#### State-Machine — aktueller Stand (v0.9.5):

**Implementiert:**
- `modules/source_state.py` — drei getrennte State-Ebenen:
  - `source_current`: idle | fm | dab | webradio | scanner | spotify | library
  - `audio_route`: klinke | bt | hdmi | none
  - `bt_state`: off | idle | connecting | connected | failed
- `begin_transition()` / `commit_source()` / `end_transition()` — serialisierte Quellenwechsel
- `_run_station_switch()` in main_core.py nutzt vollständig begin/commit/end
- `_stop_all_sources()` committed `idle`
- Scanner-Schleifen brechen bei `in_transition()` ab
- BT-Connect prüft `in_transition()` vor Connect-Versuch
- boot_phase: cold_start → restore_bt → restore_source → steady

**Noch offen für Phase 2:**
- [ ] `ipc.py`: `_get_audio_effective/reason()` liest noch aus In-Prozess-Zustand
  (`get_last_decision()`), nicht aus `read_last_decision_file()` — Status-Inkonsistenz
  zwischen WebUI-Prozess und Core bleibt möglich
- [ ] Scanner-Trigger in `main_core.py` (`scan_next/prev/up/jump/step`) übergeben
  `settings` nicht an `scanner.scan_next(b, S)` — PPM/Gain/Squelch werden dort aus
  Settings neu geladen, aber nicht durchgereicht
- [ ] `scan_next/prev/jump/step` nutzen keine `source_state.begin_transition()` —
  Scanner-Start ist noch nicht voll in die State-Machine integriert
- [ ] Spotify/Library als Source-States noch nicht über source_state.commit_source()
  erfasst
- [ ] Installer-Log-Verifikation zeigt alte Version (`v0.8.25`) weil grep-Pattern
  `"Core v0.6"` nicht die neue Versionnummer trifft

---

### Phase 3 — Resume-State & Stabilität im Dauerbetrieb (🔄 teilweise, v0.9.x)

**Ziel:** PiDrive startet im Auto sofort in der letzten Quelle, BT verbindet zuverlässig.

**Implementiert:**
- Boot-Resume: FM/DAB/Webradio wiederhergestellt (v0.8.19)
- BT-Backup/Restore der Pairing-Keys (v0.8.25)
- Boot Auto-Restore wenn BlueZ-DB leer (v0.8.25)
- BT Auto-Reconnect Watcher: 6s Startpause, 12s Intervall (v0.9.1)
- Startup-Lautstärke aus settings.json beim Boot anwenden (v0.9.0)
- `ensure_settings_file()` normalisiert settings.json beim Boot (v0.9.2)
- `settings.json` vollständig mit 34 Keys (v0.9.2)

**Noch offen:**
- [x] BT-Agent: `_ensure_agent()` nutzt jetzt printf-Pipe — WARNING behoben (v0.9.7)
- [ ] BT-Pairing praktisch noch nicht als stabil verifiziert (Feldtest fehlt)
- [ ] BT Auto-Reconnect: Nach Reboot findet Watcher das Gerät erst nach ~12s Scan-Zyklus
  — erste Verbindung noch nicht so schnell wie gewünscht
- [ ] Spotify Boot-Resume fehlt noch (letzte Spotify-Wiedergabe wird nicht wiederhergestellt)
- [ ] USB-Tethering Autostart (Pi als USB-Netzwerkgerät ohne WLAN)

---

## Offene Code-Review-Punkte (Stand nach v0.9.2)

### Kritisch / Funktional relevant

| # | Problem | Details | Priorität |
|---|---|---|---|
| 1 | `ipc.py` liest Audio-State aus In-Prozess-Zustand | `_get_audio_effective/reason()` nutzt `get_last_decision()` statt `read_last_decision_file()` → Status-JSON kann von WebUI-Debug abweichen | Hoch |
| 2 | Scanner-Settings nicht durchgereicht | `scan_next/prev/jump/step` Trigger in main_core.py übergeben keine settings → PPM/Gain werden in scanner.py neu geladen (funktioniert, aber nicht sauber) | Mittel |
| 3 | Scanner nicht in source_state integriert | scan_next/prev-Trigger nutzen keine begin_transition() | Mittel |
| 4 | Installer zeigt alte Version im Log | grep-Pattern `"Core v0.6"` trifft nicht neue Versionen → Log zeigt `v0.8.25` | Niedrig |
| 5 | ~~BT-Agent WARNING~~ | ~~`default-agent nicht bestätigt` bei jedem Connect-Versuch~~ | ✅ behoben v0.9.7 |

### Diagnose / Debug

| # | Problem | Details | Priorität |
|---|---|---|---|
| 6 | Sink-Input App/Binary/PID teilweise leer | `pactl list sink-inputs` Parsing: Application Name wird nicht immer gefunden | Niedrig |
| 7 | Default-Sink leer in Diagnose | Fallback via `pactl info` in v0.9.2 implementiert, aber nicht im echten System verifiziert | Mittel |
| 8 | amixer-Diagnose | Hex-Parse-Fix in v0.9.2, noch nicht im echten System verifiziert | Niedrig |

### Aufräum / Technische Schuld

| # | Problem | Details | Priorität |
|---|---|---|---|
| 9 | `Error_v0.8.25.md` im Repo | Debug-Analyse, kein Release-Dokument | Niedrig |
| 10 | `pidrive_debug.sh` veraltet | v0.6.0, ersetzt durch `pidrive_boot_debug.sh` | Niedrig |
| 11 | `systemd/pidrive.service` veraltet | Alter monolithischer Service, ersetzt durch Core+Display | Niedrig |
| 12 | `setup_bt_audio.sh` nicht in install.sh integriert | Wird nicht automatisch aufgerufen | Niedrig |
| 13 | `.gitignore` excludiert `settings.json` | Seit v0.9.2 soll vollständige Default-Datei ins Repo | Niedrig |
| 14 | BT-Praxistest Feldtest | Kopfhörer war bei Tests aus, BT noch nicht als stabil verifiziert | Hoch |
| 15 | BMW iDrive Feldtest | Phase 1 code-seitig fertig, kein Praxistest im Auto | Mittel |

---

## Roadmap v0.9.3

### Ziele

1. **Aufräumen** — tote Dateien entfernen, .gitignore korrigieren
2. **State-Machine vervollständigen** — Scanner und Spotify in source_state integrieren
3. **ipc.py Audio-State** — auf read_last_decision_file() umstellen
4. **Installer-Log-Verifikation** — grep-Pattern für aktuelle Versionen korrigieren
5. **BT-Agent** — zuverlässigere Registrierung

### Konkrete Patches v0.9.3

```
Remove:  Error_v0.8.25.md
Remove:  pidrive_debug.sh  (ersetzt durch pidrive_boot_debug.sh)
Remove:  systemd/pidrive.service  (veraltet)

Fix:     ipc.py  _get_audio_effective/reason() → read_last_decision_file()
Fix:     main_core.py  scan_next/prev/jump Trigger → settings durchreichen
Fix:     main_core.py  Scanner-Trigger → source_state.begin/commit/end
Fix:     install.sh  Log-Verifikation → grep-Pattern auf aktuelle Versionen
Fix:     .gitignore  settings.json Ausnahme ergänzen

Optional: setup_bt_audio.sh in install.sh integrieren oder entfernen
```

---

### ✅ Alles Erledigte

### ✅ Alles Erledigte

- [x] Baumbasiertes Menümodell (v0.7.0)
- [x] Senderlisten aus JSON mit Hot-Reload und Merge-Strategie (v0.7.1)
- [x] DAB/FM Suchlauf → JSON → Menü sofort sichtbar (v0.7.2)
- [x] Core/Display getrennt — headless Core, pygame Display (v0.7.3)
- [x] SDL_AUDIODRIVER=dummy, fb1 direkt, fbcp entfernt (v0.6.0)
- [x] Systemd Ordering-Cycle dauerhaft gelöst (v0.7.15–v0.7.17)
- [x] Raspotify wechselt automatisch BT/Klinke (v0.7.16)
- [x] PulseAudio BT A2DP Setup-Script (v0.7.19)
- [x] AVRCP 1.5 + MPRIS2 für BMW NBT EVO (v0.7.19/v0.7.20)
- [x] BT/WiFi Scan → navigierbares Submenu (v0.7.20–v0.7.22)
- [x] Favoriten: FM/DAB+/Webradio, config/favorites.json (v0.7.22)
- [x] BT Auto-Reconnect beim Boot, 3 Versuche, letztes Gerät priorisiert (v0.7.20/v0.8.6)
- [x] FM/DAB letzte Station beim Boot wiederherstellen (v0.7.20)
- [x] Performance: non-blocking Status-Thread, 20fps, ~50ms Latenz (v0.7.21)
- [x] Dead code entfernt: launcher.py, main.py, ui.py, trigger.py (v0.7.21)
- [x] RTL-SDR Architektur: rtlsdr.py, Locking, passive Erkennung (v0.8.0)
- [x] FM/DAB Scan Bugfixes: Race Condition, Timeout, Squelch (v0.8.1)
- [x] BT-Fixes: connect/disconnect/repair, bt_connect Trigger (v0.8.2)
- [x] Senderlisten Memmingen/Allgäu: fm_stations.json + dab_stations.json (v0.8.2)
- [x] AVRCP kontextsensitiv: menu/radio/scanner/list_overlay (v0.8.3)
- [x] MPRIS2 differenzierte BMW-Metadaten je Quelle (v0.8.3)
- [x] Scanner-Trigger vollständig: scan_jump/step/setfreq/inputfreq (v0.8.4)
- [x] WebUI AVRCP Debug Panel + Scanner-Buttons (v0.8.5)
- [x] PPM-Korrektur, Squelch-Einstellung, Empfangsoptimierung (v0.8.18)
- [x] WebUI-Kompakt, Phase 2 State, PulseAudio Switch-on-Connect (v0.8.17)
- [x] RTL-SDR USB-Reset, Lautstärke-Fix (v0.8.16)
- [x] BT-AuthFix, Gain-WebUI, Auto-Reconnect (v0.8.15)
- [x] Klinke-Audio-Fix, BT-Agent-Fix (v0.8.14)
- [x] Audio State File, Scanner-Guard, BT-Fix, Status-Sync (v0.8.13)
- [x] Audio Debug Cockpit, Versionsstrings, Diagnose-Fix (v0.8.12)
- [x] Audio-Architektur Option B, DAB Fix, Car-Only Cleanup (v0.8.11)
- [x] FM Race-Fix, DAB Gain, BT Agent, Cleanup (v0.8.10)
- [x] Statusfix: BT robust, AVRCP Debug-JSON, RTL-SDR Stale Lock, Display-Version (v0.8.9)
- [x] Bluetooth _btctl NameError fix, connect/repair robust (v0.8.8)
- [x] Robuste stop() für FM/DAB/Scanner, Quellenwechsel-Cleanup (v0.8.8)
- [x] Scanner Fast-Scan zweistufig: Fast-Detect + Confirm (v0.8.8)
- [x] Phase 1 Bugfixes: FM fm_next/prev, systemd Ordering-Cycle, Doppelstart-Entprellung (v0.8.7)
- [x] Phase 1 Bugfixes: mpris2 _get_prop, AVRCP D-Bus Matching (v0.8.6)


---

## Aufräum-Plan: Dateien für nächstes Release entfernen/bereinigen

### Beim nächsten Paket (v0.9.3) entfernen:

| Datei | Grund |
|---|---|
| `Error_v0.8.25.md` | Debug-Analyse, kein Release-Dokument |
| `pidrive_debug.sh` | Veraltet (v0.6.0) — ersetzt durch `pidrive_boot_debug.sh` (v0.9.0) |
| `systemd/pidrive.service` | Alter monolithischer Service — ersetzt durch pidrive_core + pidrive_display |

### Beim nächsten Paket prüfen/anpassen:

| Datei | Aktion |
|---|---|
| `.gitignore` | `pidrive/config/settings.json` ist excludiert — neu: vollständige Default-settings.json soll ins Repo, nur lokale Überschreibungen sollen ignoriert werden. Ggf. `settings.json` aus .gitignore entfernen oder Ausnahme `!pidrive/config/settings.json` hinzufügen |
| `KontextPiDrive.md` | Bleibt im Repo als Entwicklerdokumentation ✓ |
| `config.txt.example` | Bleibt — nützlich für Erstinstallation ✓ |
| `pidrive_boot_debug.sh` | Bleibt — aktuelles Debug-Script ✓ |
| `pidrive_car_only_cleanup.sh` | Bleibt — nützlich für Car-Only Setup ✓ |
| `setup_bt_audio.sh` | Prüfen ob noch aktuell — PulseAudio-Setup ggf. in install.sh integriert |
| `pidrive/status.py` | Prüfen ob noch aktiv genutzt oder Dead Code |
| `pidrive/modules/musik.py` | Prüfen ob noch aktiv genutzt |


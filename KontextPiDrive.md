# PiDrive — Kontext & Projektdokumentation v0.8.10

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

PiDrive  (v0.8.10 — Baumbasiert, beliebig tief)
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
- install.sh: setzt LIBRESPOT_BACKEND=alsa + LIBRESPOT_DEVICE=hw:1,0 als Standard

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


## Aktueller Stand (v0.8.10)

**System läuft stabil** — 16.04.2026:

```
✓ pidrive_core.service      v0.8.10 — FM Race-Fix, DAB Gain, BT Agent, Cleanup
✓ pidrive_display.service   20fps, Version korrekt
✓ pidrive_web.service       http://<PI-IP>:8080 + RTL-SDR Diagnosebox + AVRCP Debug-Panel
✓ pidrive_avrcp.service     BMW iDrive AVRCP 1.5, Debug-JSON sofort sichtbar
✓ pulseaudio.service        BT A2DP Audio
✓ rtlsdr.py                 wait_until_free() — wartet auf echte RTL-Freigabe nach stop()
✓ FM Radio                  Race Condition behoben: wait_until_free + deterministischer stop()
✓ main_core.py              Source-Switch-Lock: nur ein Quellenwechsel gleichzeitig
✓ bluetooth.py              _ensure_agent() — BlueZ Agent robuster initialisiert
✓ dab.py                    DAB Gain konfigurierbar (-g GAIN), welle-cli Log, shlex.quote
✓ settings.py               dab_gain: -1 (Auto) als Default, überschreibbar
✓ wifi.py                   Komplett neu, Altlasten entfernt, log korrekt importiert
✓ webradio.py               Komplett neu, load_stations() dict/list-robust
✓ musik.py                  Komplett neu, Alt-UI-Reste (Item) entfernt
✓ AVRCP kontextsensitiv     menu / radio / scanner / list_overlay
✓ Favoriten                 FM/DAB+/Webradio, config/favorites.json
✓ Senderlisten Memmingen    24 FM + 15 DAB+ Sender für Raum Memmingen/Allgäu
```

**Offene Punkte:**
- GPIO-Buttons (Key1=GPIO23, Key2=GPIO24, Key3=GPIO25)
- BMW iDrive AVRCP Praxistest im Auto (code-seitig fertig, Feldtest ausstehend)
- resume_state.py / last_state.json für Boot-Resume
- BT Auto-Reconnect im Laufzeitbetrieb (Kopfhörer der nach Start eingeschaltet wird)


## Entwicklungs-Phasen & Roadmap

### Phase 1 — BMW iDrive AVRCP Integration (✅ Code abgeschlossen v0.8.7)

**Ziel:** PiDrive vollständig per BMW iDrive Drehsteller bedienbar, kontextabhängiges Mapping, Debug-Sichtbarkeit.

**Abgeschlossene Punkte:**
- [x] AVRCP-Service `pidrive_avrcp.service` + `avrcp_trigger.py` (v0.7.19)
- [x] AVRCP 1.5 Versionspinning für BMW NBT EVO (v0.7.19)
- [x] MPRIS2-Metadaten → BMW-Display: Sender/Titel/Breadcrumb (v0.7.20)
- [x] Kontextabhängiges AVRCP-Mapping: menu / radio / scanner / list_overlay (v0.8.3)
- [x] Scanner über AVRCP bedienbar: VHF/UHF ±25kHz/±1MHz, CB ±10 Kanäle (v0.8.3–v0.8.4)
- [x] Differenzierte BMW-Metadaten je Quelle: FM=Frequenz, DAB=Kanal, WEB=Track, Scanner=Band+Freq (v0.8.3)
- [x] AVRCP Debug-JSON `/tmp/pidrive_avrcp.json` (last_event, context, trigger, source) (v0.8.3)
- [x] WebUI AVRCP/BMW Debug Panel: Service-Status, Event, Kontext, Trigger, Quelle (v0.8.5)
- [x] WebUI Scanner-Buttons: VHF/UHF ±25kHz/±1MHz, CB ±10 (v0.8.5)
- [x] Kritische Bugfixes: `_get_prop()` in mpris2.py, D-Bus String-Matching in avrcp_trigger.py (v0.8.6)

**Offen (Feldtest, kein Code):**
- [ ] **BMW iDrive AVRCP Praxistest im Auto** — code-seitig fertig, physischer Test steht aus

---

### Phase 2 — AVRCP Single-Path & Zustandsmaschine (🔜 nächste Phase)

**Ziel:** Saubere, wartbare AVRCP-Architektur mit einem zentralen Eingabepfad statt verteilter Verarbeitung.

**Noch offen:**
- [ ] Single-Path für AVRCP-Eingaben — aktuell verarbeiten `avrcp_trigger.py` und `mpris2.py` Eingaben teilweise selbst
- [ ] Explizite Bedien-Zustandsmaschine im Core (`control_context` als eigene State-Klasse)
- [ ] Zentraler `ControlContext` in `main_core.py` statt verteiltem Context-Lesen aus JSON-Dateien
- [ ] AVRCP-Eingaben ausschließlich über Core-Trigger (File-Trigger oder IPC), kein Direkt-Schreiben mehr

---

### Phase 3 — Boot-Resume & Stabilität im Dauerbetrieb (🔜 folgende Phase)

**Ziel:** PiDrive startet im Auto sofort in der letzten Quelle/Station, ohne manuelle Navigation.

**Noch offen:**
- [ ] `resume_state.py` / `last_state.json` — letzte Quelle, Station, Frequenz, BT-Gerät beim Boot vollständig wiederherstellen
- [ ] USB-Tethering Autostart — Pi als USB-Netzwerkgerät, kein WLAN nötig
- [ ] Hotspot-Modus — WLAN-Hotspot wenn kein Heimnetz verfügbar
- [ ] Scanner-Kanäle als Favoriten (PMR446/LPD433)
- [ ] DAB+ DLS Programminfo (`welle-cli --dls`)
- [ ] FM RDS-Text (`rtl_fm + rds_rx`)
- [ ] WebUI Breadcrumb-Navigation

---

### Weitere Roadmap

#### Kurzfristig (nächste 1–3 Updates)

- [ ] **GPIO-Buttons** (Key1=GPIO23, Key2=GPIO24, Key3=GPIO25) — direkte Steuerung am Display, wichtigste UX-Verbesserung für Fahrzeugbetrieb
- [ ] **USB-Tethering Autostart** — Pi als USB-Netzwerkgerät beim Einschalten, kein WLAN nötig
- [ ] **resume_state.py** — last_state.json: letzte Quelle/Station beim Boot vollständig wiederherstellen
- [ ] **Scanner-Kanäle als Favoriten** — PMR446/LPD433-Kanäle in Favoritenliste aufnehmen
- [ ] **WebUI Breadcrumb-Navigation** — navigierbarer Baum statt JSON-Dump

#### Mittelfristig (Fahrzeugbetrieb)

- [ ] **BMW iDrive AVRCP Praxistest** — Phase 1 code-seitig abgeschlossen; Feldtest im Auto steht noch aus
- [ ] **DAB+ Programminfo (DLS)** — laufender Titeltext via `welle-cli --dls`
- [ ] **FM RDS-Text** — Senderinformationen via `rtl_fm + rds_rx`
- [ ] **Equalizer** — ALSA-basiert, Preset-Auswahl im Menü
- [ ] **Hotspot-Modus** — Pi öffnet WLAN-Hotspot wenn kein Heimnetz verfügbar

#### Langfristig

- [ ] **OBD2 Fahrzeugdaten** — USB-ELM327, `python-obd`: Tacho, Drehzahl, Kühlwassertemperatur im Display
- [ ] **BMW iPod-Emulation** — IAP2-Emulation über CD-Wechsler-Port
- [ ] **Spotify Web API** — Play/Pause/Weiter vom Pi aus steuern (nicht nur AVRCP)
- [ ] **Pi 4 Migration** — leistungsstärkere Hardware für flüssigeres Display

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
- [x] FM Race-Fix, DAB Gain, BT Agent, Cleanup (v0.8.10)
- [x] Statusfix: BT robust, AVRCP Debug-JSON, RTL-SDR Stale Lock, Display-Version (v0.8.9)
- [x] Bluetooth _btctl NameError fix, connect/repair robust (v0.8.8)
- [x] Robuste stop() für FM/DAB/Scanner, Quellenwechsel-Cleanup (v0.8.8)
- [x] Scanner Fast-Scan zweistufig: Fast-Detect + Confirm (v0.8.8)
- [x] Phase 1 Bugfixes: FM fm_next/prev, systemd Ordering-Cycle, Doppelstart-Entprellung (v0.8.7)
- [x] Phase 1 Bugfixes: mpris2 _get_prop, AVRCP D-Bus Matching (v0.8.6)


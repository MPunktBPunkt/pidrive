# PiDrive — Kontext & Projektdokumentation v0.7.17

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
    ├── main_core.py         (Core: headless, kein pygame)
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
    ├── VERSION              (aktuell: 0.7.17)
    ├── config/
    │   ├── stations.json    (Webradio)
    │   ├── dab_stations.json (DAB+ nach Scan)
    │   ├── fm_stations.json  (FM Sender)
    │   └── settings.json
    ├── web/
    │   ├── templates/index.html  (Web UI Template)
    │   └── static/style.css
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

## TIOCSCTTY — Warum wir es NICHT verwenden (v0.7.17)

SDL fbcon ruft intern VT_SETMODE(VT_PROCESS) auf. Wenn der Prozess ein
Controlling Terminal hat (gesetzt via TIOCSCTTY), sendet der Kernel SIGHUP
bei VT-Events (z.B. wenn VT3 in den Vordergrund kommt). SDL hat keinen
SIGHUP-Handler -> exit(0), kein Python-Fehler, kein Log-Eintrag.

Diagnose (v0.7.17):
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

PiDrive  (v0.7.x — Baumbasiert, beliebig tief)
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
| Display dunkel | pygame auf fb0+fbcp Architektur — ersetzt durch fb1 direkt | main_display.py + pidrive_display.service (v0.7.17) |
| Display zeigt nichts | camera/display_auto_detect=1 | In config.txt auf 0 |
| Unable to open console terminal | /dev/tty3 nicht lesbar oder kein Controlling Terminal | launcher.py + udev-Regel (v0.3.7) |
| Service Restart-Schleife | HUP bei StandardInput=tty | launcher.py ersetzt TTY-Management (v0.3.7) |
| Service stirbt exit(0) | PAMName+StandardInput+root haengt systemd247 | Core ohne pygame (v0.7.17) |
| set_mode() haengt | SDL wartet auf VT in monolithischem Service | Core/Display Trennung + fb1 direkt (v0.7.17) |
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

### v0.7.17 (aktuell)
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

## Aktueller Stand (v0.7.17)

**System laeuft stabil** — bestätigt 11.04.2026 (v0.7.17):

```
✓ pidrive_core.service: active, headless (v0.7.17)
✓ pidrive_display.service: active, fb1 direkt (v0.7.17)
✓ pidrive_web.service: active, http://<PI-IP>:8080 (Ordering-Cycle fix)
✓ pidrive_avrcp.service: active, BMW iDrive → AVRCP
✓ fbcp: dauerhaft deaktiviert
✓ MPRIS2: BMW-Display zeigt Sendername/Titel
✓ AVRCP 1.5: konfiguriert
✓ BT Audio-Routing: raspotify wechselt automatisch BT/Klinke
✓ WebUI: Single-Column Baumnavigation, BT/WiFi Overlay
✓ IPC: status.json + menu.json + list.json + ready
✓ Menü: Baumstruktur, Senderlisten aus JSON, hot-reload
```

**Bekannte offene Punkte:**
- GPIO-Buttons (Key1=GPIO23, Key2=GPIO24, Key3=GPIO25)
- BMW iDrive BT-Pairing und AVRCP Praxistest im Auto
- Audio Klinke/HDMI/BT Umschaltung im Fahrbetrieb testen


## Roadmap

### Kurzfristig
- [x] Baumbasiertes Menümodell (v0.7.0)
- [x] Senderlisten aus JSON mit Hot-Reload und Merge-Strategie
- [x] DAB/FM Suchlauf-Pipeline → JSON → Menü sofort sichtbar
- [x] Scan-Rückmeldung: Sender gefunden / Fehler sichtbar
- [x] Senderlisten-UX: Favoriten zuerst (★), Frequenz/Ensemble/Genre
- [x] IPC-Vertrag in ipc.py dokumentiert (stabil ab v0.7.1)
- [x] Altlasten build_items() aus allen Modulen entfernt
- [ ] Audio Klinke/HDMI/BT Umschaltung testen
- [ ] GPIO-Buttons (Key1=GPIO23, Key2=GPIO24, Key3=GPIO25)
- [ ] USB-Tethering Autostart

### Mittelfristig
- [ ] Web-UI Redesign: Breadcrumb, kein Display-Spiegel
- [ ] DAB+ Programminfo (welle-cli DLS)
- [ ] FM RDS Text (rtl_fm + rds_rx)
- [ ] Favoriten setzen/entfernen im Menü
- [ ] Equalizer (ALSA-basiert)
- [ ] Hotspot-Modus

### Langfristig (Fahrzeug-Integration)
- [x] AVRCP BMW 118d 2017 NBT EVO → File-Trigger (v0.7.17)
- [x] MPRIS2 D-Bus → BMW-Display Metadaten (v0.7.17)
- [x] AVRCP 1.4 Konfiguration für NBT EVO Kompatibilität
- [ ] OBD2 Fahrzeugdaten (ELM327 USB, python-obd)
- [ ] BMW iDrive Playlist-Simulation (volles Dateisystem im Auto-Display)
- [ ] iPod-Emulation (libaacs / iap2)
- [ ] Spotify Web API (Play/Pause/Next)
- [ ] Bluetooth-Audio Autoconnect

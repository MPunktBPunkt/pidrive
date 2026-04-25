# PiDrive 🚗🎵

Raspberry Pi Car Infotainment — Spotify Connect, Webradio, DAB+, FM, MP3 für BMW iDrive und ähnliche Systeme.

[![Version](https://img.shields.io/badge/version-0.9.15-orange.svg)](https://github.com/MPunktBPunkt/pidrive/blob/main/pidrive/VERSION)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python 3](https://img.shields.io/badge/python-3.x-green.svg)](https://www.python.org/)
[![Raspberry Pi](https://img.shields.io/badge/Raspberry%20Pi-3B%2F4-red.svg)](https://www.raspberrypi.org/)

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
| Raspberry Pi | Pi 3B (getestet), Pi 4 geplant |
| Display | Joy-IT RB-TFT3.5, 480×320, XPT2046 Touch (SPI) |
| Audio-Ausgang | 3.5mm Klinke → Autoradio AUX-IN |
| Stromversorgung | USB-KFZ-Adapter 5V/2A (Micro-USB) |
| Optional | RTL-SDR Stick für DAB+ und FM |

### Verbindung mit dem Auto

```
Pi 3.5mm Klinke ──────────────────── Auto AUX-IN
Pi Micro-USB ──── USB-KFZ-Adapter ── KFZ 12V
Pi WLAN/USB ──── Heimnetz/Tethering ── SSH / http://PI-IP:8080
```

Audio-Ausgang aktivieren: `echo "audio_klinke" > /tmp/pidrive_cmd`

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

#
## settings.json — Konfigurationsreferenz (v0.9.6)

| Key | Standard | Erklärung |
|---|---|---|
| `ppm_correction` | `49` | Quarzfehler RTL-SDR Stick (ppm) — gemessen per Kalibrierung |
| `fm_gain` | `30` | FM Gain in dB, `-1` = Auto-AGC |
| `dab_gain` | `-1` | DAB+ Gain, `-1` = Auto-AGC (empfohlen) |
| `scanner_gain` | `-1` | Scanner Gain, `-1` = Auto-AGC |
| `scanner_squelch` | `10` | Rauschunterdrückung, 0=offen, 10=empfindlich, 25=Standard |
| `dab_scan_wait_lock` | `20` | Sekunden pro DAB-Kanal beim Scan (für schwachen Empfang erhöhen) |
| `dab_scan_http_timeout` | `4` | HTTP-Timeout für mux.json-Abruf in Sekunden |
| `dab_scan_port` | `7981` | welle-cli Port beim Scan (getrennt von WebUI-Diagnose Port 7979) |
| `dab_scan_channels` | `["11D","10A","8D","8B","11B"]` | Gezielte Scan-Kanäle, leer = Vollscan aller 38 Kanäle |
| `audio_output` | `"auto"` | Audioausgang: `auto`, `klinke`, `bt`, `hdmi` |
| `volume` | `90` | Startup-Lautstärke in % |
| `last_source` | `""` | Letzte Quelle für Boot-Resume (FM/DAB/Webradio) |


## Update

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
├── install.sh               # Schnellinstallation + Update (10 Schritte)
├── setup_bt_audio.sh        # PulseAudio BT Audio Setup
├── KontextPiDrive.md        # Vollständige Projektdokumentation
├── README.md
├── systemd/
│   ├── pidrive_core.service    # Headless Core (kein pygame)
│   ├── pidrive_display.service # pygame Display (fb1 direkt)
│   ├── pidrive_web.service     # Flask Web UI Port 8080
│   └── pidrive_avrcp.service   # AVRCP BMW iDrive
└── pidrive/
    ├── main_core.py         # Core: Trigger, Menü, Audio, Status-Thread
    ├── main_display.py      # Display: pygame auf fb1, 20fps
    ├── ipc.py               # IPC: atomares JSON /tmp/pidrive_*.json
    ├── menu_model.py        # Menübaum: MenuNode, MenuState, StationStore
    ├── mpris2.py            # MPRIS2 D-Bus → BMW-Display Metadaten
    ├── avrcp_trigger.py     # AVRCP 1.5 → File-Trigger
    ├── webui.py             # Flask Web UI Port 8080
    ├── status.py            # Status-Cache (Hintergrund-Thread)
    ├── log.py               # Logging (rotierend, max 512KB)
    ├── diagnose.py          # Diagnose-Script
    ├── modules/
    │   ├── musik.py         # Spotify Connect
    │   ├── webradio.py      # Webradio (mpv)
    │   ├── library.py       # MP3 Bibliothek mit Album-Art
    │   ├── dab.py           # DAB+ Radio (RTL-SDR + welle.io)
    │   ├── fm.py            # FM Radio (RTL-SDR + rtl_fm)
    │   ├── wifi.py          # WiFi Steuerung + Scan
    │   ├── bluetooth.py     # BT Scan, Connect, Audio-Routing
    │   ├── audio.py         # Audioausgang (Klinke/HDMI/BT)
    │   ├── favorites.py     # Favoritenliste (FM/DAB/Webradio)
    │   ├── scanner.py       # Funkscanner (PMR446/Freenet/LPD433/VHF/UHF)
    │   ├── system.py        # System-Info, Neustart
    │   └── update.py        # OTA Update via GitHub
    └── config/
        ├── stations.json        # Webradio-Stationen
        ├── dab_stations.json    # DAB+ Sender (nach Scan)
        ├── fm_stations.json     # FM Sender
        ├── favorites.json       # Favoritenliste
        └── settings.json        # Einstellungen (Audio, letzte Station)
```

---

## Menü-Struktur

Baumbasiert (v0.8.x) — beliebig tief, iDrive-kompatibel.

```
PiDrive  (v0.9.6 — Baumbasiert, beliebig tief)
├── Jetzt laeuft
│   ├── Quelle / Titel         (info)
│   ├── Spotify An/Aus         (toggle)
│   ├── Audioausgang           (action)
│   ├── Lauter / Leiser        (action)
│   └── Wiedergabe stoppen     (action)
├── Favoriten
│   ├── ★ Bayern 3             (station — FM)
│   ├── ★ BR Klassik           (station — DAB+)
│   └── ★ Radio BOB!           (station — Webradio)
├── Quellen
│   ├── Spotify
│   │   ├── Spotify An/Aus     (toggle)
│   │   └── Status             (info)
│   ├── Bibliothek
│   │   ├── Durchsuchen        (action → Dateiliste)
│   │   └── Stop               (action)
│   ├── Webradio
│   │   ├── Sender             (folder — aus stations.json)
│   │   │   ├── ★ Bayern 3 [Pop/Rock]    (station)
│   │   │   │   └── ★ Zu Favoriten       (action)
│   │   │   └── ...
│   │   └── Sender neu laden   (action)
│   ├── DAB+
│   │   ├── Sender             (folder — aus dab_stations.json)
│   │   │   ├── ★ Bayern 1 [11D]         (station)
│   │   │   │   └── ★ Zu Favoriten       (action)
│   │   │   └── ...
│   │   ├── Suchlauf starten   (action)
│   │   ├── Naechster / Vorheriger Sender (action)
│   ├── FM Radio
│   │   ├── Sender             (folder — aus fm_stations.json)
│   │   │   ├── ★ Bayern 3  99.4 MHz     (station)
│   │   │   │   └── ★ Zu Favoriten       (action)
│   │   │   └── ...
│   │   ├── Suchlauf starten   (action)
│   │   ├── Naechster / Vorheriger / Manuell (action)
│   └── Scanner
│       ├── PMR446 / Freenet / LPD433 / VHF / UHF
│       │   ├── Kanal +/−      (action)
│       │   └── Scan weiter/zurück (action)
├── Verbindungen
│   ├── Bluetooth An/Aus       (toggle)
│   ├── Geraete scannen        (action → 15s)
│   ├── Geraete                (folder — nach Scan)
│   │   ├── HD 4.40BT          (action → bt_connect:MAC)
│   │   └── ...
│   ├── Verbunden mit          (info)
│   ├── WiFi An/Aus            (toggle)
│   ├── Netzwerke scannen      (action)
│   ├── Netzwerke              (folder — nach Scan)
│   │   ├── Heimnetz           (action → wifi_connect:SSID)
│   │   └── ...
│   └── SSID                   (info)
└── System
    ├── IP Adresse             (info)
    ├── System-Info            (action)
    ├── Version                (action)
    ├── Neustart / Ausschalten (action)
    └── Update                 (action, OTA via GitHub)
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

## Steuerung

### Steuerung (File-Trigger / Web)

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
echo "cat:0"        > /tmp/pidrive_cmd   # Jetzt läuft
echo "cat:1"        > /tmp/pidrive_cmd   # Quellen
echo "cat:2"        > /tmp/pidrive_cmd   # Verbindungen
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
| Spotify kein Ton | Core ohne PULSE_SERVER | `PULSE_SERVER=unix:/var/run/pulse/native` in pidrive_core.service |
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

## Changelog

### v0.9.15 (2026-04-25)

**Ton auf Klinke für DAB/FM endgültig behoben:** mpv lief als root ohne
`PULSE_SERVER` → fand PulseAudio nicht → ALSA Card 0 (HDMI) → kein Ton.
Fix: `PULSE_SERVER=unix:/var/run/pulse/native PULSE_SINK=<sink>` als Shell-Env-Präfix.
Außerdem: DAB+ DLS-Metadaten (Lied/Artist), DAB-Menü nach Kanal gruppiert,
WebUI Menü-Baum live, Volume via `pactl list sinks`.

### v0.9.14 (2026-04-25)

**Persistenter BT-Agent + Bekannte Geräte + DAB dict.strip Fix:**
`svc.get("label",{}).strip()` → AttributeError behoben. BT-Icon dreistufig
(grau/blau/grün). pulse-access Gruppe für PulseAudio-Permissions. VERSION konsistent.

### v0.9.13 (2026-04-22)

**Klinken-Sink Card-Index-Fix:** `alsa_output.0.*` = HDMI (kein "hdmi" im Namen!).
`get_alsa_sink()` + `install.sh` + WebUI Sink-Typ nutzen jetzt Card-Nummer `.0.`/`.1.`
als Indikator. WebUI Lautstärke zeigt jetzt Wert auch wenn Default Sink leer.

### v0.9.12 (2026-04-21)

**BT-Diagnose vollständige Kette:** `check_bluetooth()` prüft rfkill, Controller BR/EDR-Fähigkeit,
system.pa BT-Module, BlueZ-DB Pairing-Keys, BT-Agent und BLE vs. Classic Hinweise.

### v0.9.11 (2026-04-21)

**Diagnose prüft Klinken-Kette vollständig:** `diagnose.py` prüft jetzt `system.pa`,
`aplay -l`, amixer Card 1, PulseAudio-Sinks und Routing als Kette mit Fix-Kommandos.

### v0.9.10 (2026-04-21)

**Root Cause kein Ton (endgültig):** `setup_bt_audio.sh` lud in `system.pa` nur
`module-alsa-card device_id=0` (HDMI) — Card 1 (Klinke) war nie als PA-Sink vorhanden.
Fix in `setup_bt_audio.sh`, `install.sh`, `audio.py`.

### v0.9.9 (2026-04-21)

**ALSA-Karten-Root-Cause — kein Ton endgültig behoben**

`aplay -l` zeigt: Card 0 = HDMI, Card 1 = Headphones/Klinke. Alle bisherigen
amixer-Befehle (`-c 0`) trafen HDMI statt Klinke. Fix: `/etc/asound.conf`
(`defaults.pcm.card 1`), `_get_headphone_card()` per `aplay -l`,
`get_alsa_sink()` filtert HDMI-Sinks aus.

### v0.9.8 (2026-04-21)

**Kein Ton (PCM-Unmute) & BT-Pairing-Fix**

- `modules/audio.py`: `amixer numid=2` (PCM Mute Switch) war nie auf unmute gesetzt → kein Ton trotz korrektem Routing; Fix: `amixer sset 'PCM' 85% unmute` (name-basiert, kernelversionsunabhängig)
- `modules/bluetooth.py`: Nach `bluetoothctl remove` war Gerät nicht mehr in BlueZ → 10s Mini-Scan zu kurz; Fix: Polling alle 2s bis 20s + Abort wenn nicht gefunden  
- `modules/bluetooth.py`: `repair()` + paralleles "Verbinden" starteten zwei `connect_device()`-Threads → Race Condition; Fix: `threading.Lock`
- `install.sh`: Boot-Setup setzt jetzt `amixer sset 'PCM' 85% unmute`

### v0.9.7 (2026-04-21)

**Audio-Fixes & BT-Stabilität**

- `audio.py`: `set_default_sink()` verschiebt jetzt laufende Sink-Inputs (`pactl move-sink-input`) — behebt "kein Ton" wenn mpv vor dem Routing-Wechsel gestartet wurde
- `audio.py`: `_set_pi_output_klinke()` setzt jetzt auch ALSA PCM-Volume (numid=1=340 ≈ 85%) — behebt fehlenden Ton bei fehlendem Hardware-Volumen
- `audio.py`: `volume_up/down/apply_startup_volume` nutzen echten Sink-Namen statt `@DEFAULT_SINK@` (der bei fehlendem Default leer ist)
- `main_core.py`: `apply_startup_volume()` wird jetzt beim Boot aufgerufen (war definiert aber nie aufgerufen)
- `main_core.py`: `audio_select` Trigger crashte auf nicht-existente `select_output_interactive()` — behoben mit Menü-Navigation
- `bluetooth.py`: `_ensure_agent()` nutzt jetzt `printf ... | bluetoothctl` statt `communicate()` (behebt systematisches WARNING "default-agent nicht bestätigt")
- `bluetooth.py`: BT-Scan Dauer 15s → 25s (Kopfhörer brauchen oft länger bis sichtbar)
- `bluetooth.py`: Scan-Abschluss-Feedback klarer ("X Geräte gefunden — Geraete > Verbinden")
- `status.py`: `bt_on` (Adapter-State) neu im S-Dict — unterscheidet "Adapter AN" von "verbunden"
- `main_display.py`: BT-Icon dreistufig: Grau=aus, Blau=Adapter AN/kein Gerät, Grün=verbunden
- `menu_model.py`: `bt_geraete` direkt nach `bt_scan` — Cursor landet nach Scan sofort auf Geräteliste

### v0.9.6 (2026-04-21)
- **State-Machine vervollständigt:** Spotify, Library, DAB-Scan, lib_browse über `begin/commit/end_transition`
- **`boot_phase` korrekt:** `restore_bt` → `restore_source` → `steady` in `startup_tasks()`
- **`audio_route` live:** `audio.py` spiegelt `effective` in `source_state` (klinke/bt/hdmi/none)
- **DAB Lock-Status:** `_lock_state_name()` mit `no_signal/no_fct0_lock/fic_only/ensemble_locked/services_found`
- **`NO_FCT0_LOCK` Warning:** explizite Warnung wenn `lastfct0==0` bei SNR≥2
- **FM/DAB Start-Guard:** verhindert unnötige Neustarts gleicher Station
- **WebUI Runtime-Panel:** `/api/runtime` liefert alle Settings inkl. DAB-Scan-Parameter
- **WebUI Source-State sichtbar:** `get_source_state_debug()` in View-Model und API
- **WebUI DAB-Scan-Diagnose:** `get_dab_scan_debug()`, `/api/dab/scan/last`, Tabelle mit Lock-Spalte
- **WebUI Spectrum-Last:** `get_spectrum_debug()`, `/api/spectrum/last`
- **Diagnose robuster:** Default-Sink Fallback, amixer Parse (`0x1`→`1`), Plausibilitätsprüfung Klinke
- **spectrum.py Phase 2:** `_dedupe_peaks()`, `min_distance_bins`, kompaktere FM-Kandidatenliste
- **install.sh:** Log-Prüfung robust (`tail -80 | grep -E`), numpy-Fix für Bullseye/Python 3.9

### v0.7.20 — Web UI
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
- Spotify: PulseAudio Default-Sink (LIBRESPOT_DEVICE=default)
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

| Priorität | Feature | Status |
|---|---|---|
| 🔧 Kurzfristig | GPIO-Buttons (Key1-3) | offen |
| ✅ Erledigt | Audio-Routing (Webradio/FM/DAB auf BT) | v0.9.6 |
| 🔧 Kurzfristig | resume_state.py (Boot-Resume) | offen |
| 🔧 Kurzfristig | USB-Tethering Autostart | offen |
| 🔧 Kurzfristig | WebUI Breadcrumb-Navigation | offen |
| 🚗 Mittelfristig | BMW AVRCP Praxistest im Auto | offen |
| 🚗 Mittelfristig | DAB+ DLS / FM RDS Text | offen |
| 🚗 Mittelfristig | Equalizer, Hotspot-Modus | offen |
| 🔭 Langfristig | OBD2 Fahrzeugdaten (ELM327) | offen |
| 🔭 Langfristig | BMW iPod-Emulation (IAP2) | offen |
| 🔭 Langfristig | Spotify Web API | offen |

Vollständige Roadmap mit erledigten Punkten: [KontextPiDrive.md](KontextPiDrive.md#roadmap)


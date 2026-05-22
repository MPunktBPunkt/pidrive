# PiDrive 🚗🎵

Raspberry Pi Car Infotainment — Spotify Connect · Webradio · DAB+ · FM · Bluetooth  
für **BMW iDrive** (NBT EVO) und ähnliche Systeme.

[![Version](https://img.shields.io/badge/version-0.11.46-orange.svg)](https://github.com/MPunktBPunkt/pidrive/blob/main/pidrive/VERSION)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python 3](https://img.shields.io/badge/python-3.13-green.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-Debian%2013%20%7C%20Raspberry%20Pi%20OS-lightgrey.svg)](https://www.debian.org/)

---

## Was ist PiDrive?

PiDrive verwandelt einen Einplatinen-Rechner in ein Car-Infotainment-System.  
Steuerung erfolgt über **BMW iDrive AVRCP** (Lenkrad/Drehsteller), **WebUI** (Port 8080) oder **CLI**.  
Kein Display nötig — der Fujitsu Futro S920 / HP T630 oder ein Raspberry Pi 4 genügt.

**Audioquellen:**
- 🎵 **Spotify Connect** (Raspotify / librespot)
- 📻 **Webradio** (mpv, konfiguierbare Stationen)
- 📡 **DAB+** (RTL-SDR + welle-cli)
- 🔊 **FM Radio** (RTL-SDR + rtl_fm)

**Steuerung:**
- BMW iDrive → Bluetooth AVRCP → `pidrive_avrcp.service` → Trigger
- `pidrivectl` CLI (vollständige Kontrolle via SSH)
- WebUI auf Port 8080

---

## Schnellinstallation

```bash
curl -sL https://raw.githubusercontent.com/MPunktBPunkt/pidrive/main/install.sh | bash
```

Als `root` ausführen — `sudo` wird nicht benötigt und ist auf minimalen Systemen meist nicht installiert.  
Der Installer erkennt automatisch die Plattform (Pi / x86, Container / Bare Metal).

**Nach der Installation:**
```bash
pidrivectl status          # System-Status
pidrivectl play web 1      # Ersten Webradio-Sender starten
pidrivectl bt scan         # Bluetooth-Geräte suchen
```

**WebUI:** `http://<IP>:8080`

---

## Hardware

| Komponente | Details |
|---|---|
| Primär (Entwicklung) | Fujitsu Futro S920 · Debian 13 · x86_64 |
| Geplant (Fahrzeug) | Raspberry Pi 4 · Raspberry Pi OS |
| RTL-SDR | RTL2838 DVB-T Stick (DAB+ · FM) |
| Bluetooth | Cambridge Silicon Radio Dongle (oder eingebaut) |
| Audio-Ausgang | 3.5mm Klinke → AUX-IN · Bluetooth A2DP |
| Stromversorgung | 12V KFZ → USB-Adapter 5V/3A |

### Verbindung im Auto

```
Pi/x86 ──[3.5mm Klinke]──────────────── Auto AUX-IN oder Verstärker
Pi/x86 ──[Bluetooth A2DP]────────────── BMW Audio-System
Pi/x86 ──[USB/WLAN]──── SSH/WebUI ───── Entwicklung & Wartung
BMW iDrive ──[BT AVRCP]──────────────── Steuerung (Tasten → Trigger)
```

---

## pidrivectl — Befehlsreferenz

### Status

```bash
pidrivectl status             # Quelle, Titel, Lautstärke, BT, WiFi
pidrivectl now                # Was läuft gerade? (Titel + Metadaten)
pidrivectl quick              # Kompakte Einzeile
pidrivectl version            # Versionsnummer
```

### Wiedergabe

```bash
pidrivectl play dab "ROCK FM" # DAB+ Sender nach Name
pidrivectl play dab 27        # Sender #27 aus Senderliste
pidrivectl play web "Bayern 1"# Webradio nach Name
pidrivectl play web 3         # Webradio #3 aus Liste
pidrivectl play fm 104.4      # FM-Frequenz in MHz
pidrivectl play fm 1          # FM-Sender #1 aus fm_stations.json
pidrivectl play spotify       # Spotify Connect aktivieren
pidrivectl stop               # Wiedergabe stoppen
```

### Lokale Musikwiedergabe

```bash
pidrivectl play local /home/pidrive/Musik/song.mp3   # Einzeldatei
pidrivectl play local /home/pidrive/Musik/            # Ganzer Ordner
pidrivectl play local /home/pidrive/Musik/list.m3u   # M3U-Playlist
pidrivectl play local /home/pidrive/Musik/ --shuffle  # Zufallswiedergabe
```

Unterstützte Formate: `.mp3` `.flac` `.ogg` `.m4a` `.aac` `.wav` `.opus`  
Audio läuft über den gleichen PulseAudio-Pfad wie Webradio (BT/Klinke).

### Senderlisten

```bash
pidrivectl station list dab   # DAB+-Stationen (★ = Favorit)
pidrivectl station list fm    # FM-Stationen aus fm_stations.json
pidrivectl station list web   # Webradio-Stationen
pidrivectl station list local # Lokale Musikdateien in ~/Musik
```

### Favoriten

```bash
pidrivectl favorites list        # Favoritenliste anzeigen
pidrivectl favorites add         # Aktuellen Sender als Favorit speichern
pidrivectl favorites remove 1    # Favorit #1 entfernen
pidrivectl favorites play 1      # Favorit #1 abspielen
```

### Bluetooth

```bash
pidrivectl bt scan               # Scan starten (22s, Live-Ergebnisse)
pidrivectl bt pair <mac|name>    # Gerät koppeln (Pairing-Modus nötig!)
pidrivectl bt connect <mac>      # Verbinden
pidrivectl bt known              # Bekannte / gepaarte Geräte
pidrivectl bt status             # Verbindungsstatus + Agent
pidrivectl bt reconnect          # Letztes Gerät neu verbinden
```

### Audio & Lautstärke

```bash
pidrivectl volume up             # Lautstärke erhöhen
pidrivectl volume down           # Lautstärke senken
pidrivectl volume set 70         # Direkt auf 70% setzen
pidrivectl audio route klinke    # Ausgang: klinke | bt | hdmi | auto
pidrivectl audio status          # Aktueller Ausgang, Sink, BT-Status
pidrivectl audio test            # 440 Hz Testton (3 Sekunden)
```

### DAB+

```bash
pidrivectl dab status            # Empfangsstatus (Lock, SNR, Fehler)
pidrivectl dab live              # Live-Metadaten-Stream
pidrivectl dab live --once       # Einmalig ausgeben
pidrivectl dab live --changes    # Nur bei Änderungen (DLS/Titel)
pidrivectl dab scan              # Sendersuchlauf mit Live-Feedback
pidrivectl dab stop              # DAB-Wiedergabe stoppen
```

### Scanner (PMR/VHF/UHF/CB/FM)

```bash
pidrivectl scanner               # Status + alle verfügbaren Bänder
pidrivectl scanner pmr446 scan   # Band scannen (pmr446 | vhf | uhf | cb | fm | freenet | lpd433)
pidrivectl scanner pmr446 ch 1   # Direkt auf Kanal 1 springen
pidrivectl scanner pmr446 freq 446.0  # Direkt auf Frequenz (MHz)
pidrivectl scanner pmr446 next   # Nächster Kanal
pidrivectl scanner pmr446 prev   # Vorheriger Kanal
pidrivectl scanner squelch 25    # Squelch-Level (0=aus, 25=normal, 50=streng)
pidrivectl scanner ppm 49        # PPM-Korrektur für RTL-SDR
pidrivectl scanner stop          # Scanner stoppen
```

### PPM-Kalibrierung (RTL-SDR)

```bash
pidrivectl ppm                   # Aktuellen PPM-Wert anzeigen
pidrivectl ppm set 49            # PPM-Offset manuell setzen
pidrivectl ppm calibrate         # Automatische Kalibrierung (braucht Signal)
```

### AVRCP (BMW iDrive)

```bash
pidrivectl avrcp                 # Live-Monitor: BMW-Tasten in Echtzeit
pidrivectl avrcp monitor         # Gleichbedeutend mit avrcp
pidrivectl avrcp status          # Letztes empfangenes AVRCP-Event
pidrivectl avrcp events          # Ringpuffer der letzten 20 Events
pidrivectl avrcp inject next     # Trigger simulieren (ohne BMW testen)
pidrivectl debug avrcp           # AVRCP-Debug-Modus
pidrivectl debug inject <trigger># Beliebigen Trigger direkt injizieren
```

### System, Diagnose, Logs

```bash
pidrivectl system                # Allgemeine System-Info
pidrivectl system resources      # RAM, SD-Karte, Uptime, CPU-Temp
pidrivectl system diagnose       # Vollständige Systemdiagnose
pidrivectl log                   # Core-Log (letzte 40 Einträge)
pidrivectl log core              # Core-Service-Log
pidrivectl log app               # App-Log
pidrivectl log avrcp             # AVRCP-Service-Log
```

### Wiedergabe-Playlist

```bash
pidrivectl playlist today        # Gestreamte Sender/Titel heute
pidrivectl playlist all          # Gesamte Playlist-History
pidrivectl playlist last         # Letzte Session
pidrivectl playlist 2026-05-17   # Playlist für bestimmtes Datum
```

---

## Architektur

```
BMW iDrive (AVRCP)
    │
    ▼
avrcp_trigger.py ──► /tmp/pidrive_cmd ──► main_core.py
                                               │
                      ┌────────────────────────┤
                      │                        │
               WebUI (Port 8080)         trigger/
               pidrivectl CLI            td_radio / td_nav / td_hardware
                                               │
                                    modules/radio/  modules/bluetooth/
                                    modules/audio/  modules/platform/
                                               │
                                    rtl_fm · welle-cli · mpv · librespot
```

**CAPS-System (`modules/platform.py`):** Plattform-Fähigkeiten werden beim Start einmalig ermittelt.  
Alle Subsysteme prüfen `CAPS["rtlsdr"]`, `CAPS["bluetooth"]` etc. statt `/proc/cpuinfo`.

---

## Dienste

| Service | Funktion |
|---|---|
| `pidrive_core.service` | Haupt-Core (Wiedergabe, Menü, Trigger) |
| `pidrive_web.service` | WebUI + REST-API (Port 8080) |
| `pidrive_avrcp.service` | BMW iDrive AVRCP → Trigger |
| `pulseaudio.service` | System-Mode PulseAudio |

```bash
systemctl status pidrive_core
journalctl -u pidrive_core -f
```

---

## IPC-Dateien (`/tmp/`)

| Datei | Inhalt |
|---|---|
| `pidrive_cmd` | Trigger-Datei (0660 root:pidrive) |
| `pidrive_status.json` | Wiedergabe, BT, WiFi |
| `pidrive_source_state.json` | Aktive Quelle, Transitions |
| `pidrive_avrcp_events.json` | AVRCP Ringbuffer (30 Events) |
| `pidrive_avrcp_status.json` | Letztes AVRCP-Event |

---

## Konfiguration

`/opt/pidrive/pidrive/config/settings.json` (Root-Install) bzw.  
`/home/pidrive/pidrive/pidrive/config/settings.json` (User-Install)

Wichtige Keys:

```json
{
  "audio_out": "auto",
  "startup_volume": 75,
  "bt_last_mac": "00:16:94:2E:85:DB",
  "dab_ppm": 49,
  "fm_ppm": 49
}
```

---

## Plattformen

PiDrive läuft auf **Debian 13** (x86_64) und **Raspberry Pi OS** ohne Code-Änderungen.  
Der Installer erkennt automatisch:

| Merkmal | Verhalten |
|---|---|
| Pi vs. x86 | RPi.GPIO nur auf ARM; fbcon-Konfiguration nur auf Pi |
| Container (LXC) | Null-Sink für PulseAudio; fake-hwclock übersprungen |
| User vs. root | INSTALL_DIR: `/home/<user>/pidrive` vs. `/opt/pidrive` |
| librespot | Auf ARM: Raspotify; auf x86: Binary von GitHub (automatisch) |

## Spotify Connect einrichten

### Installation (automatisch via Installer)

Der Installer lädt librespot automatisch von GitHub und richtet `librespot.service` ein.

```bash
curl -sL https://raw.githubusercontent.com/MPunktBPunkt/pidrive/main/install.sh | bash
```

### OAuth (einmalig, nach librespot-Installation)

```bash
pidrivectl system spotify-oauth
```

Es erscheint eine Browser-URL. Diese auf einem PC oder Handy im selben Netzwerk öffnen.

**Falls Verbindungsfehler:** SSH-Tunnel nutzen:
```bash
# Auf dem Windows-PC (zweites Terminal):
ssh -L 5588:127.0.0.1:5588 pidrive@192.168.178.100
# Dann die URL im Browser öffnen (127.0.0.1:5588 bleibt unverändert)
```

Nach dem Spotify-Login → `Strg+C` → Token wird in `/var/cache/librespot/credentials.json` gespeichert.

### Spotify verwenden

```bash
pidrivectl play spotify    # Spotify Connect aktivieren
```

Dann in der Spotify-App das Gerät **PiDrive** auswählen.

### Status prüfen

```bash
pidrivectl system          # zeigt Spotify: aktiv ✓ [librespot]
```

---

## Entwicklung

```bash
# Status live verfolgen
pidrivectl log               # Core-Log
journalctl -u pidrive_core -f

# Trigger manuell senden
echo "play_dab:ROCK FM" > /tmp/pidrive_cmd
echo "vol_up" > /tmp/pidrive_cmd

# AVRCP ohne BMW testen
pidrivectl avrcp inject next
pidrivectl avrcp monitor

# Diagnose
pidrivectl system diagnose
```

**Repo:** https://github.com/MPunktBPunkt/pidrive  
**Dokumentation:** `KontextPiDrive.md` (Projekthistorie, Entscheidungen, Bugs)

---

## Lizenz

GPL v3 — siehe [LICENSE](LICENSE)

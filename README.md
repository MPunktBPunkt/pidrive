# PiDrive 🚗🎵

Raspberry Pi Car Infotainment — Spotify Connect · Webradio · DAB+ · FM · Bluetooth  
für **BMW iDrive** (NBT EVO) und ähnliche Systeme.

[![Version](https://img.shields.io/badge/version-0.11.60-orange.svg)](https://github.com/MPunktBPunkt/pidrive/blob/main/pidrive/VERSION)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python 3](https://img.shields.io/badge/python-3.13-green.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-Debian%2013%20%7C%20Raspberry%20Pi%20OS-lightgrey.svg)](https://www.debian.org/)

---

## Was ist PiDrive?

PiDrive verwandelt einen Einplatinen-Rechner in ein Car-Infotainment-System.  
Steuerung über **BMW iDrive AVRCP** (Lenkrad/Drehsteller), **WebUI** (Port 8080) oder **CLI**.  
Kein Display nötig — ein Raspberry Pi 4 oder x86-Minirechner genügt.

**Audioquellen:**
- 🎵 **Spotify Connect** (Raspotify / librespot)
- 📻 **Webradio** (mpv, 13 konfigurierte Sender)
- 📡 **DAB+** (RTL-SDR + welle-cli)
- 🔊 **FM Radio** (RTL-SDR + rtl_fm)
- 🔍 **Funk-Scanner** (PMR446, VHF, UHF, CB, FM)
- 💾 **Lokale Musik** (MP3/FLAC/OGG von USB-Stick oder Festplatte)

**Audio-Stack:** PipeWire System-Mode (ab v0.11.60) — effizient, konfliktfrei, BT-stabil.

---

## Schnellinstallation

```bash
curl -sL https://raw.githubusercontent.com/MPunktBPunkt/pidrive/main/install.sh | bash
sudo reboot
```

Als `root` ausführen. Der Installer erkennt automatisch Pi / x86, Container / Bare Metal.

```bash
pidrivectl status          # System-Status prüfen
pidrivectl test all        # Komplett-Test aller Funktionen
pidrivectl play web 9      # Rock Antenne starten
pidrivectl bt scan         # Bluetooth-Geräte suchen
```

**WebUI:** `http://<IP>:8080`

---

## Hardware

| Komponente | Details |
|---|---|
| Fahrzeug | Raspberry Pi 4 · Raspberry Pi OS · Kühlkörper erforderlich |
| Entwicklung | Fujitsu Futro S920 · Debian 13 · x86_64 |
| RTL-SDR | RTL2838 DVB-T Stick (DAB+ · FM · Scanner) |
| Bluetooth | Cambridge Silicon Radio Dongle (oder eingebaut) |
| Audio | 3.5mm Klinke → AUX-IN **oder** Bluetooth A2DP → BMW |
| Netzteil | 5V/3A USB-C (Pi 4 offiziell) — kein Billig-Ladekabel! |

> **Temperatur:** Pi 4 braucht Kühlkörper. Ohne Kühlung throttelt er bei 80°C.  
> Empfohlen: Argon NEO Gehäuse oder Pimoroni Fan SHIM für Fahrzeugbetrieb.

---

## Dienste

| Service | Funktion |
|---|---|
| `pidrive_core.service` | Haupt-Core (Wiedergabe, Menü, Trigger) |
| `pidrive_web.service` | WebUI + REST-API (Port 8080) |
| `pidrive_avrcp.service` | BMW iDrive AVRCP → Trigger |
| `pipewire.service` | Audio-Server (System-Mode) |
| `pipewire-pulse.service` | PulseAudio-Compat-Layer (Socket: /var/run/pulse/native) |
| `wireplumber.service` | Session-Manager (BT A2DP automatisch) |

---

## pidrivectl — Kurzreferenz

### Status & Test

```bash
pidrivectl status             # Quelle, Titel, Lautstärke, BT, WiFi
pidrivectl now                # Was läuft gerade?
pidrivectl quick              # Kompakte Einzeile
pidrivectl test all           # Komplett-Systemtest (alle Quellen + Audio + BT + AVRCP)
pidrivectl test system        # Nur System-Ressourcen
```

### Wiedergabe

```bash
pidrivectl play web "Bayern 1"   # Webradio
pidrivectl play web 9            # Webradio #9 (Rock Antenne)
pidrivectl play dab "ROCK FM"    # DAB+ nach Name
pidrivectl play dab 27           # DAB+ nach Nummer
pidrivectl play fm 104.4         # FM-Frequenz
pidrivectl play spotify          # Spotify Connect aktivieren
pidrivectl play local /pfad/     # Lokale Musik [--shuffle]
pidrivectl stop
```

### Bluetooth

```bash
pidrivectl bt scan               # Scan (22s, Live)
pidrivectl bt pair <mac|name>    # Pairing (Gerät vorher in Pairing-Modus!)
pidrivectl bt connect <mac>      # Verbinden
pidrivectl bt known              # Bekannte Geräte (mit Typ: [AVRCP] / [Kopfhörer])
pidrivectl bt status
```

### Audio

```bash
pidrivectl audio route bt|klinke|hdmi|auto
pidrivectl audio test            # 440 Hz Testton
pidrivectl volume set 70
pidrivectl volume up / down
```

### AVRCP (BMW iDrive)

```bash
pidrivectl avrcp                 # Live-Monitor BMW-Tasten
pidrivectl avrcp inject next     # Trigger simulieren
pidrivectl debug mpris status    # MPRIS2 D-Bus + IP anzeigen
pidrivectl debug mpris push --title "Test"  # Test-Metadaten ans BMW
```

### Scanner

```bash
pidrivectl scanner pmr446 scan   # Band scannen
pidrivectl scanner pmr446 ch 3   # Direkt auf Kanal 3
pidrivectl scanner fm freq 104.4 # FM-Scanner auf Frequenz
pidrivectl scanner squelch 0     # Squelch deaktivieren (Test)
```

### System & Diagnose

```bash
pidrivectl system                # PipeWire, Spotify, Core-Status
pidrivectl system resources      # RAM, Disk, Temp, Throttling
pidrivectl system diagnose       # Volldiagnose
pidrivectl log                   # Core-Log
```

---

## Architektur

```
BMW iDrive (AVRCP) ──[BT]──► integration/avrcp_trigger.py
WebUI (Port 8080) ──────────► web/api/
pidrivectl CLI ─────────────► cli/
                                    │
                               /tmp/pidrive_cmd (append-Queue)
                                    │
                              main_core.py
                             trigger_dispatcher.py
                          ┌───┬───┬────┬──────┐
                       td_nav td_radio td_hw td_scanner td_system
                                    │
                    modules/radio/  modules/bluetooth/  modules/audio/
                    rtl_fm · welle-cli · mpv · librespot
                                    │
                    PipeWire (System-Mode) ──► BT A2DP (BMW)
                                              ALSA (Klinke/HDMI)

mpris2.py ──► org.mpris.MediaPlayer2.pidrive (System-D-Bus)
              BlueZ liest Properties ──► BMW-Display zeigt Metadaten
```

---

## Spotify Connect einrichten

```bash
# OAuth einmalig (nach librespot-Installation):
pidrivectl system spotify-oauth

# SSH-Tunnel falls Browser nicht erreichbar:
# (auf Windows-PC:) ssh -L 5588:127.0.0.1:5588 pidrive@<PI-IP>
# Dann URL im Browser öffnen
```

Token wird in `/var/cache/librespot/credentials.json` gespeichert.

---

## WiFi-IP im BMW-Display

Beim Verbinden mit einem Hotspot zeigt PiDrive für 8 Sekunden:
```
Zeile 1: SSH: 192.168.43.105
Zeile 2: ssh pidrive@192.168.43.105  
Zeile 3: WiFi: IPhone-Hotspot
```

Manuell: `pidrivectl debug mpris status` zeigt IP + SSH-Adresse.

---

## IPC-Dateien (`/tmp/`)

| Datei | Inhalt |
|---|---|
| `pidrive_cmd` | Trigger-Queue (append-only, 0660 root:pidrive) |
| `pidrive_status.json` | Wiedergabe, BT, WiFi |
| `pidrive_source_state.json` | Aktive Quelle, boot_phase |
| `pidrive_avrcp_events.json` | AVRCP Ringbuffer (30 Events) |
| `pidrive_test_results.json` | Ergebnis von `pidrivectl test all` |

---

## Entwicklung

```bash
# Trigger manuell senden
printf "play_web:Rock Antenne\n" >> /tmp/pidrive_cmd

# AVRCP ohne BMW testen
pidrivectl avrcp inject next
pidrivectl avrcp monitor

# MPRIS2 debuggen
pidrivectl debug mpris status
pidrivectl debug mpris push --title "Bayern 3" --artist "Test"

# Vollständiger System-Check
pidrivectl test all
cat /tmp/pidrive_test_results.json | python3 -m json.tool
```

**Log (INFO-Level):** `tail -f /var/log/pidrive/pidrive.log`  
**Dokumentation:** `KontextPiDrive.md` (Architektur, Entscheidungen, Bugs)

---

## Lizenz

GPL v3 — siehe [LICENSE](LICENSE)

# PiDrive 🚗🎵

Raspberry Pi Car Infotainment — Spotify Connect · Webradio · DAB+ · FM · Bluetooth  
für **BMW iDrive** (NBT EVO) und ähnliche Systeme.

[![Version](https://img.shields.io/badge/version-0.11.24-orange.svg)](https://github.com/MPunktBPunkt/pidrive/blob/main/pidrive/VERSION)
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

```bash
# Status
pidrivectl status                    # Quelle, Titel, Lautstärke, BT, WiFi
pidrivectl now                       # Was läuft gerade?
pidrivectl quick                     # Kompakte Einzeile

# Wiedergabe
pidrivectl play dab "ROCK FM"        # DAB+ Sender starten
pidrivectl play dab 27               # Sender #27 aus Liste
pidrivectl play web "Bayern 1"       # Webradio starten
pidrivectl play web 3                # Webradio #3 aus Liste
pidrivectl play fm 104.4             # FM Frequenz
pidrivectl play spotify              # Spotify Connect aktivieren
pidrivectl stop                      # Alles stoppen

# Sender
pidrivectl station list dab          # DAB-Senderliste (★ = Favorit)
pidrivectl station list web          # Webradio-Liste
pidrivectl dab scan                  # Sendersuchlauf (Live-Feedback)
pidrivectl dab status                # Empfangsstatus (Lock, PCM, Fehler)

# Bluetooth
pidrivectl bt scan                   # Scan (22s, Live-Ergebnisse)
pidrivectl bt pair <mac|name>        # Koppeln (Gerät in Pairing-Modus!)
pidrivectl bt connect <mac>          # Verbinden
pidrivectl bt status                 # Verbindungsstatus
pidrivectl bt known                  # Bekannte Geräte

# Audio
pidrivectl audio route klinke        # Ausgang: klinke | bt | hdmi | auto
pidrivectl audio status              # Aktueller Ausgang
pidrivectl audio test                # 440 Hz Testton (3s)
pidrivectl volume up / down          # Lautstärke
pidrivectl volume 70                 # Direkt auf 70%
pidrivectl ppm set 49               # RTL-SDR PPM-Offset
pidrivectl ppm calibrate            # Automatische Kalibrierung

# AVRCP (BMW iDrive)
pidrivectl avrcp                     # Live-Monitor BMW iDrive Tasten
pidrivectl avrcp status              # Letztes AVRCP-Event
pidrivectl avrcp inject next         # Trigger simulieren (ohne BMW testen)

# System
pidrivectl system                    # System-Info
pidrivectl system resources          # RAM, Speicher, Uptime
pidrivectl system diagnose           # Vollständige Diagnose
pidrivectl log                       # Core-Log (letzte 40 Einträge)
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
| librespot | Auf ARM: Raspotify; auf x86: apt oder cargo-Build |

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

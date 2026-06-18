# PiDrive

**Raspberry-Pi Car Infotainment für BMW iDrive (NBT Evo) und ähnliche Systeme.**

Spotify Connect · Webradio · DAB+ · FM · Funk-Scanner · Bluetooth A2DP · lokale Musik — gesteuert über Lenkrad (AVRCP), WebUI oder CLI. Kein Display nötig.

[![Version](https://img.shields.io/badge/version-0.11.105-orange.svg)](https://github.com/MPunktBPunkt/pidrive/blob/main/pidrive/VERSION)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python 3](https://img.shields.io/badge/python-3.11%2B-green.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-Raspberry%20Pi%20OS%20%7C%20Debian-lightgrey.svg)](https://www.debian.org/)

---

## Highlights

| Feature | Beschreibung |
|---------|--------------|
| **DAB+** | RTL-SDR + welle-cli, Senderliste, DLS (Titel/Interpret) |
| **Webradio** | mpv, kuratierte Rock-Sender, Metadaten ans BMW |
| **FM & Scanner** | rtl_fm, PMR446 / VHF / UHF / CB |
| **Spotify Connect** | librespot / Raspotify |
| **BMW iDrive** | AVRCP-Steuerung + MPRIS2-Metadaten auf dem Display |
| **Audio** | PipeWire System-Mode — Klinke, HDMI oder BT A2DP |

> **v0.11.104:** DAB State-Machine vereinheitlicht; Spotify-Trigger und librespot-Status gefixt.

---

## Schnellstart

### Installation

```bash
curl -sL https://raw.githubusercontent.com/MPunktBPunkt/pidrive/main/install.sh | bash
sudo reboot
```

Als `root` ausführen. Der Installer erkennt Raspberry Pi und x86 automatisch.

### Erste Schritte nach dem Boot

```bash
pidrivectl version          # Version prüfen (sollte 0.11.103 sein)
pidrivectl status           # System-Status
pidrivectl test all         # Komplett-Test aller Quellen
pidrivectl play web 1       # Webradio Rock Antenne
pidrivectl play dab 22      # DAB+ (Sender nach Scan/Nummer)
```

**WebUI:** `http://<Pi-IP>:8080`

---

## Audioquellen

### Webradio

```bash
pidrivectl play web 1              # Nach Nummer (1–20 Rock-Sender)
pidrivectl play web "Rock Antenne"   # Nach Name
```

### DAB+

Voraussetzung: RTL-SDR Stick (z. B. RTL2838), Antenne am Fenster hilft beim ersten Lock.

```bash
pidrivectl dab scan                # Sender scannen (einmalig / nach Umzug)
pidrivectl play dab 22             # Sender #22 aus dab_stations.json
pidrivectl play dab "DIE NEUE 107.7"
pidrivectl dab status              # Sync, PCM, Fehler
pidrivectl dab live                # Live-Monitor (Ctrl+C beenden)
pidrivectl dab stop
```

Typischer Ablauf: nach `play dab` 15–45 s warten bis Lock + PCM. DLS erscheint in `pidrivectl now` und auf dem BMW-Display.

**Diagnose bei Problemen:**

```bash
grep -E 'Superframe|pcm name|DLS:' /tmp/pidrive_dab_welle.err | tail -5
cat /tmp/pidrive_dab_play_debug.json | python3 -m json.tool | head -40
pidrivectl log | grep DAB | tail -15
```

Manueller Referenztest (RTL-SDR darf nicht von PiDrive belegt sein):

```bash
pidrivectl dab stop
sudo welle-cli -F rtl_sdr -T -c 11B -g -1 -p 'DIE NEUE 107.7'
```

### FM & Scanner

```bash
pidrivectl play fm 104.4
pidrivectl scanner pmr446 scan
pidrivectl scanner fm freq 98.5
```

### Spotify & lokale Musik

```bash
pidrivectl play spotify
pidrivectl play local /pfad/zur/musik/ [--shuffle]
pidrivectl stop
```

---

## Bluetooth & BMW iDrive

```bash
pidrivectl bt scan
pidrivectl bt pair <name|mac>      # BMW vorher in Kopplungsmodus
pidrivectl bt connect <mac>
pidrivectl audio route bt          # oder klinke / hdmi / auto
pidrivectl avrcp                   # Live-Monitor Lenkrad-Tasten
pidrivectl debug mpris push --title "Test" --artist "PiDrive"
```

Beim Hotspot-Verbinden zeigt PiDrive kurz die SSH-IP auf dem BMW-Display.

---

## pidrivectl — Referenz

| Bereich | Befehle |
|---------|---------|
| **Status** | `status` · `now` · `quick` · `version` · `playlist` |
| **Wiedergabe** | `play web\|dab\|fm\|spotify\|local` · `stop` |
| **DAB** | `dab scan` · `dab status` · `dab live` · `dab stop` · `test dab` |
| **Audio** | `audio route …` · `audio test` · `volume set/up/down` |
| **BT** | `bt scan` · `pair` · `connect` · `known` · `status` |
| **System** | `system` · `system diagnose` · `log` · `test all` |

Ausführliche Hilfe: `pidrivectl --help`

---

## Hardware

| Komponente | Empfehlung |
|------------|------------|
| **Rechner** | Raspberry Pi 4 (2 GB+), aktives Kühlgehäuse |
| **Netzteil** | 5 V / 3 A USB-C (offiziell) |
| **RTL-SDR** | RTL2838 (DAB+, FM, Scanner) |
| **Bluetooth** | CSR-Dongle oder integriert |
| **Audio** | 3,5 mm Klinke → AUX **oder** BT A2DP → BMW |
| **Fahrzeug** | BMW 118d F20/F21 LCI · NBT Evo (getestet) |

> Pi 4 ohne Kühlung drosselt ab ~80 °C — im Auto Argon NEO oder Lüfter empfohlen.

---

## Systemd-Dienste

| Service | Aufgabe |
|---------|---------|
| `pidrive_core.service` | Core-Loop, Wiedergabe, Menü, Trigger |
| `pidrive_web.service` | WebUI + REST-API (Port 8080) |
| `pidrive_avrcp.service` | BMW AVRCP → Trigger-Queue |
| `pipewire.service` | Audio-Server (System-Mode) |
| `pipewire-pulse.service` | PulseAudio-Kompatibilität (`/var/run/pulse/native`) |
| `wireplumber.service` | Session-Manager, BT A2DP |

```bash
sudo systemctl status pidrive_core
sudo systemctl restart pidrive_core    # nach git pull
```

---

## Architektur (Kurz)

```
BMW iDrive (AVRCP) ──► avrcp_trigger ──► /tmp/pidrive_cmd
WebUI :8080 ─────────► web/app.py ──────►     │
pidrivectl CLI ──────► cli/service.py ──►     ▼
                                         main_core.py
                                    trigger_dispatcher
                           ┌──────────┼──────────┐
                      radio/      bluetooth/   audio/
                   mpv·welle-cli·rtl_fm    PipeWire → Klinke / BT

mpris2.py ──► org.mpris.MediaPlayer2.pidrive ──► BMW-Display
```

---

## Update auf dem Pi

```bash
cd ~/pidrive && git pull
sudo systemctl restart pidrive_core
pidrivectl version
```

Oder Neuinstallation: `curl … install.sh | sudo bash`

---

## Entwicklung & Logs

```bash
printf "play_dab:DIE NEUE 107.7\n" >> /tmp/pidrive_cmd   # Trigger direkt
tail -f /var/log/pidrive/pidrive.log
pidrivectl test all
cat /tmp/pidrive_test_results.json | python3 -m json.tool
```

| Datei | Inhalt |
|-------|--------|
| `/tmp/pidrive_status.json` | Laufzeit-Status (Quelle, DAB-State, Metadaten) |
| `/tmp/pidrive_dab_welle.err` | welle-cli stderr (Sync, PCM, DLS) |
| `/tmp/pidrive_dab_play_debug.json` | DAB-Debug (Session, Lock, welle-PID) |
| `/tmp/pidrive_cmd` | Trigger-Queue |

Weitere Docs: [KontextPiDrive.md](KontextPiDrive.md) · [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md) · [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

---

## Versionierung

Aktuelle Version: **0.11.104** — definiert in:

- `VERSION` und `pidrive/VERSION`
- `install.sh` → `PIDRIVE_VERSION`
- Badge oben in dieser README

---

## Lizenz

[GPL v3](LICENSE)

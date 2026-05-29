# PiDrive — Developer Guide

**Stand v0.11.67**

---

## A. Architekturüberblick

PiDrive ist ein Python-Daemon mit Web-Frontend. Trigger aus BMW AVRCP, WebUI und CLI werden an Handler-Module weitergegeben, die Audio-Module steuern.

```
BMW iDrive ──[AVRCP BT]──► integration/avrcp_trigger.py
WebUI       ──[HTTP POST]──► web/api/*.py
CLI         ──[IPC-Datei]──► cli/adapters.py
                                    │
                               /tmp/pidrive_cmd   (append-Queue)
                                    │
                              main_core.py
                             check_trigger()
                                    │
                         trigger/trigger_dispatcher.py
                          ┌─────┬──────┬────────┐
                       td_nav td_radio td_hardware td_scanner td_system
                          │
                       modules/*
                          │
                       PipeWire ──► BT A2DP / Klinke / HDMI
```

---

## B. Schnell-Nachschlage-Tabelle

| Ich will... | Datei(en) |
|---|---|
| Audio-Routing (BT/Klinke/HDMI) | `modules/audio.py` |
| Webradio-Playback | `modules/webradio.py` |
| FM-Wiedergabe | `modules/radio/fm.py` |
| FM/PMR-Scanner | `modules/radio/scanner.py` |
| DAB+ starten/stoppen | `modules/radio/dab.py`, `dab_play.py` |
| DAB+ DLS/Metadaten | `modules/radio/dab_dls.py` |
| DAB+ Scan | `modules/radio/dab_scan.py` |
| RTL-SDR / Gain / PPM | `modules/radio/rtlsdr.py` |
| BMW AVRCP-Mapping | `integration/avrcp_trigger.py`, `trigger/td_nav.py` |
| Trigger-Handler Menü/Radio | `trigger/td_nav.py`, `trigger/td_radio.py` |
| Trigger-Handler Audio/BT | `trigger/td_hardware.py` |
| Trigger-Handler Scanner | `trigger/td_scanner.py` |
| Trigger-Handler System | `trigger/td_system.py` |
| Trigger-Dispatcher | `trigger/trigger_dispatcher.py` |
| pidrivectl Subcommands | `cli/cli.py` |
| pidrivectl Service-Layer | `cli/service.py` |
| pidrivectl IPC-Adapter | `cli/adapters.py` |
| Web-API Endpunkte | `web/api/routes_*.py` |
| WebUI HTML | `web/templates/*.html` |
| Flask App | `web/app.py` |
| MPRIS2 D-Bus (BMW-Metadaten) | `mpris2.py` |
| MPRIS2 Debug / IP-Announcement | `mpris2.py: announce_wifi_ip(), push_test_metadata()` |
| mpv IPC / Metadaten | `mpv_meta.py` |
| BT-Verbindung | `modules/bluetooth/bt_connect.py` |
| BT-Agent / Pairing | `modules/bluetooth/bt_agent.py` |
| BT-Geräteklasse (AVRCP vs. Kopfhörer) | `modules/bluetooth/bt_helpers.py: _device_type()` |
| BT-Audio (A2DP Sink, WirePlumber) | `modules/bluetooth/bt_audio.py` |
| Lokale Musik | `modules/local_player.py` |
| USB-Stick-Erkennung | `modules/usb_music.py` |
| System-Test | `test_suite.py` |
| Core-Loop | `main_core.py` |
| IPC-Queue / Status | `ipc.py` |
| Einstellungen | `settings.py` |
| Plattformerkennung + CAPS | `modules/platform.py` |
| Installer | `install.sh` |
| Systemdienste | `systemd/pidrive_*.service` |
| PipeWire Systemd-Units | `systemd/pipewire.service`, `pipewire-pulse.service`, `wireplumber.service` |

---

## C. Kanonische Pfade

| Bereich | Kanonischer Pfad |
|---|---|
| Trigger-Handler | `trigger/td_*.py`, `trigger/trigger_dispatcher.py` |
| CLI | `cli/cli.py`, `cli/service.py`, `cli/adapters.py` |
| Web | `web/app.py`, `web/shared/`, `web/api/` |
| Bluetooth | `modules/bluetooth/*.py` |
| Radio | `modules/radio/*.py` |
| AVRCP (Service-Entry) | `integration/avrcp_trigger.py` |
| MPRIS2 | `mpris2.py` (Root) |
| Core | `main_core.py` (Root, systemd-Entry) |

---

## D. Audio: PipeWire System-Mode (ab v0.11.67)

```
/etc/systemd/system/pipewire.service         User=pulse
/etc/systemd/system/pipewire-pulse.service   User=pulse, Socket=/var/run/pulse/native
/etc/systemd/system/wireplumber.service      User=pulse, managed BT A2DP

/etc/pipewire/pipewire-pulse.conf.d/00-pidrive.conf  → Socket-Pfad
/etc/wireplumber/wireplumber.conf.d/50-bt-pidrive.conf → A2DP-Konfiguration
/etc/dbus-1/system.d/pipewire-pidrive.conf   → pulse-User darf BlueZ
```

**Kein Code-Umbau nötig:** `PULSE_SERVER=unix:/var/run/pulse/native`, `pactl`, `--ao=pulse` bleiben unverändert.

**PipeWire erkennen:**
```python
# modules/audio.py:
_info = subprocess.run(PA_ENV + " pactl info", ...).stdout
is_pipewire = "PipeWire" in _info
```

---

## E. MPRIS2 Debug-Werkzeuge

```bash
# D-Bus Status + IP anzeigen
pidrivectl debug mpris status

# Test-Metadaten ans BMW schicken
pidrivectl debug mpris push --title "Bayern 3" --artist "Test 123"

# D-Bus direkt abfragen
dbus-send --system --print-reply \
  --dest=org.mpris.MediaPlayer2.pidrive \
  /org/mpris/MediaPlayer2 \
  org.freedesktop.DBus.Properties.GetAll \
  string:org.mpris.MediaPlayer2.Player 2>&1 | grep -A2 Title
```

**IP im BMW-Display:** `mpris2.announce_wifi_ip(ssid, duration=8.0)` — wird automatisch nach WiFi-Connect aufgerufen.

---

## F. Neuen Trigger ergänzen

1. `web/shared/constants.py` und `web/shared.py`: Whitelist erweitern
2. `trigger/trigger_dispatcher.py`: welcher `td_*`-Handler?
3. Im passenden `trigger/td_*.py`: `elif cmd == "mein_trigger":` ergänzen
4. Rückgabe: `True` wenn Menü-Rebuild nötig

---

## G. IPC: Trigger schreiben (korrekt)

```python
# Python:
import ipc
ipc.append_trigger("mein_trigger")

# Shell:
printf "mein_trigger\n" >> /tmp/pidrive_cmd
# NICHT: echo > /tmp/pidrive_cmd  ← überschreibt Queue!
```

---

## H. System-Test

```bash
pidrivectl test all           # Kompletter Test ~2-3 Minuten
pidrivectl test system        # Nur Ressourcen
pidrivectl test bt            # Nur Bluetooth/AVRCP
pidrivectl test mpris         # Nur MPRIS2 D-Bus
pidrivectl test webradio      # Nur Webradio
pidrivectl test dabscan       # DAB 11B Scan mit Stationsliste

# Ergebnis:
cat /tmp/pidrive_test_results.json | python3 -m json.tool
```

---

## I. Hinweise zum Patchen

```python
# IMMER zuerst prüfen:
OLD = "zu ersetzendes Muster"
assert OLD in src, f"Muster nicht gefunden in {datei}"
src = src.replace(OLD, NEU, 1)

# Nach jeder Änderung:
import py_compile
py_compile.compile("geänderte_datei.py", doraise=True)
```

```bash
bash -n install.sh   # Bash-Syntax prüfen
```

### Version-Bump

Nur diese Dateien:
- `VERSION` (Root)
- `pidrive/VERSION`
- `install.sh` → `PIDRIVE_VERSION="..."`
- `README.md` → Badge-Zeile

**Niemals** `re.sub()` auf Changelog-Abschnitte.

---

*Weiterführend: `ARCHITECTURE.md`, `MIGRATION_BACKLOG.md`, `TROUBLESHOOTING.md`, `KontextPiDrive.md`*

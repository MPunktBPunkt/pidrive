# PiDrive — Developer Guide

**Stand v0.11.36 · Übergangsarchitektur aktiv**

Dieses Dokument hilft beim schnellen Wiedereinstieg: wo liegt was, was ist kanonisch, was ist noch Shim.

---

## A. Architekturüberblick

PiDrive ist ein Python-Daemon mit Web-Frontend. Die Architektur besteht aus einem zentralen Core-Prozess, der Trigger aus drei Quellen empfängt (BMW AVRCP, WebUI, CLI), an Handler-Module weitergibt und Audio-Module steuert.

```
BMW iDrive ──[AVRCP BT]──▶ avrcp_trigger.py
WebUI       ──[HTTP POST]──▶ web/api/*.py
CLI         ──[IPC-Datei]──▶ cli/adapters.py
                                    │
                               /tmp/pidrive_cmd   (append-Queue)
                                    │
                              main_core.py
                             check_trigger()
                                    │
                         trigger/trigger_dispatcher.py
                          ┌─────┬──────┬────────┐
                       td_nav td_radio td_hardware td_scanner td_system
                          │      │
                       modules/*  (audio, webradio, dab, fm, scanner, bt, ...)
                          │
                       PulseAudio ──▶ BT A2DP / Klinke / HDMI
```

---

## B. Wo ändere ich was?

### Schnell-Nachschlage-Tabelle

| Ich will... | Datei(en) |
|---|---|
| Audio-Routing (BT/Klinke/HDMI) | `modules/audio.py` |
| Webradio-Playback / mpv starten | `modules/webradio.py` |
| FM-Wiedergabe | `modules/radio/fm.py` |
| FM-Scanner / PMR446 / UHF | `modules/radio/scanner.py` |
| DAB+ starten / stoppen | `modules/radio/dab.py`, `dab_play.py` |
| DAB+ DLS / Metadaten | `modules/radio/dab_dls.py` |
| DAB+ Scan-Logik | `modules/radio/dab_scan.py` |
| RTL-SDR / Gain / PPM | `modules/radio/rtlsdr.py` |
| Spektrum / Signalstärke | `modules/radio/spectrum.py` |
| BMW AVRCP-Mapping | `avrcp_trigger.py`, `trigger/td_nav.py` |
| Trigger-Handler Menü/Radio | `trigger/td_nav.py`, `trigger/td_radio.py` |
| Trigger-Handler Audio/BT | `trigger/td_hardware.py` |
| Trigger-Handler Scanner | `trigger/td_scanner.py` |
| Trigger-Handler System | `trigger/td_system.py` |
| Trigger-Dispatcher (welcher Handler?) | `trigger/trigger_dispatcher.py` |
| pidrivectl Subcommands | `cli/cli.py` |
| pidrivectl Service-Layer (IPC) | `cli/service.py` |
| pidrivectl CLI Adapter (Trigger schreiben) | `cli/adapters.py` |
| pidrivectl CLI Formatierung | `cli/format.py` |
| Web-API Endpunkte | `web/api/routes_*.py` |
| WebUI HTML-Templates | `web/templates/*.html` |
| WebUI Flask App | `web/app.py` |
| WebUI Shared Helpers | `web/shared/`, `web/shared.py` |
| Menü-Baum, Knoten, Navigation | `menu/menu_model.py`, `menu_builder.py` |
| MPRIS2 D-Bus (BMW-Metadaten) | `mpris2.py` (Root, kanonisch) |
| mpv IPC / Metadaten | `mpv_meta.py` |
| BT-Verbindungslogik | `modules/bluetooth/bt_connect.py` |
| BT-Agent / Pairing | `modules/bluetooth/bt_agent.py` |
| BT-Watcher / Auto-Reconnect | `modules/bluetooth/bt_watcher.py` |
| Lokale Musikwiedergabe | `modules/local_player.py` |
| Core-Loop / Hauptprozess | `main_core.py` |
| IPC-Queue / Statusdateien | `ipc.py` |
| Einstellungen / Settings | `settings.py` |
| Logging | `log.py` |
| CAPS / Plattformerkennung | `modules/platform.py` |
| Installer | `install.sh` |
| Systemdienste | `systemd/pidrive_*.service` |

---

## C. Kanonische Pfade vs. Altpfade

Dies ist die **wichtigste Orientierung im aktuellen Übergangszustand**.

### Kanonische Zielpfade (hier implementieren / anfassen)

| Bereich | Kanonischer Pfad |
|---|---|
| Trigger-Handler | `trigger/td_*.py`, `trigger/trigger_dispatcher.py` |
| CLI | `cli/cli.py`, `cli/service.py`, `cli/adapters.py`, `cli/format.py` |
| Web | `web/app.py`, `web/shared/`, `web/api/`, `web/templates/` |
| Menü | `menu/menu_model.py`, `menu/menu_builder.py`, `menu/menu_state.py` |
| Bluetooth | `modules/bluetooth/*.py` |
| Radio | `modules/radio/*.py` |
| Core-Einstieg | `main_core.py` (Root, bleibt vorerst) |
| AVRCP | `avrcp_trigger.py` (Root, läuft als Service) |
| MPRIS2 | `mpris2.py` (Root, läuft als Core-Modul) |

### Noch aktive Root-Entrypoints (nicht anfassen ohne Absprache)

Diese Dateien laufen als systemd-Service-Einstieg und sollten nicht verschoben werden:

| Datei | Service | Warum noch Root |
|---|---|---|
| `main_core.py` | `pidrive_core.service` | zentraler Hauptprozess, Hochrisiko-Move |
| `webui.py` | `pidrive_web.service` | Web-Entry-Shim auf `web/app.py` |
| `avrcp_trigger.py` | `pidrive_avrcp.service` | AVRCP-Daemon |

### Root-Shims (existieren noch, aber nicht der echte Code)

Diese Dateien nur für Kompatibilität vorhanden — **hier nicht neuen Code schreiben**:

| Root-Shim | Echter Code |
|---|---|
| `modules/dab.py` | `modules/radio/dab.py` |
| `modules/fm.py` | `modules/radio/fm.py` |
| `modules/scanner.py` | `modules/radio/scanner.py` |
| `modules/rtlsdr.py` | `modules/radio/rtlsdr.py` |
| `modules/bluetooth.py` | `modules/bluetooth/bluetooth.py` |
| `modules/bt_*.py` (Root) | `modules/bluetooth/bt_*.py` |
| `integration/avrcp_trigger.py` | Shim → `avrcp_trigger.py` |
| `integration/mpv_meta.py` | Shim → `mpv_meta.py` |

---

## D. Typische Arbeitsaufgaben

### Neuen CLI-Befehl ergänzen

1. `cli/cli.py`: Subparser in `parse_args()` ergänzen
2. Handling in der entsprechenden `if args.cmd == "..."` Sektion
3. Trigger via `svc.send_trigger("mein_trigger")` oder direkt `svc.send()`
4. Installer-Smoke-Test läuft automatisch beim nächsten Install
5. README `pidrivectl`-Abschnitt aktualisieren

### Neuen Trigger ergänzen

1. Trigger-String in `web/shared/constants.py` und `web/shared.py` registrieren (Whitelist)
2. In `trigger/trigger_dispatcher.py`: welcher `td_*`-Handler zuständig?
3. Im passenden `trigger/td_*.py`: `elif cmd == "mein_trigger":` ergänzen
4. Rückgabewert: `True` wenn Menü-Rebuild nötig, sonst `False`

### WebUI-Button an Trigger anbinden

1. HTML-Template `web/templates/*.html`: Button mit `data-trigger="mein_trigger"`
2. `web/static/js/*.js`: Click-Handler → POST `/api/cmd` mit `{ cmd: "mein_trigger" }`
3. In `web/api/routes_*.py` ggf. neuen API-Endpunkt anlegen (falls komplexer)

### Neue Audioquelle ergänzen

1. Neues Modul unter `modules/` anlegen
2. In `trigger/td_radio.py` neuen `play_*`-Trigger registrieren
3. `modules/source_state.py`: neue Source-ID eintragen
4. MPRIS2-Metadaten in `mpris2.py` für neue Quelle ergänzen
5. CLI: `play <neue_quelle>` in `cli/cli.py`

### Installer anpassen

Der Installer `install.sh` ist eine lange Bash-Datei. Wichtige Abschnitte:
- **Plattformerkennung:** `IS_PI`, `IS_ARM`, `IS_CONTAINER`
- **Import-Smoke-Test:** enthält die 28-Modul-Liste — bei neuen Modulen ergänzen
- **Runtime-Gate:** 15s Stabilitätsfenster nach Core-Start — **nicht entfernen**

---

## E. Wichtige Runtime-Dateien

| Datei | Inhalt | Schreiber |
|---|---|---|
| `/tmp/pidrive_cmd` | Trigger-Queue (append-only) | alle Producer |
| `/tmp/pidrive_status.json` | Audio-Status, BT, WiFi, Source | `main_core.py` |
| `/tmp/pidrive_source_state.json` | Aktive Quelle, boot_phase | `modules/source_state.py` |
| `/tmp/pidrive_avrcp_events.json` | Ringpuffer letzte 30 AVRCP-Events | `avrcp_trigger.py` |
| `/tmp/pidrive_avrcp_status.json` | Letztes AVRCP-Event | `avrcp_trigger.py` |
| `/tmp/pidrive_dab_scan_debug.json` | DAB-Scan-Fortschritt | `modules/radio/dab_scan.py` |
| `/tmp/pidrive_progress.json` | Task-Fortschritt (Scan etc.) | Core / Module |
| `/tmp/pidrive_mpv.sock` | mpv IPC-Socket | `mpv` Prozess |
| `/var/log/pidrive/pidrive.log` | Rotating Log (512KB) | `log.py` |

### IPC: Trigger schreiben (korrekt)

```python
# Innerhalb von Python-Code:
import ipc
ipc.append_trigger("mein_trigger")

# Shell (Debug):
printf "mein_trigger\n" >> /tmp/pidrive_cmd
# NICHT: echo -n "..." > /tmp/pidrive_cmd  ← überschreibt Queue!
```

---

## F. Hinweise zum Patchen

### Sichere str.replace()-Regel

```python
# IMMER prüfen, ob das Muster existiert:
OLD = "zu ersetzendes Muster"
assert OLD in src, f"Muster nicht gefunden in {datei}"
src = src.replace(OLD, NEU, 1)
```

Silent failures sind das Hauptrisiko — `str.replace()` ohne `assert` macht nichts wenn das Muster nicht stimmt.

### Nach jeder Änderung

```python
import py_compile
py_compile.compile("geänderte_datei.py", doraise=True)
```

```bash
bash -n install.sh   # Bash-Syntax prüfen
```

### Version bump

Nur diese Dateien bumpen:
- `VERSION` (Root)
- `pidrive/VERSION`
- `install.sh` → `PIDRIVE_VERSION="..."`
- `README.md` → Badge-Zeile

**Niemals** `re.sub()` auf Changelog-Abschnitte anwenden — das korrumpiert historische Headers.

### Zeilenbasiertes Patching bei Einrückungsproblemen

Bei eingerückten Code-Blöcken ist `str.replace()` mit exakten Whitespace-Angaben fehleranfällig. Alternative:

```python
lines = src.split('\n')
lines.insert(42, '    neue_zeile()')   # nach Zeile 42 einfügen
src = '\n'.join(lines)
```

---

## G. CAPS-System (Plattformerkennung)

```python
from modules.platform import CAPS

CAPS["is_pi"]        # True auf Raspberry Pi
CAPS["rtlsdr"]       # RTL-SDR verfügbar
CAPS["dab"]          # welle-cli vorhanden
CAPS["bluetooth"]    # BT-Adapter vorhanden
CAPS["pulseaudio"]   # PulseAudio-Socket vorhanden
CAPS["display"]      # immer False (TFT entfernt v0.10.83)
CAPS["gpio"]         # immer False (GPIO entfernt v0.10.83)
```

Vor Hardware-Starts immer `CAPS`-Check — verhindert 6s-Timeouts auf Systemen ohne entsprechende Hardware.

---

*Weiterführend: `ARCHITECTURE.md` (Systemarchitektur), `MIGRATION_BACKLOG.md` (Shim-Status), `TROUBLESHOOTING.md` (Fehlersuche)*

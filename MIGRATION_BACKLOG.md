# PiDrive — Migration Backlog

**Stand v0.11.58**

---

## Status-Übersicht

| Bereich | Status | Version |
|---|---|---|
| `trigger/` Migration | ✅ abgeschlossen | v0.11.27 |
| IPC-Producer unified | ✅ abgeschlossen | v0.11.27 |
| `integration/` kanonisiert | ✅ abgeschlossen | v0.11.39 |
| Web-Entry auf `web/app.py` | ✅ abgeschlossen | v0.11.39 |
| Root-Shim-Abbau Module/BT/Radio | 🟡 niedrige Priorität | — |
| `main_core.py` logisch zerlegen | 📅 nach Feldtest | — |
| **PulseAudio → PipeWire** | ✅ abgeschlossen | v0.11.58 |
| AVRCP Phase 2 State Machine | 📅 nach Feldtest | — |

---

## Aktive Systemd-Entrypoints

| Datei | Service | Zustand |
|---|---|---|
| `main_core.py` | `pidrive_core.service` | Root-Entry, bleibt vorerst |
| `web/app.py` | `pidrive_web.service` | direkt, kein Shim mehr |
| `integration/avrcp_trigger.py` | `pidrive_avrcp.service` | direkt, kein Shim mehr |
| `systemd/pipewire.service` | `pipewire.service` | System-Mode, User=pulse |
| `systemd/pipewire-pulse.service` | `pipewire-pulse.service` | PA-Compat, Socket=/var/run/pulse/native |
| `systemd/wireplumber.service` | `wireplumber.service` | BT A2DP automatisch |

---

## Audio-Migration: PulseAudio → PipeWire (v0.11.58)

**Abgeschlossen.** Kein Code-Umbau nötig — Socket-Pfad identisch.

Was geändert wurde:
- `install.sh`: System-PA-Block → PipeWire-Block
- `modules/audio.py`: `_pa_running()` prüft jetzt Socket + PipeWire-Service
- `modules/bluetooth/bt_audio.py`: `_ensure_bt_pa_modules()` erkennt PipeWire, überspringt `load-module`
- `modules/platform.py`: CAPS `pipewire` ergänzt
- `diagnose.py`: Audio-Section Header + Checks aktualisiert
- `test_suite.py`: PipeWire-Check statt PA-Konflikt-Check
- Neue Systemd-Units: `pipewire.service`, `pipewire-pulse.service`, `wireplumber.service`
- Neue Konfig: `/etc/pipewire/pipewire-pulse.conf.d/00-pidrive.conf`
- Neue Konfig: `/etc/wireplumber/wireplumber.conf.d/50-bt-pidrive.conf`
- D-Bus Policy: `pulse`-User darf BlueZ ansprechen (für WirePlumber)

---

## Root-Shims (noch vorhanden, niedrige Priorität)

| Root-Shim | Echter Code | Wann abbaubar? |
|---|---|---|
| `modules/dab.py` | `modules/radio/dab.py` | nach Repo-Check |
| `modules/fm.py` | `modules/radio/fm.py` | nach Repo-Check |
| `modules/scanner.py` | `modules/radio/scanner.py` | nach Repo-Check |
| `modules/bluetooth.py` | `modules/bluetooth/bluetooth.py` | nach Repo-Check |
| `modules/bt_*.py` (Root) | `modules/bluetooth/bt_*.py` | nach Repo-Check |
| `avrcp_trigger.py` (Root) | `integration/avrcp_trigger.py` | jetzt Shim (1 Zeile) |

---

## Nächste Releases

| Version | Fokus | Status |
|---|---|---|
| v0.11.58 | Markdown-Cleanup | ✅ |
| v0.11.58+ | BMW AVRCP Feldtest-Fixes | 🔄 nach Feldtest |
| v0.11.6x | AVRCP Phase 2 State Machine | 📅 |
| v0.12.x | main_core.py logisch zerlegen | 📅 Hochrisiko |

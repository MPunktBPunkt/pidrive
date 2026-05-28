# PiDrive — Migrationsstatus Verzeichnisstruktur

## Aktueller Stand: v0.11.58 (Übergangsphase)

Die Zielstruktur ist dokumentiert in `ARCHITECTURE.md`.
Dieser Plan zeigt den Migrationsstatus jeder Datei.

## Status-Legende
- ✅ Fertig — Datei am Zielpfad
- 🔄 Shim — Root-Shim existiert, echte Datei am Zielpfad
- ⏳ Ausstehend — noch am alten Pfad, muss verschoben werden
- 🗑 Legacy — kann entfernt werden

## Bluetooth-Subsystem
| Alt | Neu | Status |
|---|---|---|
| `modules/bluetooth.py` | `modules/bluetooth/bluetooth.py` | 🔄 Shim |
| `modules/bt_agent.py` | `modules/bluetooth/bt_agent.py` | 🔄 Shim |
| `modules/bt_devices.py` | `modules/bluetooth/bt_devices.py` | 🔄 Shim |
| `modules/bt_*.py` (alle) | `modules/bluetooth/bt_*.py` | 🔄 Shim |

## Radio-Subsystem
| Alt | Neu | Status |
|---|---|---|
| `modules/dab.py` | `modules/radio/dab.py` | 🔄 Shim |
| `modules/dab_play.py` | `modules/radio/dab_play.py` | 🔄 Shim |
| `modules/fm.py` | `modules/radio/fm.py` | 🔄 Shim |
| `modules/scanner.py` | `modules/radio/scanner.py` | 🔄 Shim |
| `modules/rtlsdr.py` | `modules/radio/rtlsdr.py` | 🔄 Shim |
| `modules/spectrum.py` | `modules/radio/spectrum.py` | 🔄 Shim |

## Web-Subsystem
| Alt | Neu | Status |
|---|---|---|
| `webui.py` | `web/app.py` | 🔄 Shim |
| `webui_shared.py` | `web/shared.py` | 🔄 Shim |

## CLI
| Alt | Neu | Status |
|---|---|---|
| `cli.py` | `cli/cli.py` | 🔄 Shim |
| `cli_service.py` | `cli/service.py` | 🔄 Shim |
| `cli_adapters.py` | `cli/adapters.py` | 🔄 Shim |
| `cli_format.py` | `cli/format.py` | 🔄 Shim |

## Noch ausstehend (Phase 3)
| Datei | Ziel | Risiko |
|---|---|---|
| `main_core.py` | `core/main_core.py` | Hoch |
| `ipc.py` | `core/ipc.py` | Hoch |
| `settings.py` | `core/settings.py` | Hoch |
| `log.py` | `core/log.py` | Hoch |
| `menu_*.py` | `menu/*.py` | 🔄 Shim |
| `trigger_dispatcher.py` | `trigger/trigger_dispatcher.py` | 🔄 Shim |
| `td_*.py` | `trigger/td_*.py` | Mittel |
| `avrcp_trigger.py` | `integration/avrcp_trigger.py` | Mittel |
| `mpris2.py` | `integration/mpris2.py` | Mittel |

## Shim-Abbauplan
Shims können entfernt werden wenn:
1. Alle internen Imports auf neue Pfade umgestellt (pyflakes check)
2. systemd ExecStart-Pfade aktualisiert (für Core/Web/AVRCP)
3. install.sh Smoke-Tests auf neue Pfade umgestellt

**Frühestens ab v0.11.x**

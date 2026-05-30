# PiDrive — Migration Backlog

**Stand v0.11.68**

---

## Gesamtstatus

| Bereich | Status | Version |
|---|---|---|
| `trigger/` Migration | ✅ abgeschlossen | v0.11.27 |
| IPC-Producer unified | ✅ abgeschlossen | v0.11.27 |
| `integration/` kanonisiert | ✅ abgeschlossen | v0.11.39 |
| Web-Entry auf `web/app.py` | ✅ abgeschlossen | v0.11.39 |
| PulseAudio → PipeWire | ✅ abgeschlossen | v0.11.56 |
| **Root-Shim-Abbau (24 Dateien)** | ✅ **abgeschlossen** | **v0.11.68** |
| MPRIS2 SIGABRT-Fix | ✅ abgeschlossen | v0.11.68 |
| AVRCP Phase 2 State Machine | 📅 nach Feldtest | — |
| `main_core.py` logisch zerlegen | 📅 später | — |

---

## v0.11.68: Root-Shim-Abbau — Was wurde gemacht

### 24 Dateien gelöscht

**Tote Root-Shims (7 Zeilen, nur Delegation):**
- `modules/bt_agent.py`, `bt_audio.py`, `bt_backup.py`, `bt_connect.py`
- `modules/bt_devices.py`, `bt_helpers.py`, `bt_watcher.py`, `bluetooth.py`
- `modules/dab.py`, `dab_dls.py`, `dab_helpers.py`, `dab_play.py`, `dab_scan.py`
- `modules/fm.py`, `rtlsdr.py`, `scanner.py`, `spectrum.py`

**Toter Code (keine Importer):**
- `modules/bluetooth_impl.py` — 3 Zeilen, nie genutzt
- `modules/radio_impl.py` — 4 Zeilen, nie genutzt
- `modules/core_callbacks.py` — 96 Zeilen, Extraktion nie abgeschlossen
- `modules/system.py` — 51 Zeilen, nie genutzt
- `modules/update.py` — 168 Zeilen, nie genutzt

**Veraltete Integration-Kopien:**
- `integration/mpris2.py` — 388 Zeilen, alte v0.7.10 Kopie, nie importiert
- `integration/mpv_meta.py` — 4 Zeilen Shim, nie importiert

### 8 Importpfade auf kanonische Pfade umgestellt

| Datei | Alter Import | Neuer Import |
|---|---|---|
| `main_core.py` | `from modules import rtlsdr` | `from modules.radio import rtlsdr` |
| `trigger/td_hardware.py` | `from modules import rtlsdr` | `from modules.radio import rtlsdr` |
| `trigger/td_hardware.py` | `from modules import bt_backup` | `from modules.bluetooth import bt_backup` |
| `web/shared.py` | `from modules import dab` | `from modules.radio import dab` |
| `web/shared.py` | `from modules import spectrum` | `from modules.radio import spectrum` |
| `web/app.py` | `from modules import spectrum` | `from modules.radio import spectrum` |
| `menu/station_store.py` | `from modules.scanner import ...` | `from modules.radio.scanner import ...` |
| `menu/menu_builder.py` | `from modules.scanner import ...` | `from modules.radio.scanner import ...` |

---

## Aktuelle Dateistruktur (71 Python-Dateien)

```
pidrive/
├── main_core.py           ← systemd-Entry (bleibt vorerst)
├── webui.py               ← Entry-Shim → web/app.py
├── avrcp_trigger.py       ← Entry-Shim → integration/avrcp_trigger.py
├── mpris2.py              ← MPRIS2-Implementierung (Root, Core importiert direkt)
├── mpv_meta.py            ← mpv IPC/Metadaten
├── diagnose.py, ipc.py, log.py, settings.py, status.py, test_suite.py
│
├── cli/                   ✅ sauber
├── menu/                  ✅ sauber
├── modules/
│   ├── audio.py, favorites.py, local_player.py, platform.py
│   ├── source_state.py, usb_music.py, webradio.py, wifi.py
│   ├── bluetooth/         ✅ sauber (bt_agent, bt_audio, bt_backup,
│   │                                bt_connect, bt_devices, bt_helpers, bt_watcher)
│   └── radio/             ✅ sauber (dab, dab_dls, dab_helpers, dab_play,
│                                     dab_scan, fm, rtlsdr, scanner, spectrum)
├── trigger/               ✅ sauber
├── web/                   ✅ sauber
└── integration/
    └── avrcp_trigger.py   ← echte AVRCP-Implementierung
```

---

## Verbleibende Aufgaben

| Aufgabe | Priorität | Wann |
|---|---|---|
| AVRCP Phase 2 State Machine | P1 | nach BMW Feldtest |
| BMW AVRCP Feldtest (Tasten + Display) | P1 | nächste Fahrt |
| `main_core.py` logisch zerlegen (~728 Zeilen) | P3 | v0.12.x |
| systemd Core-Entry modernisieren | P3 | nach Core-Zerlegung |

# Frisch-Install: Soft-Smoke vs Hardware

**Stand:** 2026-09-24 · Ziel: `curl …/install.sh | sudo bash` auf Raspberry Pi OS Bookworm
bzw. Debian 12 Soft-Test (Proxmox LXC amd64).

## Was „fertig“ heißt

| Ebene | Erwartung nach Install (+ Reboot) |
|-------|-----------------------------------|
| Soft | `pidrive_core` + `pidrive_web` aktiv, `pidrivectl version/status`, WebUI `:8080` |
| HW-Radio | RTL-Stick → FM/DAB/Scanner (nach DVB-Blacklist/Reboot) |
| HW-BT | Pairing/AVRCP/A2DP zum Auto |
| HW-ESP | `pump_bridge.py` aus **esp32.pidrive** unter `$HOME/pump_bridge.py` + UART |

## Soft vs Hardware

| Feature | Soft (kein Stick/BT/ESP) | Braucht Hardware |
|---------|--------------------------|------------------|
| Core + IPC + CLI | ja | — |
| WebUI :8080 | ja | — |
| PipeWire | oft ohne Sinks (Warnung ok) | Klinke / BT |
| BT-Agent / AVRCP | Dienst kann laufen | Controller / Auto |
| DAB+ / FM / Scanner | Binaries ggf. da | RTL-SDR |
| USB-Defer / Hotplug-Release | Units ok | ESP/RTL/QinHeng |
| `pidrive_pump` (Presence) | pollt, ESP offline | ESP SoftAP |
| `pidrive_pump_bridge` | `ConditionPathExists` → inaktiv | `/dev/ttyACM0` + Script + ffmpeg |
| Spotify Connect | librespot/OAuth manuell | Netz + Account |

## Bekannte Installer-Grenzen

- `pump_bridge.py` liegt **nicht** im PiDrive-Repo (Deploy aus esp32.pidrive).
- Raspbian existiert **nicht** als amd64-LXC auf Proxmox — Soft-Test: Debian 12 Bookworm.
- Feldregel USB: kein Hub beim Kaltstart — siehe [`BOOT-USB-DEFER.md`](BOOT-USB-DEFER.md).

## Proxmox Soft-Smoke

Auf dem PVE-Host:

```bash
sudo bash /path/to/pidrive/scripts/proxmox-install-smoke.sh
```

Template: `debian-12-standard_*_amd64.tar.zst` (Bookworm).

# Artefakte Heimabend 2026-10-01 (Auto ESP `.89`, FW 0.4.31-dev)

**Ohr:** kurz Live-Ton + ID3-Cover Rock Antenne Bayern → nach ~6 s weg; erneute Wahl = dieselben ~6 s (HU-Cache).

## Kernzahlen (Status nach Loop)

| Key | Wert |
|-----|------|
| `streamBytes` | ≈ 167 936 (Live-Consume) |
| `underruns` | hoch (nach Stopp der Host-Reads) |
| `msc.trace` | **leer** in allen Snapshots |
| Serial | `PD0004`→`PD0005` (OTG) |
| Bridge | zeitweise falsch auf `.88` (Cron `ensure_pump_bridge.sh`) — behoben → `.89` |

## Dateien

- `esp89-*-*.json` — Status-Snapshots
- `esp89-events-*.json` / `*-play-filter.txt` — Event-Ring
- `pump_bridge_manual.log` / `bridge-*-filter.txt` — Bridge
- `feld_esp_poll.txt` — 2 s-Poll (pump=false-Phase)
- `pidrive_msc_diag-*.jsonl` — Diag

## Debian-Sim

Synthetischer Trace: `esp32.pidrive/tools/traces/feld_heimabend_6s_cache.replay.json`  
(lab-safe 16 KiB; Feldgröße nur in `meta` / `field_live_bytes_approx`).

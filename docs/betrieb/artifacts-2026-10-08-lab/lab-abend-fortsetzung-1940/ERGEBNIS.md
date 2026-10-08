# Lab-Fortsetzung · 2026-10-08 ~19:40

**ESP:** `.88` · FW `0.4.46-dev` (Freeze) · Artefakt: dieses Verzeichnis  
**Umsetzung:** `tools/lab_q10_read_sniff.py`, `nbt_hu_sim` → `live_s_at_bps` / `--replug-bps`, Runner `run-lab-fortsetzung.py`

| Block | Ergebnis | Detail |
|-------|----------|--------|
| L4f authorized/VBUS | **RO** (PVE/CT) | `2-3.2/authorized` nicht schreibbar; `uhubctl` fehlt |
| Q10 READ10 | **4 KiB** | 7/7 REPLUG-Traces `n=4096` ×128; ESP `msc.xfer` n4k dominant, n8kPlus=0 |
| Kopf-Pause | Sim **~19,3 ms** | `q10-sniff-fixed.json`; Feld-USB-Sniffer weiter offen |
| Klasse-A Remount×5 | **PASS** 0 Drops | PD0316→PD0321, Uptime 3h24–3h25; vorher Remount nur nach `lab/stop` |
| Bitrate-Leiter (vorher) | **PASS** | 48k≈8,4 s · 32k≈12,6 s · 24k≈16,6 s |
| REPLUG 48k Head | **PASS** | live_bytes 50460, live_s_at_bps **8,41**, identity_ok |
| P-Schlüssel Größe | **nicht Lab** | Slot-Größe nicht per menu_set; Feld P1 bleibt |

**Operator-Bezug:** physisches OTG ab/an ohne weiße LED (~18:50) = Klasse A; Telemetrie Uptime kontinuierlich, kein `boot`.

**Freeze:** kein OTA / Stall.

## Kurzfazit

Lab kann Q10 (4 KiB) und Klasse-A-Remount ohne ESP-Reset reproduzieren; Hörfenster über Bridge-Bitrate verlängern ohne FW. VBUS-Zyklen brauchen Host/`uhubctl`. P-Größe und echter HU-Kopf-Sniffer bleiben Feld.

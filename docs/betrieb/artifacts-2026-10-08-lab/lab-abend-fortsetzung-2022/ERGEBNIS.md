# Lab-Fortsetzung · 2026-10-08 ~20:22

**ESP:** `.88` · FW `0.4.46-dev` (Freeze)  
**Neu:** `tools/lab_fat_list.py` (FAT12 STATIONS-Listing via `/dev/sda`)

| Block | Ergebnis | Detail |
|-------|----------|--------|
| Q11 UART | **kein Gerät** | Lab-CT: keine `/dev/ttyUSB*` / `serial/by-id` → `rst:` bleibt Feld |
| K3 auf Disk (1. Versuch) | FAIL | Bridge `BrokenPipe` vor `menu_set` (zu frühes `lab/stop`) |
| **K3 FAT Override** | **PASS** (Retry) | Nach `MSC_MAP_FROZEN … LAB 1008`: FAT `Radio BOB LAB 1008.mp3` |
| K3 Restore FAT | **PASS** | wieder `Radio BOB!.mp3` |
| **24k ×3** | **3/3 PASS** | live_s_at_bps **16,73–16,81 s** @3000 B/s |

## Feld-Relevanz

- Name-Override ist **auf dem Medium** sichtbar (STATIONS/), nicht nur in `/api/status` — K3/P-Test damit Lab-geschlossen.  
- Reihenfolge: Override-Datei → Bridge+`--msc-lock` → warten auf Freeze mit neuem Namen → Remount/OTG.  
- UART-Brownout-Log nur am Auto/Host mit USB-UART.

Stall/OTA: Freeze.

# Lab-Fortsetzung · 2026-10-08 ~20:05

**ESP:** `.88` · FW `0.4.46-dev` (Freeze) · Runner: `run-lab-k3-reject-fenster.py`  
**Neu:** `tools/lab_fenster_bitrate.py`

| Block | Ergebnis | Detail |
|-------|----------|--------|
| **K3 Name-Override** | **PASS** Setzen | `fav2` → `Radio BOB LAB 1008` nach Bridge+`--msc-lock`+Remount |
| K3 Restore | **PASS** (Retry) | Leere Override-Datei allein reicht nicht bei frozen map; Bridge-Neustart + Remount → `Radio BOB!` (`k3-status-restored-retry.json`) |
| **Reject Mid vs Head** | **PASS** | Mid-SG fav2 +128 KiB → `playReject` +32, `not_from_head`/`plug_window`; Head-REPLUG **PASS** live_s **8,32 s** |
| **32k ×3** | **3/3 PASS** | live_s_at_bps **12,54–12,62 s** @4000 B/s; identity_ok |

**Uptime** durchgängig ~3h43–3h47, keine Soft-Resets.

## Feld-Hinweise

- K3: Override **bei OTG ab** (msc-lock); Rücksetzen braucht neue USB-Session / Bridge-Refresh, nicht nur Datei leeren bei frozen map.  
- Mid-File tippen bleibt Reject — Head-from-0 nach Prefill liefert das Ringfenster.  
- 32k Bridge verlängert Lab-Hörfenster stabil (~12,5 s) ohne FW.

Stall/OTA: Freeze.

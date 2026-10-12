# Lab D0 — E7-B L1 Regression (512 KiB) · 2026-10-12

**FW:** `0.4.49-dev` · Lab `.88` · Mode B · `fav2` 512 KiB  
**Tool:** `tools/lab_e7_delay_ladder.py` / `nbt_hu_sim.py --golden REPLUG`

## Ergebnis

| Check | Wert |
|-------|------|
| PASS | **ja** |
| paced_like_L1 | **ja** (p50≈734 ms / Soll≈683 ms @48k) |
| undDelta | **0** |
| live_s @6 kB/s | **≈86,9 s** (Soll >60 s) |
| bytes | 524288 · 128×4 KiB |

Config während Lauf: `stallEnable` + scope 1 + maxMs 1000 + chunk 4096.  
Danach Freeze: `stallEnable=false`.

Artifacts: `stufe-b-chunk4096/`, `summary.json`, `run.log`.

**D1–D3** (1/2/8 MiB Fixed Huge) offen — nicht Teil dieses Laufs.

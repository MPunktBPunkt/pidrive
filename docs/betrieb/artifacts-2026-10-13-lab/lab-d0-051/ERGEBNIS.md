# Lab D0 — E7-B L1 Regression · 0.4.51-dev · 2026-10-13

**FW:** `0.4.51-dev` · Lab `.88` · Mode B · `fav2` 512 KiB  
**Tool:** `tools/lab_e7_delay_ladder.py --mode B`

## Ergebnis

| Check | Wert |
|-------|------|
| PASS | **ja** |
| paced_like_L1 | **ja** (p50≈736 ms / Soll≈683 ms @48k) |
| undDelta | **0** |
| live_s @6 kB/s | **≈86,9 s** (Soll >60 s) |
| bytes | 524288 · 128×4 KiB |

Vergleich 0.4.49 (`lab-d0-regression`): p50≈734 ms — Regression **stabil**.

Danach: `stallEnable=false`.

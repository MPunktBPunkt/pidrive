# Lab D3-Partial — 1 MiB paced auf fav0 (8 MiB-Slot) · 0.4.51 · 2026-10-13

**Kein D1-Geometry-Build** (1 MiB-Slot fehlt). Stattdessen: S7-armed Busy-Pacing auf dem **bestehenden L3-fav0 (8 MiB)**, gelesen bis **1 MiB** (D1-äquivalente Dauerprobe).

## Ergebnis

| Check | Wert |
|-------|------|
| PASS | **ja** |
| after head tip `stall.armed` | **true** (`playing=fav0`) |
| paced_like_L1 | **ja** (p50≈736 ms / Soll≈683 ms) |
| bytes | 1 048 576 · 240×4 KiB body (+64 KiB Head) |
| Klassen | ID3:1 · LIVE:255 |
| underruns | **0** |
| waitMsMax | 766 ms |

Volles D3 (8 MiB bis EOF, ~22 min @6 kB/s) und D1/D2-Geometrie-Builds bleiben offen — warten auf F0-Parameter.

Danach: `stallEnable=false`.

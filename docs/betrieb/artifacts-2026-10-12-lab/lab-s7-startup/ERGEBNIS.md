# Lab S7 — Startup-Poll · 2026-10-12

**FW:** `0.4.49-dev` · Lab `.88`  
**Tool:** `tools/lab_s7_startup_poll.py --arm-stall --seconds 110`

## Marks (s)

| Mark | t |
|------|---|
| serial_seen / first_read_fw | 11,465 |
| play_guess_fw | 28,393 |
| stall_armed | 28,393 |
| playingUid | 28,393 |
| retries_gt0 | 28,393 |

**Urteil:** `stall_armed` fällt **zeitgleich** mit FW-`play.guess` / `playingUid` — Scope-1-Gate an Head-Play gekoppelt.

`skipNotArmed` vor Armed blieb in diesem Remount-Poll bei 0 (kein Live-Stream vor Guess). Nachweis Live-vor-Guess: [`../lab-s7-stream-before-guess/ERGEBNIS.md`](../lab-s7-stream-before-guess/ERGEBNIS.md).

Artifacts: `poll.jsonl`, `summary.json`, `config-arm.json`.

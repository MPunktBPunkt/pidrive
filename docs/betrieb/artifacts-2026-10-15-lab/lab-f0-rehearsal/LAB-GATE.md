# Lab-Gate F0 Identity · 2026-10-16

**Frage:** Ist Isolation-Tooling (serial / label / volume-id) overnight-fest auf `.88`?  
**Nicht:** NBT Cache/P (braucht Auto).

| Run | Ergebnis |
|-----|----------|
| `run-20261016-000641` overnight 8× | serial 8/8, volume-id 8/8, label 3/8 |
| Root-Cause label | Append-`X` bei 11-Zeichen-Label → no-op |
| Fix | `next_volume_label` + `ensure_stream_quiet` (remount_skip) |
| `run-20261016-062936` verify 6× | **18/18 PASS** |

Feld-Scripts spiegeln den Fix: `feld-f0-prep/f0-identity.sh`, OTA-Retry in `ota-f0-051.sh`.

# Lab S7 — Stream-before-Guess Probe · 2026-10-12

**FW:** `0.4.49-dev` · Lab `.88` · SG `/dev/sg0`  
**Ergebnis:** **S7_PROBE PASS**

## Setup

- `stallEnable=true`, `stallScope=1`, `stallMaxMs=1000`, `chunk=4096`
- Pump-TCP `audio_start fav2` **ohne** vorheriges MSC-Head-`play.guess` (Feld-s6-Reihenfolge)
- Kurzer Producer, dann gestoppt (dünner Ring für Phase C)
- `playingUid` vor Tip geleert (`lab/stop`), sonst `already_playing` ohne Re-Arm
- Nach Test: `stallEnable=false`

## Phasen

| Phase | Soll | Ist |
|-------|------|-----|
| A · Live Mid-File, `!armed` | schnell, `skipNotArmed`↑, Retries flat | **PASS** p50≈5,5 ms · Δskip=8 · Δretries=0 |
| Tip Head `fav2` | `stallArmed=true` | **PASS** armed + `playing=fav2` |
| C · Live Mid-File, armed, dünner Ring | BUSY-Pacing ~`maxMs` | **PASS** p50≈1021 ms · Δretries≈3006 |

Artifacts: `probe-summary.json`, `probe-final.log`.

## Erkenntnisse

1. **S7-B Gate wirkt:** Live-Overlay vor Head-Play → kein BUSY (`skipNotArmed`).
2. **`lab/play` armiert nicht** — nur echtes MSC `evaluatePlay` / Head-Tip.
3. Soft-`remount` während `stream.active` wird **übersprungen** (`msc.remount_skip`) — vorher `audio_stop` / Restart.
4. `startStream` cleared `stallArmed` (frühzeitiges Overlay); Re-Arm erst bei frischem Head-Guess (nicht `already_playing`).

## Freeze

`stallEnable=false` auf `.88`. Feld-OTA 0.4.49 nur mit Go.

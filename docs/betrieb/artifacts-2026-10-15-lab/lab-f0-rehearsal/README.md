# Lab F0-Rehearsal (Overnight)

**Entscheidung 2026-10-16:** Kein weiteres Transport-Overnight (REPLUG/Q10 schon grün).  
Stattdessen **Identity-Isolation B1–B3** auf Lab `.88` — Tooling-Beweis für Feld-F0.

| Beweist | Beweist **nicht** |
|---------|-------------------|
| serial/label/volume-id isoliert drehbar | NBT Cache/P-Wirkung (braucht Auto) |
| Status ↔ Blockdevice konsistent | Prefetch/Eager-Semantik |

```bash
./run-f0-lab-rehearsal.sh          # 1×
./run-f0-lab-rehearsal.sh --loop 8 # Nacht
```

**Hinweis:** Soft-Remount wird bei `stream.active` übersprungen (`msc.remount_skip`).  
`lab_d_campaign.py identity` und `f0-identity.sh` stoppen deshalb zuerst (`/api/lab/stop` + optional Pump `audio_stop`).

**Overnight `run-20261016-000641`:** serial + volume-id 8/8; label 3/8 wegen 11-Zeichen-Stall (`…XXXXX`+`X`).  
Fix: `next_volume_label()` (Append-X, dann Last-Char-Rotate) — siehe `run-20261016-000641/ERGEBNIS.md`.

Feld bleibt: OTA 0.4.51 + F0 B0…B3 am NBT (`artifacts-2026-10-15-feld/feld-f0-prep/`).

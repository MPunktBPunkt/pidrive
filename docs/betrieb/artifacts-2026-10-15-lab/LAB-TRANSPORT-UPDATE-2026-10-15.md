# Lab-Transport-Update · 2026-10-15

Quellen: hu-probe `@5dbec43` · Audit `hu-probe-bmw-s0s2-field-2026` · HU-Facts E11/Q10.

## Was sich fürs Lab ändert

| Alt (Lab-Annahme) | Neu (Feld belegt) | Lab-Konsequenz |
|-------------------|-------------------|----------------|
| Q10 ≈ immer 4 KiB CBW | CBW oft **8** und **240** Blöcke | REPLUG `4` **und** `120` KiB; Sniff/mess-fw Histogramm |
| `all_4kib` / `all_q10_4kib` als Pass | Mischbetrieb normal | Score `matches_field_cbw` |
| Gap ~4 ms = Scheduler | Gap = Messgröße / Link | kein Pace-Modell daraus |
| Burst-39 Konstante | REJECTED | nicht in Sim/Gates |
| ms6-Stall = HU-Recovery | Instrument (vor 0.2.18) | ignorieren |

**Nicht** geändert: Prefetch/Eager/Cache bleiben Semantik → F0, nicht Lab-Transport.

## Umgesetzt

- `tools/mess_hu_capture.py` — Feld-Hist + `--self-test`
- `tools/lab_q10_read_sniff.py` — `q10_matches_field_cbw`, blocks-Anzeige
- `tools/nbt_hu_sim.py` — `--replug-cmd-kib 120`
- `tools/profiles/nbt_evo_lab_2026-10-15.json` — Transport-Epistemik
- Runbooks: `MESS-FW-RUNBOOK.md`, `LAB-D-STARTGATE-RUNBOOK.md`

## Lab-Empfehlung (nächster Abend, ohne NBT)

```bash
python3 tools/mess_hu_capture.py --self-test
python3 tools/nbt_hu_sim.py --self-test
# mit ESP .88 + mess-fw:
python3 tools/mess_hu_capture.py --esp http://192.168.178.88 q10 --sit usb_cycle --wait 20 -o /tmp/q10.json
# REPLUG-Stress (SG):
python3 tools/nbt_hu_sim.py --golden REPLUG --sg /dev/sg0 --replug-cmd-kib 4
python3 tools/nbt_hu_sim.py --golden REPLUG --sg /dev/sg0 --replug-cmd-kib 120
```

Produktpfad bleibt **F0** (`artifacts-2026-10-15-feld/`).

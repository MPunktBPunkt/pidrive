# Lab-NOTE: Stufe 0–2 Lab (2026-10-06)

**Bezug:** [`Stufenplan.md`](../../planung/Stufenplan.md) · [`KONZEPT-HU-SIM-NBT-2026-10-06.md`](KONZEPT-HU-SIM-NBT-2026-10-06.md) · [`MASSNAHMEN-…`](../artifacts-2026-10-06-feld/MASSNAHMEN-HU-CACHE-BACKPRESSURE-2026-10-06.md)

## Erledigt

| ID | Artefakt | Abnahme |
|----|----------|---------|
| M1 | `templates/run.yaml` · `feld_status_poll.py` | 1 Hz + Wanduhr |
| M2 | Spike TinyUSB | USBMSC 1:1, USB-Task max prio, BUFSIZE=4096 |
| M3 | `nbt_profile_extract` · `nbt_evo_2026-10-06.json` | gap median **4** ms, n=4096 |
| O6 | soft_rst empty-body | kein `restart_err=Expecting value` |
| Mimic | `m3_lab_hu_eager_file.py` | Lab-Lauf arm: hostAbs/und≈524288, maxSeq=524288 (**Muster A**) |
| Bridge | `pump_bridge.py` | bitrate→target_bps; `--marker` |
| Sim | `nbt_hu_sim.py` | self-test + Golden **G1/G2/G4/G5 PASS** gegen 0.4.46 |
| Ingest | `tools/ingest/ingest.py` → `data/*.parquet` | Review-Format: runs/status/slots/msc_reads/… |

## Lab-Läufe (Artefakte)

| Lauf | Ergebnis |
|------|----------|
| `lab88-hu-eager-arm/` | Muster_A_like: und=hostAbs=524288, maxSeq=524288 |
| `lab88-hu-eager-cold/` | Re-Read bei vollem maxSeq (Cursor unverändert) |
| `lab88-nbt-hu-sim-g1g4/` | G1+G4 PASS (before_arm=86016; fav2 prefetch 1.2 s) |
| `lab88-nbt-hu-sim-g2/` | G2 PASS: hostAbs=0 nach Cold-Read+Arm, und_delta=0 |
| `lab88-nbt-hu-sim-g5/` | G5 PASS: burst median **8703** B/s, late **6143** B/s |

```bash
sg disk -c 'python3 tools/nbt_hu_sim.py --self-test'
sg disk -c 'python3 tools/nbt_hu_sim.py --golden G1,G2,G4 --sg /dev/sg0'
sg disk -c 'python3 tools/nbt_hu_sim.py --golden G5 --g5-s 68 --sg /dev/sg0'
```

## Offen

- **G3** (Ring-voll / 49 152 B LIVE) — noch nicht automatisiert
- Vollständiger 3×-Repro-Lauf `ALL` hintereinander
- FW Stall / `streamBytesServed_` Reset (Freeze)

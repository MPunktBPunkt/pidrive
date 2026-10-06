# Lab-NOTE: Stufe 0–2 Lab (2026-10-06)

**Bezug:** [`Stufenplan.md`](../../planung/Stufenplan.md) · [`KONZEPT-HU-SIM-NBT-2026-10-06.md`](KONZEPT-HU-SIM-NBT-2026-10-06.md) · [`MASSNAHMEN-…`](../artifacts-2026-10-06-feld/MASSNAHMEN-HU-CACHE-BACKPRESSURE-2026-10-06.md)

## Erledigt

| ID | Artefakt | Abnahme |
|----|----------|---------|
| M1 | `templates/run.yaml` · `feld_status_poll.py` | 1 Hz + Wanduhr |
| M2 | Spike TinyUSB | USBMSC 1:1, USB-Task max prio, BUFSIZE=4096 |
| M3 | `nbt_profile_extract` · `nbt_evo_2026-10-06.json` (+ `nbt_evo_feld-s1-1700.json` gleiche gap/n) | gap median **4** ms, n=4096 |
| O6 | soft_rst empty-body | kein `restart_err=Expecting value` |
| Mimic | `m3_lab_hu_eager_file.py` | Lab-Lauf arm: hostAbs/und≈524288, maxSeq=524288 (**Muster A**) |
| Bridge | `pump_bridge.py` | bitrate→target_bps; `--marker` |
| Sim | `nbt_hu_sim.py` | self-test + Golden **G1–G5 PASS** gegen 0.4.46 |
| Ingest | `tools/ingest/ingest.py` → `data/*.parquet` | Review-Format: runs/status/slots/msc_reads/… |

## Lab-Läufe (Artefakte)

| Lauf | Ergebnis |
|------|----------|
| `lab88-hu-eager-arm/` | Muster_A_like: und=hostAbs=524288, maxSeq=524288 |
| `lab88-hu-eager-cold/` | Re-Read bei vollem maxSeq (Cursor unverändert) |
| `lab88-nbt-hu-sim-g1g4/` | G1+G4 PASS (before_arm=86016; fav2 prefetch 1.2 s) |
| `lab88-nbt-hu-sim-g2/` | G2 PASS: hostAbs=0 nach Cold-Read+Arm, und_delta=0 |
| `lab88-nbt-hu-sim-g5/` | G5 PASS: burst median **8703** B/s, late **6143** B/s |
| `lab88-ingest-demo-1605/` | E2E: G2+1Hz-Poll → Ingest; DuckDB Muster-B hostAbs=0 vs Feld max_host≈4MiB |
| `lab88-nbt-hu-sim-g3/` | G3 PASS |
| `lab88-nbt-hu-sim-all-final{,2}/` | 2× ALL G1–G5 PASS |
| `lab88-feld-s1-replay/` | Feld `feld-s1-1700`: A Muster_B fav1→fav2; B Muster_A_like fav0 (host≈8.4 MiB); G1+G2 PASS |
| `lab88-nbt-hu-sim-all-evening/` | 3.× ALL G1–G5 PASS (Abend, nach Feld-Replay) |

```bash
sg disk -c 'python3 tools/nbt_hu_sim.py --self-test'
sg disk -c 'python3 tools/nbt_hu_sim.py --golden G1,G2,G4 --sg /dev/sg0'
sg disk -c 'python3 tools/nbt_hu_sim.py --golden G5 --g5-s 68 --sg /dev/sg0'
```

## Offen

- G3 ✅ Ring-voll → ear LIVE≈45 KiB + silence; 2× ALL PASS (`all-final`, `all-final2`)
- Pump-Bugfix: Framing war `0xA5` statt `0x01` (kein absEnd-Fill)
- Vollständiger 3×-Repro-Lauf `ALL` hintereinander
- FW Stall / `streamBytesServed_` Reset (Freeze)

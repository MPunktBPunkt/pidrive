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
| `lab88-nbt-hu-sim-g1-c1/` | G1 allein nach C1: **und=hostAbs=438272** PASS |
| `lab88-nbt-hu-sim-all-c1/` | ALL G1–G5 PASS mit **strikter** G1-Assertion |
| `lab88-classify-c2/` | OTHER-Dump: Phase≠0 → false OTHER; Fix bestätigt |
| `lab88-nbt-hu-sim-g1-c2/` | G1: SILENCE=254 OTHER=0 silence_ratio=1.0 |
| `lab88-nbt-hu-sim-g6/` | G6 Lab-F2: Cache-Hit 0 Reads; Remount +128 Reads PASS |
| `lab88-nbt-hu-sim-all-c2/` | ALL nach C2: G1–G5 PASS; G3 SILENCE=116 (kein OTHER) |
| `lab88-nbt-hu-sim-all-c2-repro{2,3}/` | **3× ALL C2-Serie** identisch: und=438272, sil=1.0, ear=45056 |
| `lab88-nbt-hu-sim-g6-repro2/` | G6+G1+G2 PASS |
| `lab88-feld-s1-replay-c2/` | Soft-RST → G2 Muster B + G1 Muster A PASS |
| `lab88-nbt-hu-sim-all-profile-s1/` | ALL mit Profil `nbt_evo_feld-s1-1700.json` PASS (Profil austauschbar) |
| **Vergleichsblatt** | [`KALIBRIERUNG-LAB-HU-2026-10-06.md`](KALIBRIERUNG-LAB-HU-2026-10-06.md) |

```bash
sg disk -c 'python3 tools/nbt_hu_sim.py --self-test'
sg disk -c 'python3 tools/nbt_hu_sim.py --golden G1,G2,G4 --sg /dev/sg0'
sg disk -c 'python3 tools/nbt_hu_sim.py --golden G5 --g5-s 68 --sg /dev/sg0'
sg disk -c 'python3 tools/nbt_hu_sim.py --golden G6 --sg /dev/sg0'   # nicht in ALL
```

## Offen

- **M4/F1** und **M5/F2** (Feld, Video + Remount-Kette) — Stall-Go blockiert
- M9 `streamBytesServed_` Reset erst mit Stall-FW
- G3 Report-Semantik: fill_pre=49152, ear LIVE=45056 (±16 KiB), dann silence
- `m3_lab_hu_eager_file.py` BrokenPipe/Timeout unter Last — Regression über `nbt_hu_sim` abdecken

## C1 (2026-10-06 Nachzug)

Vorher: `arm_uid` vor pre_arm → underruns=524288 trotz expect=438272, OR-Kaskade → falscher PASS.  
Jetzt: pre_arm **ohne** ESP-Arm, dann `arm_uid`; Check `near(und, expect)` ∧ `near(host, und)`. Artefakt: `lab88-nbt-hu-sim-all-c1/`.

## C2 (Overnight)

Vorher: Silence nur Phase-0 → G1 OTHER≈241.  
Jetzt: `silence_hits()` alle Phasen 0..155; G1 `other_ratio=0`, G3 ohne OTHER. Soft-Gate G1 `OTHER < 20%`. Artefakt: `lab88-nbt-hu-sim-all-c2/`.

## G6

Lab-F2-Rehearsal (Sim-Cache + ESP-Remount). **Ersetzt nicht** Feld F2/M5.

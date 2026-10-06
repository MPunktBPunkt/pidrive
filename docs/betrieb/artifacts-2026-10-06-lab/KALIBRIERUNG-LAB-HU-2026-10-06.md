# Kalibrierung Lab ↔ HU — Vergleichsblatt für Feld morgen

**Stand:** 2026-10-06 Abend · FW **0.4.46-dev** · Geometrie **L3** · Freeze (kein Stall)  
**Zweck:** Im Auto gemessene Größen sofort gegen Lab-Soll halten — ohne neue Interpretation.

---

## 1. HU-Leseprofil (Kalibrierdaten)

| Quelle | Datei | n (Traces) | Read | Gap median | Queue |
|--------|-------|------------|------|------------|-------|
| Feld morgen 0723 | [`tools/profiles/nbt_evo_2026-10-06.json`](../../../tools/profiles/nbt_evo_2026-10-06.json) | 20 203 | **4096** (99,9 %) | **4 ms** | 1 |
| Feld s1-1700 | [`tools/profiles/nbt_evo_feld-s1-1700.json`](../../../tools/profiles/nbt_evo_feld-s1-1700.json) | 960 | **4096** (957/960) | **4 ms** | 1 |

**Lab nutzt dasselbe Modell:** `nbt_hu_sim` / Eager-Mimic mit `gap_ms=4`, `READ_N=4096`.  
Beide Profile sind für den Sim **austauschbar** (gleiche Targets). Default-Sim: `nbt_evo_2026-10-06.json`.

**Nicht Kalibrierung:** `max` Gap 65535 ms = Trace-Artefakt, nicht HU-Rate.

---

## 2. Ankerzahlen Feld → Lab-Golden (bitgenau prüfbar)

| Anker | Feld (HU) | Lab-Soll (Golden) | Artefakt |
|-------|-----------|-------------------|----------|
| Muster A Rest | 86 016 + **438 272** = 524 288 (07:58) | G1: `und=hostAbs=**438272**` ±4 KiB | `all-c2*` |
| Muster B Cache | hostAbs=0, maxSeq=524288, Reads stop (08:00/s1 17:23) | G2: `hostAbs_after_arm=0`, `und_delta=0` | `all-c2*`, `feld-s1-replay-c2/G2-*` |
| Ring voll → LIVE | 01.10.: live≈49 152 | G3: fill=49152, ear LIVE=**45056** (±16 KiB), dann silence | `all-c2*` |
| Next-Prefetch | fav2 voll ≤~1–2 s nach EOF | G4: fav2_maxSeq=524288, prefetch≈1,1–1,2 s | `all-c2*` |
| Producer | Burst ≈8,7 KB/s → late ≈6 KB/s | G5: burst≈8703, late≈5887 | `all-c2*` |
| Eager-Rate | ~1 MB/s (4 KiB/4 ms) | Sim gap 4 ms → gleiche Größenordnung | Profil + Eager-Läufe |
| LED | Blink ≈ cold body / MSC | nur Hilfsindikator (R14), kein Orakel | HU-Facts |

**Lab 3× Repro nach C1+C2:** `lab88-nbt-hu-sim-all-c2{,-repro2,-repro3}` — alle PASS, G1/G3-Zahlen bitgleich.  
**Profil s1-1700 als Sim-Input:** `lab88-nbt-hu-sim-all-profile-s1` — ALL PASS (gleiche Ankerzahlen).

---

## 3. s1-1700 — was morgen direkt vergleichbar ist

Aus Poll/Snapshots (auch DuckDB: [`F2-DUCKDB.md`](../artifacts-2026-10-06-feld/feld-s1-1700/F2-DUCKDB.md)):

| Episode | Feld | Lab-Äquivalent |
|---------|------|----------------|
| 17:23 BOB | rc +124, dann flat, hostAbs→0 | G2 / Replay Muster B |
| 17:22 Rock | hostAbs≈1,44 MiB frozen, und≈7,75 MiB | Muster-A-like Familie (Lab G1 auf fav1 exakter) |
| 17:28 Bayern→Rock | rc 382→2345 in ~8 s | Eager ~1,2 MB/s ≈ Profil |
| nach RST | fav2 erneut USB-gelesen | G6 Remount-Zweig (Sim-Cache ≠ HU-Cache!) |

---

## 4. Was **noch fehlt** (nur Auto)

| ID | Kalibrierung? | Status |
|----|---------------|--------|
| **F1** t_timer vs t_eof | Decode-Start — **entscheidend für Stall** | ❓ morgen Video |
| **F2** fav1→fav2→fav1 + OTG | echter HU-Cache | ❓ / RST-Teil [S] |
| Q1 READ10-Timeout | HU-Toleranz ms | ❓ Stufe 5 |
| MPEG Live 22,05 vs Silence 44,1 | Format-Mismatch | bekannt, nicht kalibriert |

---

## 5. Checkliste Auto ↔ Lab (kurz)

1. FW/Geometrie = Lab? (`0.4.46-dev`, L3, `fw_commit`)  
2. Poll 1 Hz + Video Spielzeit (F1)  
3. Nach Session: G1/G2-Anker gegen neue Polls (438272 / hostAbs=0)  
4. Profil optional neu extrahieren: `nbt_profile_extract.py` → gap weiter 4 ms?  
5. Ingest: `./run-ingest.sh` → DuckDB wie s1-1700  

**Lab-Kommando (Referenz):**
```bash
sg disk -c 'python3 tools/nbt_hu_sim.py --golden ALL --profile tools/profiles/nbt_evo_feld-s1-1700.json --sg /dev/sg0'
```

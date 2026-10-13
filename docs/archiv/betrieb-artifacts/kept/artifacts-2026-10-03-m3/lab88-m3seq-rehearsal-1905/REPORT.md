# Lab M3seq-Rehearsal — 2026-10-03 19:05

**FW:** `0.4.42-dev` · ESP `.88` · Bridge `.105 --no-audio` · Host `.108`  
**Tool:** `tools/m3_lab_m3seq_rehearsal.py`  
**Scope:** Lab-Host Instrumentation für Select/Remount — **kein** BMW-Q1–Q3-Ersatz.

## Ergebnis

| Arm | Muster | Ist |
|-----|--------|-----|
| **0 Idle** 30 s nach Sweep | quiet | **PASS** `Δrc=0` |
| **1 Select** fav1 64 Sektoren, kein Remount | neue Reads + Slot-Attribution | **PASS** `Δrc=64=Σn`, `remountGen` gleich, fav1 `bytes +32768` |
| **3a Remount passiv** | Gen↑, Host still | **PASS** `Δgen=1`, `Δrc=0` (Lab-Host) |
| **3b Remount + Nudge** | Gen↑ + Scan | **PASS** `Δgen=1`, `Δrc=256=Σn`, `ov=0` |

## Interpretation (I)

- Select-ohne-Remount ist lab-seitig messbar (Status + JSONL + `slot.bytes`).  
- Soft-Remount allein triggert am Lab-Host **keine** Reads — Nudge (`dd` Boot/Meta) nötig. NBT kann anders reagieren; Feld-Arm3 bleibt Pflicht.  
- M0-Balance hält in allen aktiven Fenstern.

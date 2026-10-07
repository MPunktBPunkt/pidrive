# Feld s2 — Lauf `s2-20261007-172123`

**Zeit:** 2026-10-07 17:21–17:35 · ESP `.89` · FW 0.4.46-dev · **ohne F1** (kein Stick)  
**Capture:** Bridge `--no-audio` · Trace 4 Hz · Status 1 Hz · Marken in `marks.jsonl`

## Ablauf

5× A+C (Z1–Z5): BOB → RST1 → Rock (~60 s) → RST2.  
Z1 abweichend: zuerst Bayern, dann Rock.

## Q8 / R10 (Kurz)

Auswertung: `q8/Q8-REPORT.json` (`feld_q8_msc_order.py --reads msc_reads.jsonl --trace trace.jsonl`).

| Befund | Bedeutung |
|--------|-----------|
| Mehrfach **`r16_resume_like`** | Frische Auswahl startet oft **nicht** bei Dateioffset 0 |
| Muster **`F16 B120 B120 F360…`** (u. a. ep1/6/9/12) | Klassisches R16-/Fragment-Muster; P-Quelle klären |
| Stall-Implikation | „Startposition ≠ 0 — R16-Muster“ → Stall-Go **noch nicht**; feste Zuordnung allein reicht ggf. nicht |

**Stall-Go:** weiter **offen** (F1 fehlt + R10 zeigt Resume-Muster).

## Artefakte

| Datei | Zeilen / Größe |
|-------|----------------|
| `msc_reads.jsonl` | ~10 079 |
| `trace.jsonl` | ~23 426 |
| `marks.jsonl` | 24 |
| `status-poll.jsonl` | ~859 |
| `q8/Q8-REPORT.json` | Q8 |

## Nächstes

1. F1 nachholen (Stick + Hub), sobald Stick da.  
2. Rock-Episoden gezielt als Lab-Replay (`--replay` um Marken-Fenster).  
3. P-Quelle bei frischer Auswahl (gespeicherte Position?) vs. echter Offset-0-Lauf.

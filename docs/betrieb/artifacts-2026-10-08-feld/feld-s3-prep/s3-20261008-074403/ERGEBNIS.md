# s3 P-Quelle — Ergebnis · 2026-10-08

**Lauf:** `s3-20261008-074403` · **FW:** 0.4.46-dev Freeze · **Capture:** Bridge `--no-audio` (von Lab-Host)  
**Serial:** PD0096 → … → **PD0106** (jeder Remount neue Serial)  
**Phase A/B:** nicht formal · Fokus Remount/Resume (C–C9)

## Operator-Orakel (Ohr/Auge) — Kern

| Beobachtung | Evidenz |
|-------------|---------|
| Nach Replug oft **Resume mitten/hinten** im File | Bild da, **kein Ton** |
| **BOB von vorn** starten | **wenige Sekunden Ton**, dann Stille (Ringinhalt 48 KiB ≈ 8,2 s Live-Audio; Producer lief über den Bridge-Service) |
| Bayern → zurück BOB | **gleiches Bild + gleicher Tonabschnitt** |
| Repro mehrfach (C7, C9) | stabil reproduzierbar |

**Deutung (vorsichtig):** HU stellt **P ≠ 0** nach USB-Remount **trotz neuer Serial** wieder her. Schlüssel ist **nicht nur** die flüchtige USB-Session/Serial. Exakter Schlüssel (Track-ID/Name/Größe/Kombi) offen.  
**P ≠ Stall** — erklärt aber die Stille bei Resume in leerem Ringbereich.

## Autoplay nach Replug

| Runde | Serial | Autoplay |
|-------|--------|----------|
| C | PD0097 | BOB (obwohl Rock zuletzt) |
| C2 | PD0098 | Rock |
| C3+ | PD0099… | oft BOB; C5 Bayern |

Nicht immer „letzter Song“.

## Q8 (aus Trace; `msc_reads` leer)

| Episode | Verdict | Muster |
|---------|---------|--------|
| ep3 | **`r16_resume_like`** | `F8 B120 B120 F360…` — Start ≠ 0 |
| ep15 | unclear (Muster nah) | `F16 B120 B120…` |
| viele andere | unclear / no_slot / Index | Remount-/Meta-Fenster |

`head_like` nirgends True in den bewerteten Episoden.

## Schluss (eine Zeile)

**Evidenz heute:** P überlebt Remount + Serial-Wechsel; Resume mitten → Stille bis „von vorn“; Suchraum Richtung persistente Track-/Medien-Bindung, nicht nur Serial.

**Korrektur (Analyse s3, 08.10.):** Die Capture-Bridge `--no-audio` starb sofort (BrokenPipe, ESP hält den bestehenden TCP-Client sticky). Verbunden war der reguläre Bridge-Service **mit Audio** (`absEnd` +~6000 B/s). Nach Replug liest die HU den BOB-Slot **komplett ab 0** (R24); hörbar sind die letzten ~8 s Ring (R25). Details: [`ANALYSE-S3-TONFENSTER-2026-10-08.md`](../../ANALYSE-S3-TONFENSTER-2026-10-08.md)

**Muster-Bericht:** [`../../GESAMTBERICHT-FELD-S3-P-QUELLE-2026-10-08.md`](../../GESAMTBERICHT-FELD-S3-P-QUELLE-2026-10-08.md)

## Artefakte

- `marks.jsonl` / `OPERATOR-LIVE.txt` · `status-poll.jsonl` · `trace.jsonl` · `q8/`
- `msc_reads.jsonl` **leer** (Bridge-Reads nicht mitgeschrieben) — Auswertung über Trace

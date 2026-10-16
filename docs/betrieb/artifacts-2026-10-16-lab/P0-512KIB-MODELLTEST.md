# P0 · 0.4.52 512‑KiB Modelltest (NBT) — **ERLEDIGT 2026-10-16**

**Status:** Feld gelaufen · Auswertung  
[`../artifacts-2026-10-16-feld/feld-512kib-predict-01/ERGEBNIS.md`](../artifacts-2026-10-16-feld/feld-512kib-predict-01/ERGEBNIS.md) ·  
Übergabe [`../artifacts-2026-10-16-feld/UEBERGABE-TAG-2026-10-16.md`](../artifacts-2026-10-16-feld/UEBERGABE-TAG-2026-10-16.md)

## Vorhersage (Ausgang)

```text
512 KiB Slot = 1024 × 512-B-Blöcke
READ10-Sequenz ≈  8  +  4×240  +  56
```

## Feld-Ergebnis

| Claim | Ergebnis |
|-------|----------|
| Max = 240 Blöcke | **ja** |
| Sequenz `8 + 4×240 + 56` | **nein** |
| Sequenz `240,240,32,240,240,32` | **ja** (Summe 1024), mehrfach |
| LIVE-Ohr | selten ~5–6 s nach OTG ohne Weiß |
| Panic / weiße LED | häufig, Episode tot |

**Matrix:** Ableitung **A7** + A2→[S] in `docs/fahrzeug/HU-PARAMETER-MATRIX-2026-10-16.md`.  
**Noch nicht:** Blind-Commit in `HU-Technical-Facts.md` ohne Review (A7 ist Matrix-[S]).

## Setup (historisch)

- FW: `0.4.52-dev` mess, Stall aus, ESP `.89`
- Capture: `ram_local`
- Artefakte: `docs/betrieb/artifacts-2026-10-16-feld/feld-512kib-predict-01/`

## Danach

1. Panic bei physischem OTG  
2. Optional Capture-Timing für Tonfenster  
3. Soft-Cycle Overnight / F0 / Ring weiter hinten

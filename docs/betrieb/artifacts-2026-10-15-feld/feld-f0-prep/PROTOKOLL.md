# F0 — Protokoll & Scoring

Vor dem ersten Replug ausfüllen: **FW ______ · Serial ______ · stall=false?**

## Identity-Definition (fix)

| Feld | Quelle Status | B1 serial | B2 label | B3 volume-id |
|------|---------------|-----------|----------|--------------|
| `usbSerial` | `msc.usbSerial` | **ändern** | gleich | gleich |
| `productRevision` | `msc.productRevision` | **ändern** | gleich | gleich |
| `bpbLabel` | `msc.bpbLabel` | gleich | **ändern** | gleich |
| `rootLabel` | `msc.rootLabel` | gleich | **ändern** | gleich |
| `bpbVolumeId` | `msc.bpbVolumeId` | gleich | gleich | **ändern** |

Isolation PASS nur wenn genau die **fett** markierten Felder differieren.

## Laufblatt

| ID | Klasse A/B | Identity PASS? | READs (keine/Mid/Head/Full) | playingUid | LIVE-Bytes? | Ohr | Notiz |
|----|------------|----------------|------------------------------|------------|-------------|-----|-------|
| B0 | | n/a | | | | | |
| B1 | | | | | | | |
| B2 | | | | | | | |
| B3 | | | | | | | |

## Scoring → Ast

Ankreuzen **eine** dominante Lesart (bei Unklarheit: wiederholen, nicht raten):

| Code | Lesart | Kriterium (mindestens) |
|------|--------|------------------------|
| **I** | Identity dominant | ≥1 von B1–B3: LIVE/hörbar **und** B0 bleibt Cache/Stille; Isolation PASS |
| **C** | Cache dominant | B0–B3: Wiedergabe **ohne** relevante neue Body-Reads; Identity ändert nichts |
| **R** | Read-/Prefetch-Pfad | Hörbar erst **nach** klaren Head/Body-Reads; Identity irrelevant |
| **P** | Play-Intent / Resume-P | Position/Kontext bleibt trotz Inhaltswechsel; Mid ohne Arm möglich |
| **X** | Kombination / unklar | gemischte Muster → UART + Wiederholung; kein D1 |

## Folge (nicht vorab binden)

| Ast | Nächster Auftrag |
|-----|------------------|
| I | Session-Rotation der wirksamen Dimension spezifizieren |
| C | Head-Force / Prefill-Lab-Gate; Cache-Eviction |
| R | Prefetch/Head-Force Messplan |
| P | Intent-Erhaltung / Mid-Play-Arm |
| X | Wiederholung + UART; Fallback Slot-Kette |

Stall-Feld-Go: **erst nach** Ast ≠ X und explizitem Go; CBW blocks 8/240 mitdenken.

# Maßnahmen nach Prefetch-Livelock-Audit · 2026-10-17

**HEAD-Bezug:** Tri-Review Abend `d50196e` · FW `0.4.53-dev` · Stall aus  
**Quellen:** Abend-Feld `feld-go-abend-01/` · [`TRI-REVIEW-ABEND-2026-10-17.md`](TRI-REVIEW-ABEND-2026-10-17.md) · GPT-Schärfung (UART = Gate, nicht Ziel) · Mistral-Kernzahlen  
**Vorgänger:** [`MASSNAHMEN-NACH-TRI-REVIEW-2026-10-17.md`](MASSNAHMEN-NACH-TRI-REVIEW-2026-10-17.md) (M20–M29 bleiben gültig; Status unverändert)

## Urteil (1 Satz)

USB-Transport und Meta/FAT sind raus; der Auftrag ist **Storm-File-Body → Guess/Play-Intent → spielbarer Inhalt** messbar machen — F0 bleibt Schwerpunkt, nicht Busy/167/136-Optimierung.

## Modell (verbindlich)

```text
USB-Transport OK
        │
        ▼
File-Body Reads
        ├── Normal → Guess → Play
        └── Storm (S)
             ├── midFile ≫, bytesFile ↑, Meta konstant
             ├── Guess manchmal möglich
             └── Play meistens nicht
                        │
                        ▼
              ??? Play-Intent / Cache / Resume
                        │
                        ▼
                     F0-Frage
```

| Zustand | Traffic | File-Body | Guess | Play |
|---------|---------|-----------|-------|------|
| **Q** (Quiet) | niedrig | niedrig / saturiert | selten/0 | nein |
| **S** (Storm) | hoch | hoch (`midFile`, `bytesFile`) | gelegentlich | selten |
| **Normal** | normal | zielgerichtet | vorhanden | ja |

`(readCount, playRejectCount)` allein klassifiziert **nichts** — Invariante `reads−rej ∈ {31,32}` gilt auch post-Ton / after-plug.

---

## Maßnahmen-Tabelle (M30+)

| ID | Maßnahme | Prio | Wo | Status |
|----|----------|------|-----|--------|
| **M30** | **P0-Session:** UART **und** Storm-Capture in **einer** verwertbaren Session | **P0** | Feld | ☐ Feld · Lab-Harness ☑ `feld_storm_session.sh` + `arm --storm` |
| **M31** | Stuck-Klassifikator Q/S: Trigger **nie** auf reads/rej allein — Achsen `prefetchHits`, `fav*.midFile`, `bytesFile`, Ohr/Ton | **P0** | Feld (+Status-Poll) | ☐ Feld · Tool ☑ `feld_qs_classify` + poll schema v2 |
| **M32** | Während **S**: MessCapture/Journal → LBA→Band (`mess_band_report`) + Korrelation zu Guess | **P0** | Feld | ☐ Feld · Lab ☑ `band.json` in Session |
| **M33** | Q vs S **reproduzierbar** machen (Zustandstabelle oben; mind. je 1 saubere Episode mit Label) | **P1** | Feld | ☐ |
| **M34** | Reset-Isolation **nach** Storm-Capture: A kein Reset · B ESP-RST · C Soft-Detach/OTG · D HU-Power-Cycle — jeweils: verschwindet S? bleibt Guess-Verhalten? | **P1** | Feld | ☐ |
| **M35** | Guess-Verteilung `msPlugToPlayGuess` **n≥10**; Storm-Guess-Auslöser-Klasse (welche Read-Klasse unmittelbar vor Guess?) | **P1** | Feld | ☐ |
| **M36** | Dashboard/Alert: Q/S-Label + Invariante `reads−rej` nur als Plausibilität, nie als Alarm | **P2** | Lab/Tools | ☐ |
| **M37** | hostAbs-Overshoot nach Tonfenster dokumentieren (Messfakt M27) — Cursor über EOF ≠ Play-Intent | **P2** | Lab/Docs | ☐ (= M27 erweitern) |
| M22′ | M22 bleibt: Guess-Pfad vor Stall; Zusatz: Storm ≠ Blockade (Guess-im-Storm belegt) | — | — | läuft |
| M23 | Stall-Leiter **weiter blockiert** bis M30+M35 grün und Guess greift | — | Feld | ☐ |
| M25 | Identity-Zeitpunkt A/B **nach** M30/M34, nicht parallel zum ersten Storm-Capture | P1 | Feld | ☐ |

### M30 — Pflichtinhalt einer P0-Session

Gleichzeitig vorliegend:

- USB-/MessCapture (arm vor OTG)
- UART (Resetgrund, Panic-Tail, ideal VBUS)
- Status-Poll: `prefetchHits`, `midFile`, `bytesFile`, `guess`, `stream.active`
- Guess-Events mit Timestamp
- Reset/Panic-Marker
- möglichst LBA/Read-Klassen aus Capture

**Erfolgskriterium:** eine Storm-Episode, in der beantwortbar ist: *welche LBAs liest die NBT während S, und was macht die FW unmittelbar danach?*

---

## Reihenfolge (GPT-Schärfung)

```text
P0  UART als Gate + Storm-Capture (M30/M31/M32)   ← eine Session
P1  Q vs S reproduzierbar (M33)
P1  Reset-Isolation A–D auf gefangenem Storm (M34)
P1  Guess-Verteilung n≥10 + Storm-Guess-Klasse (M35)
    └─ optional M25 (Identity-Zeitpunkt)
erst dann  Stall-Leiter M23
```

UART ist **Instrumentierung**, kein eigenes Analyseziel. Ohne UART bleibt Panic = UNKNOWN — Capture trotzdem priorisieren, aber Reset-Isolation ohne UART ist blind.

---

## PiDrive-Auftrag (F0-Fokus)

| Tun | Nicht tun |
|-----|-----------|
| Übergang File-Body-Read → Play-Intent → spielbarer Inhalt verständlich machen | 167/136 oder Quiet-Plateau „reparieren“ |
| Storm als Prefetch-Livelock behandeln (File-Body) | USB-Busy-Transport weiter optimieren (E7/Transport nicht Hauptverdächtiger) |
| Scan/Prefetch ≠ Play trennen (fav2 voll ohne Play) | Sheet-A-HU-Claims ohne Capture |
| Detektor auf pref/midFile/bytesFile/Ohr | Stuck = reads/rej oder „USB tot“ |
| F0 Identity / Silence-Cache / Resume-P | Stall×Identity mischen; Replug-Sturm nach Tonfenster |
| Operator: ≥20 s nach gutem Plug; nach erstem Tonfenster pausieren | Panic „gefixt“; M24 als Cache-Beweis |

---

## Offene Fragen (nur mit M30+)

1. Welche LBA/UID/Klasse liest die NBT im Storm?
2. Warum wird daraus meist kein Guess — auch über ESP-RST hinweg?
3. Welche Read-Klasse löst den belegten Storm-Guess (Poll 17:58:21) aus?
4. Heilt nur HU-Power-Cycle (M34-D)?

---

## Artefakte / Anker

- Facts: Meta-Bytes session-konstant · `reads−rej∈{31,32}` · Guess-im-Storm · midFile dominant · fromHead rar · fav2 oft voll ohne Play · hostAbs-Overshoot  
- Tools: `feld_storm_session.sh` · `mess_hu_capture arm --storm` · `feld_status_poll` (schema 2) · `feld_qs_classify` · `mess_band_report` · UART an `.89`  
- Lab-Prep: [`../artifacts-2026-10-18-lab/lab-storm-capture-prep/ERGEBNIS.md`](../artifacts-2026-10-18-lab/lab-storm-capture-prep/ERGEBNIS.md)  
- Protokoll: [`CAPTURE-PROTOKOLL-STORM-M30.md`](CAPTURE-PROTOKOLL-STORM-M30.md)  
- Kanone: [`TRI-REVIEW-ABEND-2026-10-17.md`](TRI-REVIEW-ABEND-2026-10-17.md) · [`UEBERGABE-NAECHSTE-KI-2026-10-17-FELD.md`](UEBERGABE-NAECHSTE-KI-2026-10-17-FELD.md)

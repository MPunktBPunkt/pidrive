# Tri-Review Abend · 2026-10-17 (GPT + Grok + Mistral) + Rohdaten-Nachrechnung

**Repo:** MPunktBPunkt/pidrive · **HEAD:** `83ce815` · **FW:** `0.4.53-dev` · Stall aus · UART: nein  
**Quellen:** `feld-go-abend-01/` · Reviews GPT/Grok/Mistral · Nachrechnung Status+Polls

## 1. Konsens (alle drei)

- M20/M21 PASS: ≥3× Klasse A, Ton ~6–7 s; Ring voll ≈8,2 s (`cap=49152`, `liveAvailMs=8192`).
- Session-Kipppunkt nach erstem Weiß/Panic → Prefetch ohne Play-Transition; ESP-RST bricht das nicht → HU-persistenter Anteil (INFERENCE).
- M22 labil; Guess-Latenz ~17–22 s (n≈2); Stall (M23) blockiert.
- M24 Gate OK; „VID allein = Ordner“ geschwächt; Favoriten unter Mediensuche.
- underruns = Bytezähler; Stream≠Ohr nach dem Fenster = Normalfall.
- UART / Panic-Ursache = UNKNOWN; nächstes Feld: UART → Stuck-Capture → Reset-Isolation → Guess-Verteilung → M25 → M23.
- Begriff: eher **PREFETCH-LIVELOCK** (HU liest weiter, Transition Prefetch→Guess fehlt), kein totes USB.

## 2. GPT-Widerspruch geklärt (167 Reads / 136 Rejects)

**Beide Berichte halb richtig — das Tupel allein ist kein Stuck-Marker.**

Über **alle** Abend-Snapshots gilt:

| Invariante | Wert |
|------------|------|
| `readCount − playRejectCount` | **31 oder 32** (immer) |
| `bytesDir / Fat / Meta / Boot` | **57344 / 44544 / 114688 / 12800** (konstant) |

`(167, 136)` = typisches **Quiet-Plateau nach leichtem File-Scan** (`prefetchHits≈8`). Es kommt vor bei:

- gutem Plug ohne Play noch (`1752-after-plug`, `power_on`)
- **nach** Bayern-Tonfenster (`bayern-ton-*`, Stream oft noch `active`, `live=0`)
- Stuck ohne Ton (`bayern-notone`, `replug-180335`, Panic)

Unterscheidung braucht **Zusatzachsen**, nicht nur Reads/Rejects:

| | Quiet-nach-Ton | Quiet-ohne-Ton (Stuck-Q) | Storm (Stuck-S) |
|--|----------------|--------------------------|-----------------|
| reads/rej | ~167/136 | ~167/136 | Tausende |
| prefetchHits | ~8 | ~8 | 200–2200+ |
| stream.active | oft **true** fav1 | **false** | false (bis Guess durchkommt) |
| fav1.bytes | 524288 (Body durch) | oft 524288 oder 0 | variabel |
| fav0.midFile | ~8 | ~8 | **600–2000+** (fav0 aufgefressen) |

## 3. Weitere Muster (Nachrechnung, über die Reviews hinaus)

### 3.1 Zwei Stuck-Morphologien

1. **Stuck-Q (Quiet):** gleiche Zähler wie Post-Ton-Quiet, aber kein neuer Guess/kein Ohr-Ton — HU „fertig“ mit leichtem Prefetch, kein Head-Commit.
2. **Stuck-S (Storm):** Rock/„alle Files“/RST-Rock — `fav0` midFile≫, bytes → ~8 MiB, `prefetchHits` 4-stellig, Rejects≈Reads−31. USB sehr lebendig.

→ GPT P0-2 (Stuck-Capture) ist zentral: Capture entscheidet P⊕C (mid-file fav*) vs. Index-only.

### 3.2 Guess kann mitten im Storm kommen (FACT)

Poll `poll-replug-1757.jsonl`: Rejects steigen ~181→2057 (~16 s), dann **17:58:21** `guess=1` / `play=fav1` / Stream an — bei weiter laufenden Rejects. Livelock ≠ „Guess unmöglich“.

### 3.3 Meta-Scan saturiert sofort (FACT)

`bytesDir/Fat/Meta/Boot` ändern sich über die ganze Session **nicht**. Livelock-Traffic ist **fast nur `bytesFile`**. Stützt: Problem = Media-Body-/Play-Intent, nicht erneute FAT-Enumeration.

### 3.4 Head-Reads sind rar (FACT)

Slot-Zähler: `fromHead` typisch **0 oder 2**, `midFile` dominiert (fav1 nach Ton: `fromHead=2`, `midFile=126`, `bytes=524288`). Play-Guess braucht die seltene Head-Sequenz — HU verbringt die Zeit im Mid-file.

### 3.5 fav2 oft „voll vorgelesen“ ohne Play (FACT)

In Scan/Quiet-Zuständen häufig `fav2.bytes=524288`, `fromHead=2`, `midFile=126` während fav1/Stream anders laufen. Scan lädt Station-Bodies aggressiv vor (P⊕C-nah).

### 3.6 hostAbs-Overshoot nach Fenster (FACT → M27)

Nach Bayern-Ton: z. B. `hostAbsCursor=592164` bei `hostExpectFileOff=524288` (Overshoot **+67876**); später sogar ~**+859 KiB**. HU liest über Dateiende weiter (Ring/Stille). Mid-Play kann `hostAbs < expectOff` sein (`replug-175301`).

### 3.7 Soft-Serial ≠ Panic (Konsens, bestätigt)

Drift `PD0305→PD0325` auch in `power_on`-Zyklen. M24 „Serial gehalten“ nur **gate-zeitpunkt**-gültig (Mistral B2).

### 3.8 29-s-Pause (GPT Trace)

In den **Poll-JSONLs** keine >5 s Sample-Lücken; die Pause sitzt vermutlich im Bridge-`msc.reads`-Journal, nicht in Status-Polls. Nächstes Feld: MessCapture/Journal gezielt auf Gap nach 4-KiB-Burst.

## 4. Epistemik (übernommene Schärfung)

| Klasse | Inhalt |
|--------|--------|
| FACT | Panic beobachtet; RST beendet Livelock nicht; msFirstRead≈1005 ms; msGuess≈17–22 s (n=2); Ring 8,2 s; Operator 6–7 s; Meta-Bytes konstant; reads−rej∈{31,32}; Guess-im-Storm möglich |
| INFERENCE | Persistenter Anteil HU/Media-Session; Panic ≠ kausal identisch mit Livelock; Ton = Ringfenster |
| HYPOTHESE | Zweistufiger Handshake (~1 s Scan, ~17–22 s Play-Commit); Identity zeitabhängig (VID+Serial+RemountGen+DIR-Timing+UI) |
| UNKNOWN | Panic-Ursache; Stuck-LBAs; ob nur HU-Power-Cycle heilt; Tonfenster vs. Ring exakt; welche Read-Klasse den Storm-Guess auslöst |

## 5. Ampel + Auftrag (nächste KI)

| ID | Status |
|----|--------|
| M20 | ☑ n≥3; Session-stabil ✗ |
| M21 | ☑ ~6–7 s; Ring 8,2 s |
| M22 | ☑/☐ labil; Latenz gemessen; Storm-Guess möglich |
| M23 | ☐ blockiert |
| M24 | ☑ Gate; Hypothese VID-allein **geschwächt** |
| M25 | ☐ Identity-**Zeitpunkt**-Experiment |
| UART | ☐ P0 |

**Reihenfolge:** UART → Stuck-Capture (Q vs S) → Reset-Isolation A–D (GPT) → Guess-Verteilung n≥10 → M25 → M23.

**Operator:** nach gutem Plug ≥20 s; nach erstem Tonfenster pausieren; kein Replug-Sturm.

**Nicht tun:** Panic „gefixt“; Stuck = USB-tot; n=4096 als CBW-Architektur; M24 als Cache-Beweis; Stall×Identity mischen.

## 6. Zentrale offene Frage (GPT, übernommen)

> Was liest der NBT im Prefetch-Livelock (welche UID/LBA/Klasse), und warum wird daraus (meist) kein Play-Guess — auch über ESP-RST hinweg?

## 7. Artefakte

`feld-go-abend-01/` · `feld-ota-053/` · `MASSNAHMEN-NACH-TRI-REVIEW-2026-10-17.md` · `UEBERGABE-NAECHSTE-KI-2026-10-17-FELD.md`

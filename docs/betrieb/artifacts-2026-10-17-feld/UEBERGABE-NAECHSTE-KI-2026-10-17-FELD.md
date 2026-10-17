# Übergabe · 2026-10-17 Feld (Abend nach Tri-Review)

**Repo:** `MPunktBPunkt/pidrive` · **FW Feld:** `0.4.53-dev` · Stall aus  
**Kanone:** [`MASSNAHMEN-NACH-TRI-REVIEW-2026-10-17.md`](MASSNAHMEN-NACH-TRI-REVIEW-2026-10-17.md) · Abend [`feld-go-abend-01/`](feld-go-abend-01/) · Morgen [`feld-ota-053/`](feld-ota-053/)

## Ein Satz

M20 Klasse-A + ~6–7 s Ton (n≥3) und Favoriten unter Mediensuche sind der Abend-Fortschritt; danach Panic/Prefetch-Stuck ohne stabilen Play-Guess — Stall-Leiter weiter blockiert; M24 Volume-ID-only als Ordner-Fix geschwächt.

## Abend-Ergebnisse (kurz)

| ID | Status |
|----|--------|
| M20 | ☑ PASS n≥3 (danach wieder Weiß/Panic) |
| M21 | ☑ ~6–7 s; Ring voll ≈8,2 s (`liveAvailMs=8192` @ 49 KiB) |
| M22 | ☑/☐ greift sporadisch (`msPlugToPlayGuess` ~17–22 s); nach Panic oft 0 |
| M24 | ☑ Gate VID; Ordner-Hypothese allein **geschwächt** |
| M23 | ☐ wartet auf stabile Guess |
| UART | ☐ nicht erfasst |

## Claude-Korrekturen (unverändert gültig)

Callback≠HU-Architektur; underruns=Bytes; Stall nicht „erstmals“; Play-Guess vor Stall.

## Auftrag (Priorität)

1. UART bei Weiß (Q11)
2. M22 Play-Guess unter Feld-Last stabilisieren — **dann** M23 Stall-Leiter fav1
3. Optional M25 Serial/RemountGen A/B vs M24
4. Nicht: Panic „gefixt“, Layout umbauen, Stall ohne Guess, Replug-Sturm nach erstem Ton

## Artefakte

```
feld-ota-053/          OTA + erster Bayern LIVE (Mittag)
feld-go-abend-01/      M20/M21/M24 + Panic-Stuck + ERGEBNIS
claude-triage-lab-01/  Lab Volume-ID / DIR / underruns
MASSNAHMEN-NACH-TRI-REVIEW-2026-10-17.md
```

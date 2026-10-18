# Übergabe · 2026-10-17 Feld (Abend + Tri-Review GPT/Grok/Mistral)

**Repo:** MPunktBPunkt/pidrive · **HEAD:** `83ce815` (+ Folgecommits falls Review-Docs) · **FW:** `0.4.53-dev` · Stall aus  
**Kanone:** [`TRI-REVIEW-ABEND-2026-10-17.md`](TRI-REVIEW-ABEND-2026-10-17.md) · [`MASSNAHMEN-NACH-LIVELOCK-AUDIT-2026-10-17.md`](MASSNAHMEN-NACH-LIVELOCK-AUDIT-2026-10-17.md) (M30+) · [`feld-go-abend-01/ERGEBNIS.md`](feld-go-abend-01/ERGEBNIS.md) · [`MASSNAHMEN-NACH-TRI-REVIEW-2026-10-17.md`](MASSNAHMEN-NACH-TRI-REVIEW-2026-10-17.md) (M20–M29)

## Ein Satz

M20/M21 reproduzierbar (~6–7 s Ton, Ring ≈8,2 s); danach Prefetch-Livelock (HU liest weiter, Guess oft aus) — ESP-RST heilt nicht; Meta-Scan-Bytes konstant, File-Body-Storm variabel; nächster Hebel UART + Stuck-Capture, nicht Stall/Layout.

## Ampel

| ID | Status |
|----|--------|
| M20 | ☑ n≥3 Klasse A + Ton; Session danach Panic |
| M21 | ☑ ~6–7 s; voller Ring ≈8,2 s |
| M22 | ☑/☐ Latenz ~17–22 s; Guess-im-Storm möglich; nach Panic oft 0 |
| M23 | ☐ wartet |
| M24 | ☑ Gate; VID-allein geschwächt; Ordner = Mediensuche |
| M25 | ☐ Identity-Zeitpunkt A/B |
| UART | ☐ |

## Muster für die nächste Session

1. **Kipppunkt** nach erstem Weiß → Prefetch-Livelock; RST ≠ Heilung (HU-Anteil).
2. **Zwei Stuck-Formen:** Quiet `(reads≈167, pref≈8)` vs Storm (fav0 midFile≫, pref 4-stellig) — `(167,136)` allein ≠ Stuck.
3. **Invariante:** `reads−rej ∈ {31,32}`; `bytesDir/Fat/Meta/Boot` session-konstant → Livelock = File-Body.
4. **Guess-Latenz** 17–22 s; Operator ≥20 s warten; kein Replug-Sturm nach Tonfenster.
5. **Stream≠Ohr** nach Fenster normal; underruns = Bytes; hostAbs kann über EOF (M27).

## Auftrag (Prio) — siehe M30+

1. **M30 P0:** UART als Gate + Storm-Capture in **einer** Session (nicht UART allein) — Lab-Harness ☑; **Feld offen**
2. **M31/M32:** Q/S + Band — Lab ☑; Feld anwenden
3. **M36:** Live `--qs` Dashboard — Lab ☑ (`alert_n=0` trotz Lab-inv≠31/32)
4. **M33/M34:** Q vs S reproduzierbar → Reset-Isolation A–D auf gefangenem Storm
5. **M35:** `msPlugToPlayGuess` n≥10 + Storm-Guess-Auslöser-Klasse
6. Optional M25, dann erst M23 Stall — **kein** 167/136- oder Transport-Tuning

## Nicht tun

Panic „gefixt“ · Stuck = USB-tot · 4 KiB = CBW-Architektur · M24 als Cache-Beweis · Stall ohne Guess · Replug-Sturm nach Ton

## Artefakte

```
feld-go-abend-01/     Status, Polls, M24, ERGEBNIS
feld-ota-053/         Mittag OTA + Bayern
TRI-REVIEW-ABEND-2026-10-17.md
MASSNAHMEN-NACH-LIVELOCK-AUDIT-2026-10-17.md   M30+
claude-triage-lab-01/ Lab
```

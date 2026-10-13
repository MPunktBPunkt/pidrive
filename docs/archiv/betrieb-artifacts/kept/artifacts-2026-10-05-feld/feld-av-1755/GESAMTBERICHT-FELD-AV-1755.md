# Feld AV 17:55 — Head-Trigger BOB→Bayern · 2026-10-05

**FW:** `0.4.45-dev` · Auto `.89` · Serial **PD0073** · Seed **aus** · Bridge `.105` `--msc-lock`  
**Kontext:** nach Lab Prefill PASS + Head-Trigger Mid→Head PASS — Feld: Station-Next wie 15:41  
**Operator:** [`OPERATOR-1755.txt`](OPERATOR-1755.txt)

## Ergebnis (Ampel)

| Check | Ergebnis |
|-------|----------|
| Gate FROZEN Rock/Bayern/BOB | **PASS** (nach Bridge-Retry) |
| BOB→Bayern Wechsel | ausgeführt ~17:58 |
| `playGuess` / Stream-Arm | **nie** (`guess=0`) |
| LED kurz bei Wechsel | **ja** = cold mid |
| Ohr / Ton | **FAIL** |
| Klassifikation | Gate **A PASS** · Head-Trigger **FAIL** (wieder nur mid) |

**Ein Satz:** Lab-Form Mid→Head armt — im Auto kam 17:58 nur Mid (`not_from_head`); Prefill kam nicht zum Zug.

## Ablauf

1. 17:55 Prep: Bridge frisch, OTG aus.  
2. 17:57 OTG rein (LED grün→blau); BrokenPipe → Bridge-Restart → **MSC_MAP_FROZEN**.  
3. 17:58 Wechsel zu Bayern; LED kurz blinkt; halten.  
4. 17:59 kein Ton.

## Messung Bayern-Wechsel

| Größe | Wert |
|-------|------|
| playGuessCount | **0** |
| coldBodyBurst | 1→**2** |
| playReject | 308→**351** |
| Bayern bytes / fromHead / mid | 524288 / **2** / **126** |
| Bridge | `play.reject not_from_head fav1` · `cold_body_burst` · **kein** `audio_start` |
| stream / live / ring | false / 0 / 0 |

Artefakte: [`status-1758-bayern-end.json`](status-1758-bayern-end.json), [`bridge-1758-bayern.txt`](bridge-1758-bayern.txt), [`status-1759-no-tone.json`](status-1759-no-tone.json).

## Folgerung

1. **HU-wann-Head** bleibt die Blockade — BOB→Bayern-Next allein erzeugte 17:58 **keine** Head-Sequenz (anders als 15:41).  
2. Prefill-vor-Arm (Lab PASS) ist im Feld weiterhin **nicht testbar**, solange kein Arm.  
3. Detect/Freeze unverändert richtig: Mid → Reject.

## Nächste Schritte

1. Lab/Bridge: spekulatives Prefill hilft erst **nach** reproduzierbarem Head — Priorität bleibt HU-Head-Trigger (andere Next-Patterns, Timing, Cache).  
2. Oder: Langfrist Detect-Mid-Arm (Freeze — erst nach Hörbeweis-Pfad).  
3. Freeze hält für Detect/Lock.

```
Gate 17:55 PASS (PD0073)
Head-Trigger Feld FAIL (nur cold mid/LED)
Prefill ungetestet (kein Arm)
Freeze hält
```

## Nachtrag 18:00 — Bayern durch

Operator: Bayern zu Ende. Messung: Rock-Body-Sturm (~8,4 MiB, lba→16449), cold 2→5, rej→2314, **guess=0** — gleiche Signatur wie 17:31/17:38. [`status-1800-bayern-durch.json`](status-1800-bayern-durch.json)

## Nachtrag 18:01–18:03 — Remount PD0074/75

OTG neu → Serial **PD0074** dann **PD0075**; Gate erneut FROZEN nach Bridge-Retry.  
GO BOB→Bayern: LED blinkt, **guess=0**, Bayern mid 512 KiB / fromHead=2, kein `audio_start` — Head-Trigger erneut FAIL.  
Artefakte: `status-1803-no-tone.json`, `bridge-1803.txt`, `OPERATOR-1755.txt`.

## Nachtrag 18:04 — Rock Dauerfeuer

Operator: Wechsel zu Rock Antenne, LED Dauerfeuer. Messung PD0076: Rock ~8,4 MiB mid/end (lba→16449), cold 2→5, rej→2314, **guess=0** — Body-Sturm, kein Arm. [`status-1804-rock-dauerfeuer.json`](status-1804-rock-dauerfeuer.json)

**Session-Ende:** OTG 18:06 aus. Head-Trigger in keinem Versuch (PD0073–76).

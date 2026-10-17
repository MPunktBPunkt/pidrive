# Übergabe · 2026-10-17 Feld (Tri-Review GPT/Mistral/**Claude** + Lab-Triage)

**Repo:** `MPunktBPunkt/pidrive` · **HEAD:** nach diesem Commit auf `main`  
**FW Feld:** `0.4.53-dev` · **Lab:** `.88` same  
**Kanone:** [`MASSNAHMEN-NACH-TRI-REVIEW-2026-10-17.md`](MASSNAHMEN-NACH-TRI-REVIEW-2026-10-17.md) · [`feld-ota-053/`](feld-ota-053/) · Lab [`../artifacts-2026-10-17-lab/claude-triage-lab-01/`](../artifacts-2026-10-17-lab/claude-triage-lab-01/)

## Ein Satz

Klasse-A + Bayern LIVE (n=1) bleibt der Fortschritt — Claude korrigiert die Überinterpretation (Callback≠HU-Architektur, Stall nicht „erstmals“, underruns=Bytes, Reset dazwischen); **neues P0 = Repro+UART+Play-Guess**, Ordner-Test = Volume-ID-only (Lab vorbereitet).

## Claude vs GPT/Mistral (entschieden)

| Thema | Entscheidung |
|-------|----------------|
| Live „4 KiB @ 5 ms“ als HU-Architektur | **Ablehnen** (E5/R15 Callback; E11 = CBW) |
| fav1-LBA beweist Favoriten | **Nein allein** — aber mess: **DIR 65+73 gelesen** ✓ |
| Erster Stall am NBT | **Nein** (R29 s6); Play-Guess vor Stall (R30) |
| `software`→`power_on` | **Replug** (`plugCount=2`) — UART/Q11 |
| underruns 732k | **Bytezähler** Stille (FW + R25/R27), ≈1,4×fav1 |
| Ordner fehlend | Hypothese **NBT-Index/BPB-ID**; Lab: Volume-ID-Rotation ✓ |

## Lab erledigt (während Operator unterwegs)

- Stall-Enable false erzwungen
- `fatVolumeId` 1346634188 → **1358003479**, Serial PD0489 gehalten; SG_IO BPB vid match
- DIR-Hits + underruns-Semantik dokumentiert

## Auftrag (Priorität)

1. **M20** 3–5× Klasse-A auf 0.4.53 + UART + Ton-Dauer (M21)
2. **M22** Play-Guess muss greifen, bevor Stall
3. **M24** optional: nur Volume-ID ändern → Ordner-UI?
4. **M23** Stall-Leiter fav1 (0…15 s) erst nach M20+M22
5. Nicht: Layout umbauen, Panic „gefixt“, Callback als CBW verkaufen

## Artefakte

```
feld-ota-053/          OTA, OTG-Poll, flat mess, Bayern LIVE
claude-triage-lab-01/  Volume-ID, DIR-Hits, underruns-note, ERGEBNIS
MASSNAHMEN-NACH-TRI-REVIEW-2026-10-17.md
```

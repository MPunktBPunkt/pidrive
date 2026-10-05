# Feld AV 18:07 — RST + Head-Trigger · 2026-10-05

**FW:** `0.4.45-dev` · Auto `.89` · Serial **PD0076→PD0077** · Seed **aus** · Bridge `.105` `--msc-lock`  
**Operator:** [`OPERATOR-1807.txt`](OPERATOR-1807.txt)

## Ergebnis (Ampel)

| Check | Ergebnis |
|-------|----------|
| Gate FROZEN Rock/Bayern/BOB | **PASS** |
| Head-Trigger / `playGuess` | **PASS** — Bayern `guess=1`, dann Rock `guess=2` |
| Stream + Ring | **an**, Ring **voll** (49152) |
| `liveBytes` hörbar | **FAIL** — Bayern durchgängig `live=0`; Rock Zähler ~254 k aber Host weit vor Fenster |
| Ohr / Ton | **FAIL** (Operator) |
| Klassifikation | Gate **A PASS** · Arm **PASS** · AV **B FAIL Fenster** |

**Ein Satz:** Nach RST kam endlich der Head-Arm (wie 15:41) — Ring voll, ffmpeg Bayern — aber Cursor/Fenster-Miss (`live=0`): Host ~254 KiB, Fenster bereits ~457 KiB+ (**Fenster voraus**, nicht „Host outrannt“ wie 15:41).

**Review:** [`../KRITIK-REVIEW-MISTRAL-GPT-FELD-1807-87d2523.md`](../KRITIK-REVIEW-MISTRAL-GPT-FELD-1807-87d2523.md) — `253952` sehr wahrscheinlich Underrun-Zähler seit Arm auf `absBase≈0`, nicht persistierter Cursor.

## Ablauf

1. 18:07 RST, OTG ein, alle Sender.  
2. 18:08 Gate FROZEN (Bridge-Retry nach BrokenPipe).  
3. 18:09 bereits auf Bayern → **`playGuess=1`**, `playing=Rock Antenne Bayern`, `stream.active`, Ring voll, **`live=0`**.  
4. 18:10 kein Ton; Autoplay wechselt.  
5. 18:11 Rock: `guess=2`, Stream an; Host ≫ absEnd.  
6. 18:12 weiterhin kein Ton. Ende 18:13.

## Messung Bayern-Arm (Kern)

| Größe | Wert |
|-------|------|
| playGuessCount | **1** |
| play / uid | Rock Antenne Bayern / fav1 |
| stream.active / cursorArmed | true / true |
| ring_size | **49152** (voll) |
| hostAbsCursor | **253952** (= `streamBytes`; 62×4096 — vermutlich HU-Burst + Underrun-Zähler) |
| absBase..absEnd | läuft voraus (z. B. 457112..506264) |
| streamBytes / underruns / live | 253952 / 253952 / **0** |
| Bridge | `play_uid=fav1` + `audio_start` + ffmpeg Rock-Antenne-Bayern |

→ Gleiche Fenster-Signatur wie Abend 15:41, aber Ring diesmal **nicht** leer beim Arm (Prefill/Producer hatte Inhalt — Host trotzdem außerhalb).

Artefakte: [`status-1809-guess.json`](status-1809-guess.json), [`status-1809-armed-window.json`](status-1809-armed-window.json), [`bridge-1809-arm.txt`](bridge-1809-arm.txt).

## Rock nach Autoplay

- `guess=2`, fav0, Ring voll.  
- `liveBytes`-Zähler ≈253952 bei zugleich `hostAbs` ~6 MiB und `ahead` ≫ 0 → **kein** in_window; Ohr nein.  
[`status-1811-rock-now.json`](status-1811-rock-now.json), [`status-1812-no-tone.json`](status-1812-no-tone.json).

## Folgerung

1. **HU-wann-Head** ist nach RST **reproduzierbar** (17:55 ohne RST: nie; 18:07 mit RST: ja).  
2. Blocker eingegrenzt: **Arm-/Producer-Timing** — Arm + voller Ring reichen nicht, wenn der Cursor früh auf kleinem `absBase` armt und durch Underruns auf ~254 KiB läuft, während der Ring scrollt (18:07: Fenster **voraus**).  
3. Lab Prefill PASS zeigt das Gegenbild (Cursor im Fenster) — Ursache ist Timing, nicht „Ring leer“.  
4. Freeze hält (kein Detect-Umbau; kein pauschaler FW-Snap vor Lab-Timeline).

## Nächste Schritte

1. **Lab P0:** Arm-Timeline (`cursorArmed` false→true, `absBase` beim Arm, Reads bis 253952) + **Versuch C** (Producer zuerst, dann Head-Arm).  
2. Instrumentierung: `fileOff`, `headResyncs` je Read (nearHead-Resync?).  
3. Feld erst nach Lab-Antwort; optional kurz RST→dense Correlate zur Bestätigung.  
4. Freeze hält.

```
Gate PASS · Head-Arm PASS (nach RST)
Fenster FAIL live=0 (Cursor/Fenster-Miss)
Nächstes: Lab Arm-Timeline + Versuch C
Freeze hält
```

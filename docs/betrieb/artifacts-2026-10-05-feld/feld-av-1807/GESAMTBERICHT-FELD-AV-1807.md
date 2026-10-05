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

**Ein Satz:** Nach RST kam endlich der Head-Arm (wie 15:41) — Ring voll, ffmpeg Bayern — aber Host outrannt / hängt außerhalb → kein Ton.

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
| hostAbsCursor | **253952** (stuck) |
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
2. Nächstes Blocker ist klar **Fenster/Prefill-Timing**: Arm + voller Ring reichen nicht, wenn Host schon bei 254 KiB und Fenster hinterherläuft bzw. Host später wegläuft.  
3. Lab Prefill-vor-Arm PASS bleibt relevant — im Feld muss Fill den Host **einholen/halten** (`liveBytes>0` anhaltend + `in_window`).  
4. Freeze hält (kein Detect-Umbau).

## Nächste Schritte

1. Lab/Bridge: Prefill + Pace so, dass nach Head-Arm `host` im Fenster bleibt (nicht nur Ring voll).  
2. Feld: RST→schneller Tip nur noch zur Fenster-Messung mit densem Correlate.  
3. Freeze hält.

```
Gate PASS · Head-Arm PASS (nach RST)
Fenster FAIL live=0 / Host außerhalb → kein Ton
Nächstes: Prefill hält Host im Fenster
Freeze hält
```

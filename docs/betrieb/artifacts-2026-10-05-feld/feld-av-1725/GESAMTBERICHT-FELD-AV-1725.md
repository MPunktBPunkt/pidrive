# Feld AV 17:25 — 2026-10-05 ~17:25–17:39

**FW:** `0.4.45-dev` · Auto `.89` · Serials **PD0071→PD0072** · Seed **aus** · Bridge `.105` `--msc-lock`  
**Kontext:** Kurzlauf nach Lab Arm-Diag (mid≠Arm, Head-Arm bei ring=0) + HU-Mimic Fenster-Outrun  
**Operator:** [`OPERATOR-1725.txt`](OPERATOR-1725.txt)

## Ergebnis (Ampel)

| Check | Ergebnis |
|-------|----------|
| Gate Sender-Slots | **PASS** (PD0071 + Remount PD0072) |
| `MSC_MAP_FROZEN` Rock/Bayern/BOB | **PASS** |
| `playGuess` / Stream-Arm | **nie** (`guess=0` durchgängig) |
| AV / Ohr hörbar | **FAIL** |
| LED-Blinken | **ja** = cold mid/end Body-Reads (`not_from_head`) |
| Klassifikation | Gate **A PASS** · AV **B FAIL Arm** (kein Fenster-Fall — Stream nie aktiv) |

**Ein Satz:** Gate stabil; HU liest Sender-Slots nur mid/end (LED), Detect armiert nicht — Feld bestätigt Lab „mid≠Arm“.

## 1. Gate

- Prep 17:25: frische Bridge, Traces leer, OTG noch aus ([`status-00-pre-otg.json`](status-00-pre-otg.json)).
- 17:28 OTG ein → Bridge BrokenPipe → Restart →  
  `MSC_MAP_FROZEN [Rock Antenne,Rock Antenne Bayern,Radio BOB!,Menue]` ([`bridge-gate.txt`](bridge-gate.txt), [`status-gate-pass.json`](status-gate-pass.json)).
- Remount 17:36: Serial **PD0072**, erneut FROZEN ([`bridge-1736-bayern.txt`](bridge-1736-bayern.txt)).

## 2. AV-Läufe

### 2.1 Autoplay BOB (17:28–17:30)

- Alphabetisch erster Sender; kurzes LED-Blinken, vor BOB-Ende nochmal.
- Correlate-1/2: `stream_active=false`, `liveBytes=0`, `playGuess=0`.
- Slot-Bytes BOB/Bayern je ~512 KiB, `fromHead=2`, `midFile=126`.
- Bridge: `cold_body` / kein `audio_start` ([`bridge-1730-bob-led.txt`](bridge-1730-bob-led.txt), [`status-1730-bob-led.json`](status-1730-bob-led.json)).

### 2.2 Bayern→Rock Wechsel (17:31)

Starkes LED-Blinken am Ende Bayern / Start Rock:

| Größe | Delta |
|-------|--------|
| Rock slot bytes | ~0,4 MiB → **8,4 MiB** |
| Rock midFile | 91 → **2054** (maxSeq ≈7 MiB) |
| coldBodyBurst | 2 → 5 |
| playReject | 351 → 2314 |
| playGuess | **0** |
| stream.active / hostAbs / ring | false / 0 / 0 |

Trace: sequenzielle 4k-Reads nahe **Rock-Dateiende** (lba≈16337…16449).  
Artefakt: [`status-1731-bayern-tip.json`](status-1731-bayern-tip.json), [`correlate3/`](correlate3/).

### 2.3 Remount + bewusster Bayern-Tip (17:36–17:38)

Ziel: Head-Arm-Versuch (Lab-Hypothese).

- OTG aus/an → PD0072, Gate FROZEN.
- Bayern tippen: wieder nur **512 KiB mid**, `fromHead=2`, `guess=0` ([`status-1736-bayern.json`](status-1736-bayern.json)).
- Danach HU wieder auf Rock: Body-Sturm erneut (~8,4 MiB), cold 2→6, rej→2314, **kein** `audio_start` ([`status-1738-rock-blink.json`](status-1738-rock-blink.json), [`bridge-1738-rock-blink.txt`](bridge-1738-rock-blink.txt)).
- Operator: starkes Blinken; Bayern zu Ende, Rock läuft; nach wenigen Sekunden wieder Blinken.

## 3. Correlate / Messhinweis

Standard-Correlate (`hostAbs`/`live`) blieb flach **null**, obwohl LED/Slot-Bytes stark stiegen — erwartbar ohne Arm (`hostAbs` nur bei armed Cursor). Slot-/cold-/reject-Poller ([`correlate3/`](correlate3/)) zeigt die Body-Stürme.

## 4. Was belegt / was nicht

**Belegt:**

1. Abend-Gate mit frischer Bridge reproduzierbar (PD0071/72).  
2. Feld-HU-„Play“ hier = **cold mid/end**, nicht Head → **kein playGuess / kein Stream**.  
3. LED-Starkblinken = MSC-Traffic (Body), **nicht** Live-MPEG.  
4. Remount+Bayern-Hold ändert das Muster nicht.  
5. Passt zu Lab Arm-Diag: mid rejects, nur Head würde armieren (dort ring=0-Folgeproblem).

**Nicht belegt:**

- Feld-Lauf mit `playGuess≥1` / `stream.active` in dieser Session  
- Fenster-Outrun am Auto (kein Producer)  
- Detect-Umbau nötig (Messlage, Freeze hält)

## 4b. Review-Nachtrag (`4bcadaf`-Prüfung)

Externer Review + Cursor-Gegenprüfung: [`KRITIK-REVIEW-FELD-1725-4bcadaf.md`](KRITIK-REVIEW-FELD-1725-4bcadaf.md).

- **Übernommen:** Head-Trigger der HU ist die neue offene Feldfrage (15:41 einmal Head→Arm; 17:25/36 nie). `mscTrace` 15:41 beginnt erst bei Mid→Head — Vorlauf fehlt im Ring.
- **Anomalie:** nach Remount PD0072 `readOverflow=67`; kurz `readsEmit=0` bei `readCount>0` (M0: Emit braucht Bridge-Drain) — mitloggen, kein Arm-Beweis.

## 5. Nächste Schritte

1. Lab: Prefill/Fill **vor** Head-Sequenz (Gegenmittel zu ring=0 nach Arm).  
2. Feld erst wieder, wenn Lab hörbaren Head→liveBytes-Pfad hat.  
3. Freeze hält (Detect/Lock/Ring unverändert).

```
Gate 17:25 PASS (PD0071/72 FROZEN Rock)
AV Ohr FAIL (Arm nie — cold mid/LED)
Lab mid≠Arm im Feld bestätigt
Freeze hält
```

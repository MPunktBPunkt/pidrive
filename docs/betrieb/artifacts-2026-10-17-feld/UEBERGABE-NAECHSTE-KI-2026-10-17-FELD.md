# Übergabe · 2026-10-17 Feld (nach Tri-Review GPT/Mistral/Claude)

**Repo:** `MPunktBPunkt/pidrive` · **HEAD:** `724e492` (= `origin/main`)  
**FW Feld `.89`:** `0.4.53-dev` · **Lab-Vorbereitung:** `6ee1b96`  
**Kanone:** [`feld-ota-053/ERGEBNIS.md`](feld-ota-053/ERGEBNIS.md) · Lab [`../artifacts-2026-10-17-lab/UEBERGABE-NAECHSTE-KI-2026-10-17.md`](../artifacts-2026-10-17-lab/UEBERGABE-NAECHSTE-KI-2026-10-17.md) · Tri-Review (GPT + Mistral + Claude, 17.10.)

## Ein Satz

Erstmals **Klasse-A-OTG + Bayern LIVE auf fav1** nach OTA 0.4.53 (n=1) — Panic ist nicht mehr „jeder Lauf tot“, sondern **Reproduzierbarkeit ist neues P0**; Ordner-UI flach, Playback ok; Stall-Leiter am NBT als Nächstes nach 3–5 Wiederholungen.

## Verifikation (Artefakte nachgerechnet, 17.10. Nachmittag)

| Claim | Artefakt | Ergebnis |
|-------|----------|----------|
| 107/107 Polls, kein Panic | `otg-1210/` | ✓ resets nur `software`; LEDs `uart`→`otg`; pumpTcp immer true; RSSI −86…−76 |
| OTG-Fenster reset | `otg-1210` | ✓ **`software`** (OTA-Nachlauf) — GPT sagte teils `power_on` → korrigiert (Mistral) |
| Bayern LIVE fav1 | `klasse-a-bayern-1214` | ✓ `stream.active/uid=fav1`; `fav1.bytes=maxSeq=524288`; `msc.streamBytes=524288` |
| bytesFile Arithmetik | Status | ✓ 557056 = 32768 (fav0-Anteil) + 524288 (fav1) |
| Identity PD0286 | Status | ✓ usbSerial/root/bpb/volume = PD0286, rev 0286 |
| LIVE-Takt 4 KiB @ ~5 ms | `mscTrace` (96) | ✓ **alle** 96 Events `n=4096`, gap 5–6 ms (mean 5,14), LBA-Δ=8, Band 16721→17481 in fav1 |
| Eager 240er | `nbt-flat-1212/mess.json` | ✓ früher Scan: blocks-Hist inkl. **8×240** + viele 8er — **andere Capture-Phase** als mscTrace |
| Stream≠Ohr im Erfolg | Bayern-Status | ✓ `hostAbsCursor=817380` > `hostExpectFileOff=524288`, `liveAvail=0`, `underruns=732404`, Ton trotzdem da |
| `stream.size=49152` | Status | = Ring-/Puffer-**cap**, nicht Dateigröße (Datei 524288) |
| Lab Stall+QD1 | `stall-ladder-full-01` | ✓ 18 rows; `qd1_audio.all_consistent=true`, `any_second_lba=false` |

**Epistemik:** n=1 Klasse A ≠ Panic gefixt. A7 (240/240/32-Muster) in diesem Lauf **nicht** neu bewiesen — nur 512‑KiB-Slot + Vollread **kompatibel**. Zwei-Phasen-Lesen (Eager 240 / Live 4 KiB) ist belastbar, aber aus **zwei** Artefakten kombiniert (mess Scan + mscTrace Live), nicht aus einem durchgehenden Capture.

## Ampel

| Thema | Stand |
|-------|-------|
| OTA 0.4.53 am NBT | 🟢 |
| Klasse-A OTG (dieser Zyklus) | 🟢 n=1 |
| Bayern LIVE fav1 | 🟢 |
| WLAN/Pump unter dem Lauf | 🟢 in diesem Lauf |
| Panic dauerhaft weg | 🟡 Repro ausstehend |
| Panic-Ursache | 🔴 UART/VBUS noch offen |
| Ordner-UI vs Stick | 🟡 UI/Presentation, kein Playback-Blocker |
| LIVE-Takt 4 KiB (R15) | 🟢 Trace-belegt |
| underruns / hostAbsCursor | 🟡 Semantik klären |
| Stall am NBT | 🟠 bereit nach Repro |
| Lab (Q10, Vollleiter, QD1, SG_IO, Bin) | 🟢 |

## Auftrag an die nächste KI (Priorität)

1. **B3 / neues P0 — Klasse-A-Repro:** 3–5 identische Plug-Zyklen auf **exakt 0.4.53**, Poll + resetReason + Ohr, **UART diesmal an**. Alle A → Panic P1-historisch; sonst M8 (UART/VBUS A/B).
2. **B5 Matrix:** LIVE = 4 KiB @ ~5 ms (R15); Eager = 240er-CBWs — als Arbeitsmodell [S]/vorläufig.
3. **B1/B2 Lab (ohne Auto):** `underruns`-Zählersemantik + `hostAbsCursor`-Definition dokumentieren/klären.
4. **B4 Ordner:** Ursache isolieren (Cache vs FAT/LFN vs Ansicht) — **kein** Layout-Umbau vor Befund. DIR-Vergleich vs Stick; optional frische Serial/Volume-ID.
5. **Danach Stall-Leiter am NBT auf fav1** (LBA 16465–17488, 512 KiB): 0/1/2/5/10/15 s, Vorhersage vorher, volle Telemetrie — A3/A4/QD=1-am-NBT.
6. **B6:** `playGuessCount=0` / `playReject=136` trotz Stream — Detektion auf Favoriten-Pfad.
7. **B7:** `nbt-flat` mess.json Scan-Geometrie detailliert ingesten (8er/240er-Mix).

## Nicht tun

Panic als „gefixt“ bezeichnen · Ordner-Layout umbauen vor Ursachenklärung · 512‑KiB-Wiederholungen · Stall vor Repro/UART · Soft-Cycle mit Stall mischen · `dd` als MSC-Wahrheit · F0 vor Stall-A3/A4 am NBT

## Artefakte

```
docs/betrieb/artifacts-2026-10-17-feld/feld-ota-053/
  ERGEBNIS.md
  status-{before,after,final}-ota.json
  otg-1210/{SUMMARY.json,status-poll.jsonl}
  nbt-flat-1212/{status.json,mess.json}
  klasse-a-bayern-1214/status.json   ← mscTrace Live 4KiB

docs/betrieb/artifacts-2026-10-17-lab/
  stall-ladder-full-01/   ← QD=1 Lab
  favoriten-read-behavior-sgio-01/
  BIN-RICHTLINIE.md
```

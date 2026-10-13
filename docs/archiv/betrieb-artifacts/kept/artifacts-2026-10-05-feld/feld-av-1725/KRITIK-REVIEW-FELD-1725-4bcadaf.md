# Kritik Review Feldtest 17:25 (HEAD `4bcadaf`) · 2026-10-05

**Quelle:** externer Review-Bericht „Feldtest-Review 05.10.2026 17:25 — HEAD 4bcadaf“ (vollständiger Text unten / Canvas)  
**Prüfer:** Cursor · gegen Rohartefakte `feld-av-1725/` + `feld-av-abend-1530/status-1541-…` + M0-Semantik

## Kurzurteil

Review ist **überwiegend bestätigt**. Klassifikation Gate PASS / Arm nie / Lab mid≠Arm trägt die Rohdaten. Zwei Präzisierungen und ein Lab-Auftrag übernehmen wir.

| Review-Claim | Urteil | Hinweis |
|--------------|--------|---------|
| Gate PASS PD0071+72, FROZEN | ✅ | bridge-gate / bridge-1736 |
| `playGuess=0` überall, mid/end Rock-Sturm | ✅ | Status-Serie + Trace lba≈16449 |
| „Feld bestätigt Lab mid≠Arm“ | ✅ | |
| 05.10. kausal: 15:41 Arm@ring0→Outrun; sonst Mid→Reject; 17:25 bestätigt Mid | ✅ | stimmig mit `6e2c427` + `305b55f`-Kritik |
| Lab-Pause + Prefill-vor-Arm, Freeze hält | ✅ | |
| **Head-Trigger offen** (15:41 1× Head, 17:25 nie) | ✅ **neu, übernommen** | siehe §1 |
| `readOverflow=67` / `readsEmit=0` unerklärt | 🟡 **teilweise erklärt** | siehe §2 |
| Correlate-Watch-JSONLs nicht im Detail | ⚠️ akzeptiert | Finals + Snapshots reichen |

## 1. Head-Trigger 15:41 — was die Daten wirklich zeigen

`status-1541`: `playGuessCount=1`, `msPlugToPlayGuess=81125`.

`mscTrace` (Ring, n=96) beginnt **bereits** bei Mid `lba=16929`, dann Sprung auf Head `16465` (+ sequentiell 4 KiB).  
→ Was dem Mid→Head-Sprung **unmittelbar vorausging**, ist in diesem Snapshot **nicht** im Trace (Ring zu spät). Operator 15:40–41: BOB „läuft“ (UI), dann **HU wechselt selbst BOB→Bayern** (nicht nur kalter Tip).

**Lab-Auftrag:** Head-Trigger-Hypothesen testen, u. a. „Next/Station-Change nach laufendem Slot“ vs. „kalt tippen nach Remount“ — mit Trace-Export **vor** dem Arm (größeres Fenster / JSONL), nicht nur Status-Ring.

## 2. `readOverflow=67` / `readsEmit=0`

Serie bestätigt Review:

| Snapshot | overflow | emit | reads |
|----------|----------|------|-------|
| pre-remount PD0071 | 0 | 1644 | 2345 |
| plug/bayern PD0072 | **67** | **0** | 250–382 |
| 1738 rock-blink | **67** | 819→892 | 2232–2345 |

Nach M0-Semantik: `readsEmit` steigt nur bei Bridge-Burst-Drain; `readOverflow` = Drops wenn Queue nicht nachkommt. Remount `USB_SESSION_END→START` + kurzzeitig nicht gedrainte Bursts erklären **emit=0 bei readCount↑** und Overflow plausibel — **kein Arm-/Fenster-Beweis**, aber mitloggen bleibt richtig (Review §8.3).

## 3. Übernommene nächste Schritte (Reihenfolge)

1. Lab Prefill-vor-Arm → Ziel `liveBytes>0` **anhaltend**.  
2. Lab: 15:41 Head-Trigger-Repro / Trace-Vorlauf.  
3. Lab: `readOverflow` + Ring-`size` zum Arm-Zeitpunkt mitloggen.  
4. Erst dann Feld. Detect unverändert. Freeze hält.

## 4. Ampel (Cursor)

Mit Review einverstanden: Gate/Arm-Miss 🟢 · Head-Trigger 🟠 · Prefill 🟠 · Hörnachweis 🔴 · Gesamt 🟡.

# Kritik Mistral-Review Lab-Follow-up (`305b55f`) · 2026-10-05

**Prüfer:** Cursor (lokal gegen Rohartefakte + `StreamBuffer.h` / `UsbMscGadget.cpp`)  
**Basis:** Mistral-Bericht „Lab-Follow-up zum Feldabend“

## Kurzurteil

Mistral ist **überwiegend korrekt** und ehrlich bei `mirrors_1541:false`. Drei Präzisierungen:

| Mistral-Claim | Urteil | Korrektur |
|---------------|--------|-----------|
| Outrun-Mechanismus Lab-A + Semantik | ✅ | numerisch bestätigt (`absBase≡0`, host≈106 KiB/s Mittel, absEnd≈7.7 KiB/s) |
| Host „~0,9 MB/s“ | 🟡 | das ist die **theoretische** 4 KiB@4,5 ms-Rate; Serienmittel A nur ~**106 KiB/s** (Pausen/Samples) |
| B: 4× `in_window`, und=0 | ✅ | lokal **5**er Streak, und=0 in 5 Samples |
| A Near-Mirror, nicht exakt | ✅ | REPORT Flags stimmen; Gesamtbericht-Tabelle war zu weich → korrigiert |
| Feld näher an C als A | 🟡 | Feld-Snapshot Ring voll (wie C-Spätphase), aber **live=0 ab erstem active** (wie A-Form, strenger). Weder reines A noch C |
| „Fenster statisch“ widerlegt | 🟡 | In **A** ist Fenster faktisch eingefroren (`absBase=0`) — Mistral richtig: nur „alleinige Ursache“ ist widerlegt |
| StreamBuffer-Doku | ✅ | gegen `StreamBuffer.h` lokal bestätigt (Cursor++ bei Underrun) |
| Tool-Code nicht geprüft | ⚠️ | akzeptiert; Tool läuft und liefert Zeitreihen |

## Feld 15:41 — zusätzliche Code-/Trace-Lesung

`status-1541`: `playGuessCount=1`, `msPlugToPlayGuess=81125`, `playDetect.minSeqBytes=6000`, `headLbaSlop=12`.

`mscTrace` um den Arm: zuerst Mid-LBA (~16929, fileOff≈237 KiB), dann **Head** 16465 und sequentiell 4 KiB — passt zu Detect: Mid → `not_from_head`/prefetch; Head-Sequenz ≥6 KiB → `play.guess`.

Correlate-1540 erstes `stream_active`: sofort `hostAbs=253952`, `und=sb`, `live=0`, `abs=[0,0]` (alte Correlate-Lücke). → Arm + Outrun innerhalb &lt;1 s Messraster; Producer nicht vorausgefüllt.

## Was Mistral für den nächsten Schritt richtig priorisiert

Arm-Diagnose **mit Cursor-/Ring-Zustand beim Arm** — verbindet Tip-ohne-`play_uid` und 0-live-ab-Anfang.

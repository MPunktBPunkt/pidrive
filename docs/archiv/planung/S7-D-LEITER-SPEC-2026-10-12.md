# S7 Startup + D Fixed-Huge-File · Spezifikation · 2026-10-12

**Status:** S7-B + D0 Lab auf `.88` **grün** (`0.4.49-dev`). Feld-Go offen.  
**Auftrag:** [`../betrieb/artifacts-2026-10-12-feld/UEBERGABE-S6-NAECHSTE-KI-2026-10-12.md`](../betrieb/artifacts-2026-10-12-feld/UEBERGABE-S6-NAECHSTE-KI-2026-10-12.md)

## S7 — Stall nur nach Head-Play

### Problem (s6)

Nach OTG ~20 s kaum bedienbar; `stream_on` (Menu/Pump) aktivierte Live-Overlay **bevor** `play.guess` → Body-Reads mit BUSY blockierten die HU-Initialisierung.

### Fix 0.4.49 (`stallScope=1`)

| Zustand | Verhalten |
|---------|-----------|
| `stallEnable` + scope 1 + **nicht** `stallArmed` | Live-Reads wie ohne Stall (`readAt`) — kein BUSY |
| `play.guess` from head | `stallArmed=true` → danach E7 Busy-Pacing |
| Plug / `startStream` / `stopStream` | `stallArmed=false` |
| `stallScope=2` | bisheriges Verhalten (alle Live-Body-Reads) |

Telemetrie neu: `msc.stall.armed`, `msc.stall.skipNotArmed`.

### Lab-Messung

```bash
python3 tools/lab_s7_startup_poll.py --esp http://192.168.178.88 --arm-stall --seconds 90 \
  --out docs/betrieb/artifacts-2026-10-12-lab/lab-s7-startup
```

Soll: vor `stall_armed` steigt `skipNotArmed`; Retries erst danach.

**Lab 2026-10-12:** Poll [`lab-s7-startup/ERGEBNIS`](../betrieb/artifacts-2026-10-12-lab/lab-s7-startup/ERGEBNIS.md) — armed@play.guess.  
Stream-before-guess [`lab-s7-stream-before-guess/ERGEBNIS`](../betrieb/artifacts-2026-10-12-lab/lab-s7-stream-before-guess/ERGEBNIS.md) — **PASS** (p50 !armed≈5 ms / armed≈1021 ms).

## D — Fixed Huge Live File (Leiter)

Nicht dynamisch FAT-Size wachsen. Feste Slot-Bytes von Anfang an.

| Stufe | Größe | Soll (≈ @6 kB/s) | Geometrie |
|-------|-------|------------------|-----------|
| D0 | 512 KiB | &gt;60 s bis EOF | L3 fav1/fav2 heute |
| D1 | 1 MiB | &gt;2 min | neues Build-Flag / Slot |
| D2 | 2 MiB | ~5–6 min | |
| D3 | 8 MiB | ~22 min | L3 fav0 schon 8 MiB — mit S7+Identity |
| D4 | + Resume-Test | Mid-P stumm? → Rotate Serial/Label | |

**D0 jetzt:** bestehendes L3 + Stall scope 1 + `lab_e7_delay_ladder.py --mode B`.  
**Lab 2026-10-12:** [`lab-d0-regression/ERGEBNIS`](../betrieb/artifacts-2026-10-12-lab/lab-d0-regression/ERGEBNIS.md) — **PASS** (p50≈734 ms, undDelta=0, ~87 s live).

Resume-P: bei Mid-File-Start Identity-Rotation (`remount` ohne keepIdentity / Label-Override) — separates Go.

## Freeze

Feld-OTA nur mit Go. Default `stallEnable=false`.

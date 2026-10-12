# S7 Startup + D Fixed-Huge-File · Spezifikation · 2026-10-12

**Status:** Umsetzung gestartet in `esp32.pidrive` **0.4.49-dev** (S7-B Gate).  
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

Resume-P: bei Mid-File-Start Identity-Rotation (`remount` ohne keepIdentity / Label-Override) — separates Go.

## Freeze

Feld-OTA nur mit Go. Default `stallEnable=false`.

# Capture-Protokoll · Storm-Session (M30) · 2026-10-17/18

**Ziel:** Eine verwertbare **Storm (S)**-Episode mit simultaner Beobachtung innen+außen.  
**Nicht-Ziel:** Mehr 167/136-Statistik · UART allein · Stall · Sheet-A ohne Capture.

## Qualitätslage Abend 17.10. (Ist)

| Spur | Abend | Qualität | Lücke für M30 |
|------|-------|----------|----------------|
| Status-Snapshots | reich (`prefetchHits`, Meta-Bytes, `fromHead`/`midFile`) | gut | nur Stichproben |
| Status-Poll JSONL | `bytesFile`/reads/guess | **mittel** | **kein** `prefetchHits`, **kein** slot-`midFile` (Schema v1) |
| MessCapture | Abend **leer** | — | keine LBA/Read-Klasse im Storm |
| UART | Ordner leer | — | Panic = UNKNOWN |
| Operator-Ohr | ERGEBNIS/Notizen | ok | Tonfenster-Marker unscharf |
| Zeitkorrelation | Poll 1 Hz + Snapshots | ok für Guess-Events | ohne Capture keine LBA↔Guess-Join |

**Fazit:** Morphologie Q/S war aus Snapshots + `ΔbytesFile` beweisbar; kausale ???-Zone (welche LBA → FW-Reaktion) bleibt blind ohne MessCapture+UART.

## Pflicht-Set einer P0-Session

Gleichzeitig:

1. **Status-Poll Schema v2** (`tools/feld_status_poll.py`) — Achsen pref / midFile / Meta / Guess  
2. **MessCapture arm** vor OTG (`tools/mess_hu_capture.py arm`)  
3. **UART** (`tools/lab_uart_reset_log.py`) — Resetgrund + Panic-Tail  
4. **Operator-Marker** (Uhr + Aktion) in `OPERATOR.md`  
5. Optional parallel: `feld_trace_poll.py` ≥3 Hz (LBA-Ring, join auf ESP-ms)

## Korrelationsachsen

```text
wall_iso (Poll)
    ↔ mess.cmds[].t / seq / lba / blocks / op
    ↔ uart wall + uptimeMs rollback
    ↔ guess Δ (Poll)
    ↔ prefetchHits / midFile / bytesFile Δ
    ↔ resetReason / plugCount
```

**Erfolg:** Für mind. eine **S**-Episode beantwortbar: *welche LBAs/UID/Klasse liest die NBT, und was macht die FW unmittelbar danach (Guess? Reject? Stream? Reset?)*

## Operator-Ablauf (kurz)

```text
T-5   UART starten · OUT-Dir anlegen · MessCapture arm
T0    OTG stecken (Klasse A wenn möglich)
T0+20 s warten (Guess-Latenz) — kein Replug-Sturm
      wenn Ton: Fenster notieren, DANN pausieren / beobachten
      wenn S (pref↑ mid↑ bytesFile↑): Capture laufen lassen ≥60–120 s
      kein Sofort-Reset während S
T+…   optional Reset-Isolation (M34) erst NACH Dump
Ende  mess dump · poll stop · uart stop · qs-classify · status-Snapshot
```

## Schwellen (Orientierung, Audit)

| Label | Hinweis |
|-------|---------|
| **Q** | pref≲20, midFile niedrig, ΔbytesFile ≈0, guess oft 0 |
| **S** | pref≳200 **oder** ΣmidFile≳400 **oder** ΔbytesFile ≳80 KiB/s |
| **Normal** | Guess + Stream + Ohr, File-Body zielgerichtet |
| **nie** | Alarm nur auf reads/rej (Invariante 31/32 = Quiet-Plateau) |

Klassifikator: `python3 tools/feld_qs_classify.py --poll <jsonl>`

## Lab-Prep (ohne NBT)

Auf `.88` (mess-fw): Soft-USB-Cycle + Poll v2 + MessCapture **`--storm`** (Timeout-only) + M31/M32.

```bash
bash tools/feld_storm_session.sh --esp http://192.168.178.88 \
  --out docs/betrieb/artifacts-2026-10-18-lab/lab-storm-capture-prep/session-storm-m32 \
  --sit usb_cycle --seconds 30 --mark lab_storm_m32
# → poll.jsonl (schema 2) · arm.json · mess-cmds.json · qs.json · band.json · SUMMARY.json
```

**Wichtig:** normales `arm` stoppt bei `play_cleared` (~1 s) — für Storm-Fenster immer `--storm`.

## Feld-Startkommando (Paket)

```bash
OUT=docs/betrieb/artifacts-2026-10-18-feld/feld-storm-m30-01
bash tools/feld_storm_session.sh --esp http://192.168.178.89 --out "$OUT" \
  --sit none --seconds 120 --uart /dev/ttyACM0
# Operator: nach ARMED OTG stecken; Script hält Capture bis Timeout
```

## Artefakt-Checkliste (Session-Ende)

- [ ] `poll.jsonl` schema_version=2, pref+midFile befüllt  
- [ ] `mess-cmds.json` / `arm.json` mit READ10 während S  
- [ ] `uart/` status+log (oder begründet fehlend)  
- [ ] `qs.json` Label S-Episode ≥1  
- [ ] `status-end.json` Meta-Bytes vs Start  
- [ ] `OPERATOR.md` mit Uhrzeiten  
- [ ] Guess-Events im Poll markiert (Δguess)

## Nicht tun

Replug-Sturm nach Ton · Capture erst nach Reset · nur Snapshots ohne Poll · 167/136 als Stuck-Beweis · Stall in derselben Session

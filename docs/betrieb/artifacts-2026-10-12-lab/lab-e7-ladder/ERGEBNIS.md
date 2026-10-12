# Lab E7 Ladder · Ergebnis 2026-10-12

**ESP:** `.88` · FW **`0.4.48-dev`** (nach Fix) · Host `/dev/sg0` (PIDRIVE) · Producer 6000 B/s  
**Freeze:** Feld `.89` nicht angefasst. Nach Tests `stallEnable=false`.

## Kurzurteil

| Stufe | Ergebnis | Kernzahl |
|-------|----------|----------|
| **L0** stall aus | **PASS** | Live ~8,3 s → Stille; `undDelta≈471k`; `sg p50=5 ms` |
| **E7-B L1** maxMs=1000 chunk=4096 | **PASS (PC)** | `sg p50=735 ms` ≈683; `undDelta=0`; Live ~86,9 s; Rate 6,6 kB/s; **kein Host-Abort** |
| **L3** maxMs=300 | **PASS** | `timeouts=115`; `waitMsMax=301`; danach Stille wie L0 |
| **L4** cmd-timeout=500 | **PASS (ESP stabil)** | SG `ENODEV` nach Host-Abort; ESP Uptime/Heap ok; USB erst nach `/api/restart` wieder am Host |
| **L2** chunk=512 | **TEIL** | `partials=457`; ~111× LIVE @~735 ms, dann Silence/`timeouts`; REPORT fehlte (HTTP-Timeout unter MSC-Last) |
| Config-Leiter A | **PASS** | `stallMaxMs` 100…11000 setzbar |

**PC akzeptiert Busy-Retry ≥ ~800 ms/4 KiB.** Hybrid B′ (`vTaskDelay`+`return 0`) hält Producer am Leben (`producer_err=null`, ~0,5 MB geliefert). **NBT weiter UNKNOWN.**

## Firmware-Fix 0.4.48

Busy-Retry ruft `onRead` mit gleichem `(lba,offset)` erneut auf. In 0.4.47 setzte `if (offset == 0)` jedes Mal `stallCmdT0_` zurück → **`stallMaxMs` griff nie**, `cmds`/`retries` explodierten.

Fix: Timer/`cmds++` nur bei **keyChanged** (neuer LBA/Offset), nicht bei Busy-Reentry.

SHA256: `ad17086530fac0c90f833269641dd23849840a7783cee5c62483c0dff195ac2a`  
`esp32.pidrive/dist/pidrive.0.4.48-dev.ota.esp32s3.bin`

## Detail

### L0 Baseline (`l0-baseline/`)

- `pass=true`, `live_s_at_bps=8.32`, `SILENCE=115`, `rate_kBps=622`

### E7-B L1 (`e7b/` auf 0.4.47 + `e7b-l1-v048/` auf 0.4.48)

Beide Läufe paced; 0.4.48 mit korrekter Telemetrie:

- `waitMsMax=829`, `waitHist` mit Bucket 500–1000 ms  
- `class_counts`: ID3=1, LIVE=127, **kein SILENCE**  
- `seq_gaps` klein (4) — Spec wollte 0; nicht blockierend für PC-Gate

### L3 (`e7b-l3-max300/`)

- Beweis: Silence-Fallback nach `maxMs` funktioniert post-Fix

### L4 (`e7a-l4-host500/`)

- Linux SG-Timeout 500 ms < benötigte ~700 ms → Device verschwindet (`Errno 19`)  
- ESP rebootet nicht von selbst; Remount allein reichte nicht → **`/api/restart`** stellte USB wieder her

### L2 (`e7b-l2-chunk512/`)

- Device: `partials>0` belegt Teilantworten  
- Host-Reads bleiben 4 KiB-Kommandos; Dauer ~Producer-Takt bis gegen Slot-Ende Timeouts  
- Sim-REPORT: HTTP Status-Snap Timeout — Tool/WiFi unter Partial-Last härten

### Tool

`lab_e7_delay_ladder.py`: liest jetzt `REPORT.json` und nested `results.REPLUG`.

## Nächste Schritte

1. **NBT E7** (C) — gleiche L1-Idee, erst nach Q11/Go  
2. L2 wiederholen wenn USB/WiFi ruhig (oder Status-Snap robuster)  
3. Optional: `botResets`-Telemetrie verdrahten (L4-Signal)  
4. Stall-Feld weiter Freeze

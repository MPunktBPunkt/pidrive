# Lab: Bulk-`drainTcp` (0.4.46-dev) · Idle + Hold-Retest

**Datum:** 2026-10-06 · **Lab .88** · **FW:** `0.4.45-dev` → **`0.4.46-dev`** (nur Lab-OTA)  
**Änderung:** `PumpServer::drainTcp` liest TCP in 512‑B-Blöcken statt Byte-für-Byte.

---

## Ergebnis

| Test | Vorher (0.4.45) | Nachher (0.4.46 bulk) |
|------|----------------:|----------------------:|
| Idle abs_bps (512/gap200µs) | ~73 847 | **~840 078** (~11×) |
| Idle gap0 / batch8 | ~70 k | **~797–838 k** |
| Burst-then-Slow + Hold | und=0, behind≠0 | **PASS** und=0 behind=0 in_window |
| maxpump-hold 248 KiB @~275 KB/s | und≈195 KiB | **PASS** und=0 behind=0 live=253952 · pump_obs≈268 KB/s |

**Claude-Hypothese bestätigt:** Byte-`read()`-Schleife war der Ceiling-Engpass. Ziel ≥300 KB/s ist erreicht (Leerlauf ~840 KB/s).

**Hold:** Bei schnellem Pump reicht Status-Poll nicht — lokale `absEnd`-Schätzung zwischen Polls nötig (`bts-localhold` / `maxpump-hold-bulk`).

---

## Artefakte

- Idle: `lab88-pump-idle-bulk-*`, `pump-idle-bulk-summary.jsonl`
- PASS: `lab88-async-071910-bts-localhold`, `lab88-async-071943-maxpump-hold-bulk`
- FW: `esp32.pidrive` dist `pidrive.0.4.46-dev.ota.esp32s3.bin` · env `pidrive-s3-l3`

**Feld:** noch `0.4.45-dev` — Flash erst nach Abstimmung. Freeze für Feld hält.

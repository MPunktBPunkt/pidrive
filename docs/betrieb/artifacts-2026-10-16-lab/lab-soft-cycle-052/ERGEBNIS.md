# Lab Soft-Cycle · 0.4.52-dev · 2026-10-16

**ESP:** `.88` · **FW:** `pidrive-s3-mess` `0.4.52-dev` · **stall:** false  
**Bin:** `esp32.pidrive/dist/pidrive.0.4.52-dev.ota.esp32s3.bin`  
**Host-Tools:** `tools/soft_cycle_orchestrator.py`

## Kurzfassung

| Gate | Status |
|------|--------|
| Build `pidrive-s3-mess` | ☑ |
| OTA `.88` → 0.4.52-dev | ☑ |
| Orchestrator Dry-run | ☑ PASS |
| Soft-USB Zelle | ☑ PASS (nach Soft-USB-Identity-Fix) |
| **Vollmatrix 5 Zellen** | ☑ **PASS** `matrix-full-03` |

**Capture-Modus Lab:** `ram_local` + `--no-live-audio` (kein Pump).  
`ram_wifi_off` ist mit Soft-USB/Stop unverträglich (409).

## Fixes in diesem Durchgang

### 1. Soft-USB behält Identity (esp32.pidrive)

Soft D+ Cycle lief über `onUsbPlugged(false)` → `applyUsbIdentity()` → Serial-Sprung → Soft-usb-Zelle `identity-drift`.

**Fix:** `armSoftUsbKeepIdentity()` vor Soft-Detach; physisches Unplug bumpet weiter.

### 2. Quiet-Gate akzeptiert Lab-Reindex (pidrive)

Nach Soft-USB/Remount bleibt der Lab-Host oft in `phase=play|scan` ohne Stream → nächste Zelle `not-quiet`.

**Fix:** `quiet_gate` erlaubt `play`/`scan`, solange `stream.active=false`.

## Matrix-Ergebnis (`matrix-full-03`)

| Zelle | valid | Isolation | Outcome | Capture cmds |
|-------|-------|-----------|---------|--------------|
| soft-usb | ☑ | keine Änderung | E (indeterminate) | 47 |
| media-hide | ☑ | keine | C | 2 |
| serial | ☑ | serial+rev | C | 2 |
| label | ☑ | bpb+root label | C | 2 |
| volume-id | ☑ | bpbVolumeId | C | 2 |

Panic-Gate durchgängig ok (kein Uptime-Rollback) — Soft-Cycle umgeht den Feld-Panic bei physischem OTG.

## Frühere Läufe

| Ordner | Ergebnis |
|--------|----------|
| `matrix-soft-usb-01` | FAIL wifi_off 409 |
| `matrix-soft-usb-ramlocal-01` | FAIL identity-drift (vor FW-Fix) |
| `matrix-soft-usb-ramlocal-02` | PASS soft-usb allein |
| `matrix-full-01` / `02` | not-quiet (vor Quiet-Fix) |
| `matrix-full-03` | **PASS** |

## Soft-USB Kurz-Kampagne

`overnight-soft-usb/`: **10/10 PASS** — danach **stopp** (Prioritäts-Shift).

## Nächste Schritte

→ **P0 Modelltest:** **erledigt** — siehe Feld  
[`../../artifacts-2026-10-16-feld/feld-512kib-predict-01/ERGEBNIS.md`](../../artifacts-2026-10-16-feld/feld-512kib-predict-01/ERGEBNIS.md)  
(`4×240+2×32`, nicht `8+4×240+56`).  
→ **Neues P0:** Panic bei physischem OTG · siehe [`PRIORITAET-SHIFT.md`](PRIORITAET-SHIFT.md) und  
[`../../artifacts-2026-10-16-feld/UEBERGABE-TAG-2026-10-16.md`](../../artifacts-2026-10-16-feld/UEBERGABE-TAG-2026-10-16.md).  
→ Soft-Cycle/Orchestrator nicht weiter ausbauen. Matrix A7/[S] gepflegt; Facts-Spiegel erst nach Review.

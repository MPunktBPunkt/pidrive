# Lab-Maßnahmen nach Übergabe · 2026-10-16 (Abend)

**ESP:** `.88` · **FW:** `0.4.52-dev` mess (bereits on-device) · **stall:** false  
**Auslöser:** [`../../artifacts-2026-10-16-feld/UEBERGABE-NAECHSTE-KI-2026-10-16.md`](../../artifacts-2026-10-16-feld/UEBERGABE-NAECHSTE-KI-2026-10-16.md) B2/B3

## Umgesetzt

| ID | Maßnahme | Status |
|----|----------|--------|
| **B3** | Soft-USB Identity-Fix (`armSoftUsbKeepIdentity`) in **esp32.pidrive** | ☑ gepusht `0ec4b89` |
| **B2** | `mess_hu_capture.py arm` — Capture vor Aktion + Auto-Stop | ☑ |
| Lab | Soft-USB Identity smoke | ☑ Serial `PD0483` unverändert über soft cycle |
| Lab | Soft-Cycle Zelle `soft-usb` | ☑ PASS ×2 (`soft-usb-01`, `soft-usb-02`) |
| Lab | `arm --usb-cycle-ms 600` | ☑ Capture scharf vor Cycle; 50 CMDs; Stop `timeout` (Lab ohne Underrun-Spike) |
| Offline | `decide_arm_stop` Self-Test (play_cleared / underrun / host_stuck) | ☑ |

## Nicht umgesetzt (bewusst)

| ID | Grund |
|----|-------|
| B1 Panic/OTG | braucht NBT/physischen Replug — nicht Lab-D+ |
| B5 Stall-Leiter | nach B1 |
| 128 kbit/s | nach stabiler Klasse A |
| F0 / Größenleiter | nach B1 |

## Artefakte

| Pfad | Inhalt |
|------|--------|
| `arm-usb-cycle.json` | Arm+Soft-Cycle Capture |
| `soft-usb-01/` · `soft-usb-02/` | Orchestrator PASS, Identity A=B `PD0483` |
| esp32.pidrive `0ec4b89` | Soft-USB keepIdentity |

## Nutzung Feld (nächster Termin)

```bash
# Capture VOR Tip/OTG scharf; Auto-Stop bei play clear / Underrun / Host-Stuck
python3 tools/mess_hu_capture.py --esp http://192.168.178.89 arm \
  --timeout 60 --mark feld_ton \
  -o docs/betrieb/artifacts-…/arm-feld.json
# Operator: tippen / OTG — Tool stoppt selbst und dumpt CMDs
```

## Ampel

Lab Soft-USB + Capture-Arm: 🟢 · Panic-P0: 🔴 unverändert (Feld)

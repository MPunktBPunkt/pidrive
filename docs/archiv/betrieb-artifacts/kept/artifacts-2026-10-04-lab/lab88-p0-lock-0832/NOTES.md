# P0 MSC-Session-Lock — Lab-Provokation 2026-10-04

**Verdict:** PASS  
**Code:** `esp32.pidrive/tools/pump_bridge.py` (`MscSessionLock`, `--msc-lock` default on)  
**Tool:** `pidrive/tools/m3_lab_p0_menu_lock_provocation.py`

## Ablauf (D)

1. Bridge TCP → `.88`, `--no-audio --msc-lock`
2. Root-Presets gesiegelt: Rock Antenne / Bayern / BOB / Menue
3. `/tmp/pidrive_menu.json` auf Zurueck/Ausgang/Auto umgeschrieben (Pi-UI-Provokation)
4. ESP `/api/menu` unverändert; Bridge loggte `frozen_reject`

## Offen

- Deploy auf Bridge-Pi `.105` (`systemctl restart pidrive_pump_bridge`)
- Feld-Provokation am BMW (UI-Wechsel während USB-Session)

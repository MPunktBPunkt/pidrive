# P0 Deploy Bridge-Pi `.105` — 2026-10-04

**Host:** `pidrive@192.168.178.105`  
**Binary:** `/home/pidrive/pump_bridge.py` (from `esp32.pidrive` `79fc96a`+connect-retry)  
**Backup:** `pump_bridge.py.bak-pre-p0-202610040834`

## Verifikation (D)

Lab-Provokation auf dem Pi gegen ESP `.88`: **PASS** (`report.json`).  
Siegel: Rock Antenne / Bayern / BOB / Menue — Zurueck-UI abgelehnt (`frozen_reject`).

## Betrieb

- `systemctl enable --now pidrive_pump_bridge` → Ziel `192.168.178.89` (Auto)
- Connect-Retry bei offline `.89` (kein Exit-Code-1-Loop mehr)
- Cron Backup: `@reboot` + `*/2` → `ensure_pump_bridge.sh`

## Offen

Feld-Provokation am BMW (Pi-UI-Wechsel während USB-Session).

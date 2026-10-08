# Lab nach s4 · 2026-10-08 ~17:41

Bezug Feld: [`../../artifacts-2026-10-08-feld/GESAMTBERICHT-FELD-S4-TONFENSTER-2026-10-08.md`](../../artifacts-2026-10-08-feld/GESAMTBERICHT-FELD-S4-TONFENSTER-2026-10-08.md)

## L4 — Reboot-Stress (angepasst)

| Punkt | Ergebnis |
|-------|----------|
| `sysfs …/authorized` | **Read-only** auf diesem Host → kein VBUS/authorized-Zyklus |
| Ersatz | `nbt_hu_sim --golden REPLUG` ×10 (`l4d-*`), Sim besitzt Pump |
| ESP-Uptime-Drops | **0** (1h 47 min → 1h 51 min, Serial `PD0262` konstant) |
| REPLUG PASS/FAIL | 2 PASS / 8 FAIL (oft `ring_full_pre=False` ohne Dauer-Bridge) |
| Live-s (Beispiel PASS/Messung) | ~8,1 s wie Lab L2 / Feld Live-Window |

**Deutung:** Software-Host-Replug (SG) rebootet den Lab-ESP **nicht**. Feld-Steck-Resets (s4: ~24 Drops) → **Versorgung priorisieren** (Q11), nicht MSC-Stack-Panic.

## Offene Lab-Punkte

- Authorized/VBUS-Zyklen auf Host mit schreibbarem sysfs oder `uhubctl`
- UART-Reset-Grund bei echtem Brownout (DTR/RTS aus)
- P ohne Dateiname (Größe/Pfad) — Spec bis FW-Go

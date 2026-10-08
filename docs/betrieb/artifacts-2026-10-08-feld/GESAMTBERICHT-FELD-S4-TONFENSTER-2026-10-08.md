# Gesamtbericht Feld s4 — Tonfenster · 2026-10-08

**Ein Satz:** Ringfenster im Auto = Lab (**~8,2 s** instrumentiert); Ohr oft ~5 s; Bild+Ton für BOB und Antenne; Steck-Reboots und Resume-P dominieren die Ausfälle.

**Detail:** [`feld-s4-prep/s4-20261008-165212/ERGEBNIS-S4.md`](feld-s4-prep/s4-20261008-165212/ERGEBNIS-S4.md)  
**Lab-Gate:** [`../artifacts-2026-10-08-lab/lab-abend-1556/ERGEBNIS-LAB-ABEND.md`](../artifacts-2026-10-08-lab/lab-abend-1556/ERGEBNIS-LAB-ABEND.md)

## Ergebnis vs. Auftrag

| Frage | Antwort |
|-------|---------|
| Hörbares Fenster vs. Lab 8,2 s | Instrument **8,26 s** (BOB); Ohr ~5 s → Verlust im HU-Pfad |
| R28 (nicht nur BOB) | **ja** — Rock Antenne Bild+Ton (17:18, 17:24) |
| P-Schlüssel = Dateiname? | **nein allein** — Rename/Cache-Bust, HU weiter Mid-File |
| Reboot-Rate Stecken | **hoch** (~24 Uptime-Drops, 38 Serials) — Versorgung |

## Lab-Nachlauf (gleicher Abend)

[`../artifacts-2026-10-08-lab/lab-abend-nach-s4-1741/ERGEBNIS-LAB-NACH-S4.md`](../artifacts-2026-10-08-lab/lab-abend-nach-s4-1741/ERGEBNIS-LAB-NACH-S4.md): REPLUG×10 → **0 ESP-Uptime-Drops**. Software-Host-Pfad unwahrscheinlich als Feld-Reset-Ursache → Versorgung.

## Nächste Schritte

1. Feld: Netzteil-A/B / VBUS-Blocker (O3/O4), weniger Stecken.
2. P ohne Name: Größe/Pfad (FW-Go).
3. Lab: authorized/VBUS wo sysfs schreibbar + UART-Reset-Grund.

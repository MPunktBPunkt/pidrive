# Übergabe · 2026-10-17 (nach Lab-Nacht `6043a22`)

**Kanone:** [`MASSNAHMEN-NACH-6043a22.md`](MASSNAHMEN-NACH-6043a22.md) · [`METHODIK-MSC-WAHRHEIT.md`](METHODIK-MSC-WAHRHEIT.md) · Matrix Stand 17.10.

## Ein Satz

MSC-Phasen und Messmethode sind reif für **Lab-Stall als Instrument**; Feld-P0 bleibt **OTG-Panic**. Keine weiteren 512‑KiB-Wiederholungen.

## Sofort (Lab, ohne Fahrzeug)

1. `tools/lab_q10_calibrate.py` → Artefakt `q10-calib-*`
2. `tools/lab_stall_phase_ladder.py` Smoke dann Full (0…15 s, Menü/ID3/Audio)
3. QD=1 aus Audio-Phase-Capture ablesen

## Feld erst nach Panic-Diagnose

UART / resetReason / VBUS A/B — sonst HU-Reaktion ⊕ ESP-Fehler vermischt.

## Nicht tun

512‑KiB wiederholen · 64er-Lab als HU · Ring blind · Soft-Cycle mit Stall · `dd` als MSC-Wahrheit · Overnight-Loop-Ordner als Langzeit lesen (`SMOKE.md`).

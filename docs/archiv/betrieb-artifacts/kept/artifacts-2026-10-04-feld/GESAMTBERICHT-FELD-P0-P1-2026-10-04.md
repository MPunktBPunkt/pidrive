# Gesamtbericht Feld: P0 PASS, P1/AV offen — 2026-10-04

**Normativ kurz:** [`FELD-ERGEBNIS-2026-10-04.md`](FELD-ERGEBNIS-2026-10-04.md) · Index: [`../MSC-AKTUELL.md`](../MSC-AKTUELL.md)

## Fazit

P0 (MSC-Session-Lock in `pump_bridge`) ist **feld-PASS**. P1 (kalter Auto-Next ±1,5 s) ist **heute nicht entscheidbar**: die HU spielt überwiegend aus dem Scan-Cache ohne Head-Read. Einmal greifen Play-Detect und Bridge-ffmpeg (PD0058) — trotzdem **kein Ton/kein Cover** (`bufferMs=0`). Das verschiebt die kritische Arbeit von „noch ein Autoplay“ auf **AV-Buffer/MSC-Fill** und **Cache/Detect**, nicht auf Menü-Lock.

## Was feststeht

- Lock siegelt Favoriten und blockiert Pi-UI-Overwrite (`frozen_reject`).  
- Falsches Erstsiegel, wenn USB schon steckt und Pi im Audio-Menü ist → Unplug + Root vor Reseal.  
- LED ≠ Ton: große Reads blinken auch ohne `play_uid`.  
- `audio_start` + `audio_ack ok` ≠ hörbarer USB-Pfad.

## Entscheidung gegen Plan Rev.5

```
P0 Feld PASS ✓
P1×2 → NICHT GRÜN (nicht messbar / AV fail)
→ kein Sequenz-GO; Freeze halten; nächster Engpass = AV + Detect/Cache
```

BT-Hybrid bleibt Fallback, aber erst nach Lab-Klärung von `bufferMs=0`, sonst doppelt blind.

## Nächste Arbeitspakete

1. Lab-Repro: Detect → ffmpeg → `bufferMs` > 0 → Host liest wachsende Datei.  
2. Optional Detect-Lockerung nur mit AV-Beweis.  
3. Feld-P1 erst nach einmal Ton an HU.  
4. Q3a Oracle weiter optional parallel.

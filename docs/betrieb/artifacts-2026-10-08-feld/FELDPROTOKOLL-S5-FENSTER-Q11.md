# Feldprotokoll s5 · Längeres Fenster + Q11 · 2026-10-08

**Ein Satz:** Lab hat 32k≈12,5 s / 24k≈16,8 s und K3-FAT bewiesen; im Auto jetzt Q11 (Reset) und Ohr @32k unter Klasse A.

## Vorbedingungen

- FW `0.4.46-dev` Freeze  
- Prep: `feld-s5-prep/` (`run-s5.sh` Default **32k / 4000 B/s / marker 1 s / msc-lock**)  
- UART-Adapter bereit, **kein** DTR/RTS-Toggle beim Öffnen  

## Kern (~20–25 min)

1. **Q11** — UART loggen → 1× OTG → `rst:` / brownout / panic markieren.  
2. **O2** — nur Klasse-A-Replug: BOB tippen, Hördauer + Zähltöne vs. Instrument.  
3. **K2** — Bayern einmal Klasse A.  
4. **K3** — Rename bei OTG ab (Lab: Name erscheint als `….mp3` auf FAT).  
5. Reboots zählen; wenig stecken.

## Nicht in s5

- Stall / OTA  
- P-Größe (braucht FW/Slot-API)  
- Host-USB-Sniffer Pflicht (Lab-Q10 = 4 KiB Kandidat)

## Auswertung

```bash
python3 tools/feld_live_window.py --run <RUN>
# 32k: Hör-/Live-Sekunden ≈ live_bytes / 4000
```

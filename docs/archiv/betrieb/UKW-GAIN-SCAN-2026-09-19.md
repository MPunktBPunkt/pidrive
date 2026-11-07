# UKW-Band Scan 87.5–108.0 MHz — Gain-Vergleich

**Datum:** 2026-09-19  
**Host:** Pi `192.168.178.105` · Stick R820T · PPM 49  
**API:** `mode=range` · samples 65k · avg×4 · SR auto (~2.048 MHz, 12 Fenster)

## Kurzfazit

Bei **hohem Gain** sind die vielen „Träger“ **größtenteils keine Radiosender**, sondern:

1. **Peak-Detektor-Füllung** — max. 20 Peaks; bei hohem Gain/Übersteuerung steigt der Rauschboden, schwache Spitzen und Spurs schaffen die Schwelle und füllen die Liste.
2. **Fenster-/DC-Spurs** — wiederkehrende Peaks nahe Fenstermitten und Bandkanten (z. B. ~88.7, ~100.0, ~108.0).
3. **Intermodulation / ADC-Clipping** — bei Gain 40+ breitere Scheinlinien, weniger klare Hierarchie.

**Beste Detektion echter UKW-Sender:** Gain **~20–30 dB**, enger Zoom (±0,5 MHz), Avg ≥4, nicht den ganzen Band-Sweep als Senderliste lesen. Referenzen 95.8 / 103.0 / 104.4 waren in früheren **Zoom**-Messungen sauber; im **Vollband**-Top-20 tauchten sie hier nicht auf (von Spurs/stärkeren Peaks verdrängt).

## Messwerte (Vollband)

| Gain | Dauer | Fenster | nPeaks | „strong“ (≤12 dB unter Top) | top_db | Bemerkung |
|------|-------|---------|--------|-----------------------------|--------|-----------|
| −1 Auto | 50.6 s | 12/12 | 20 | 10 | 79.8 | AGC laut; Top bei 88.7 / 100.0 / 96.0 — typische Spur-/Kantenlage |
| 20 | 52.8 s | 12/12 | 20 | 20 | 49.1 | Alle 20 „strong“ → flache Liste, wenig Dynamik im Detektor |
| 30 | 53.0 s | 12/12 | 20 | 18 | 58.9 | Etwas mehr Spreizung; Top weiter ~100.0 / 96.0 |
| 40 | 105.7 s | 10/12 | 20 | 7 | 68.7 | 2 Fenster fehlgeschlagen; stärkere Spurs, Scan langsamer/instabiler |
| 48 | — | — | — | — | — | Lauf abgebrochen (Timeout/Fehler nach Gain 40) |

### Top-Peaks (Auszug)

**Gain −1:** 88.699 (79.8), 100.004 (76.9), 95.999 (73.5), 107.999 (71.1), 100.805 (70.0) …  
**Gain 20:** 100.005 (49.1), 95.467, 97.207, 88.504, 91.985, 105.912 … (viele ~47 dB)  
**Gain 30:** 100.005 (58.9), 96.0 (57.5), 100.805 (51.9), 108.0 (50.2) …  
**Gain 40:** 100.005 (68.7), 96.0 (67.3), 100.805 (61.7), 101.871 (60.1) …

Bekannte Allgäu-Referenzen **95.8 / 103.0 / 104.4:** im Vollband-Top-20 **nicht** als nächster Peak getroffen (tol 80 kHz) — Zoom-Pfad bleibt der richtige Nachweis.

## Empfehlung Praxis

| Ziel | Einstellung |
|------|-------------|
| Sender suchen | Gain **20–30**, Range ±0,5…1 MHz um Verdacht, Avg 4–8 |
| Band-Übersicht | Gain **20–30**, Vollband nur als grobe Karte; Peaks skeptisch lesen |
| Vermeiden | Gain **40–50** für Peak-Listen — Spur-/IM-Schwarm |
| Feinere Frequenz | SR senken (z. B. 1.024 / 0.25 MHz), nicht Samples >65k |

## Artefakt-Checkliste

- Peak wiederholt sich an **vielen Gain-Stufen an derselben krummen Frequenz** → eher Spur/Fenster.
- Peak nur bei **hohem Gain**, verschwindet bei 20 → eher Rauschen/IM.
- Peak stabil bei 20–30 **und** im Zoom mit Sub-Bin-Interpolation → eher echter Träger.
- Bandkante / exakte .000-MHz → oft **DC/Fensterartefakt**.

## Rohdaten

Terminal-Log der Messung: Cursor-Session 2026-09-19 (Gain −1…40 vollständig).  
Skript: `tools/spectrum_ukw_gain_scan.py`

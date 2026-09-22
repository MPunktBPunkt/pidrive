# Antennen-Vergleich 2026-09-22

Spektrum-Messungen (RTL-SDR über PiDrive `/api/spectrum/capture`) im Dachboden.
Ziel: aktive AliExpress-DVB-T-Antenne (A) gegen die bisherige Antenne (B, folgt).

| | |
|---|---|
| Datum | 2026-09-22 |
| Position | Dachboden |
| PPM | 49 |
| Empfänger | RTL-SDR (PiDrive) |
| TX | PMR446 Ch8 nur während Stützpunkt-Messung (Nahfeld) |

Rohdaten: `antenna-a-*.json` in diesem Ordner.
Stützpunkte: `antenna-a-anchors.json` (+ `antenna-a-anchor-*.json`).

---

## Antenne A — AliExpress DVB-T AT-01 (aktiv)

**Marketing-Claim (AliExpress, mit Vorsicht):** VHF 172–240 MHz / UHF 470–860 MHz,
„200 Meilen“, LNA „25 dBi“, USB 5 V (~20 mA), F-Male, ~4,5 m Kabel, Impedanz 75 Ω.

**Realistisch:** Integrierter USB-LNA (5 V) ist aktiv. Claim-Band deckt DAB Band III und
DVB-T UHF ab; UKW (87,5–108), Airband (118–137) und PMR446 liegen **außerhalb** der
angegebenen Spec — Empfang dort ist trotzdem möglich (LNA breitbandig + Kabelantenne),
aber keine Garantie und kein Beleg für „200 Meilen“.

### Messparameter

| Band | Bereich (MHz) | Gain | Datei |
|------|---------------|------|-------|
| UKW | 87,5–108 | 25 | `antenna-a-ukw.json` |
| Airband | 118–137 | 36 | `antenna-a-airband.json` |
| DAB Band III | 174–230 | 30 | `antenna-a-dab_b3.json` |
| PMR446 | 446,0–446,2 | 36 | `antenna-a-pmr446.json` |
| UHF-TV-Stichprobe | 474–490 | 30 | `antenna-a-uhf_tv_sample.json` (Peaks) |

### UKW — Zielsender (SNR)

| Sender | Peak (dB) | SNR (dB) |
|--------|-----------|----------|
| FM 90,2 | 47,8 | 14,9 |
| FM 90,7 | 73,2 | 42,6 |
| FM 95,8 | 67,1 | 41,1 |
| FM 98,5 | 46,3 | 19,3 |
| FM 103,0 | 64,6 | 34,0 |
| FM 104,4 | 73,5 | **48,3** |

Top-Peaks gesamt: 101,0 MHz (81,2 dB), 88,7 (73,6), 104,4 (73,5).

### Airband EDJA — Presets K1–K6 (SNR)

| Preset | Peak (dB) | SNR (dB) | Hinweis |
|--------|-----------|----------|---------|
| K1 Emergency | 33,3 | 2,4 | idle / Rauschen |
| K2 ATIS | 71,7 | **42,3** | stark (Dauerträger) |
| K3 Ground | 39,1 | 8,8 | schwach / idle |
| K4 Tower | 33,2 | 6,4 | idle |
| K5 AFIS | 32,1 | 4,7 | idle |
| K6 Radar | 47,2 | **22,4** | hörbar bei Verkehr |

Top-Peaks: 120,0 MHz (77,3 dB), 122,92 (72,2), 118,85 ATIS (71,8).

### DAB Band III — Energie (kein Ensemble-Decode)

| Peak (MHz) | dB |
|------------|-----|
| 208,33 | 74,6 |
| 201,61 | 65,5 |
| 226,19 | 61,1 |
| 216,01 | 60,8 |
| 187,21 | 60,0 |

Claim-Band VHF 172–240: Energie vorhanden (LNA+Antenne wirkt in Band III).

### PMR446 (kein Senden)

| Kanal | Peak (dB) | SNR (dB) |
|-------|-----------|----------|
| PMR K1 | 29,0 | 6,8 |
| PMR K8 | 28,7 | 7,0 |

Scan-Top: 446,100 (47,3 dB) — wahrscheinlich Fenster-/FFT-Zentrum-Artefakt; Idle-SNR ~7 dB, kein Verkehr während der Messung.

### UHF TV Stichprobe (Claim-Band 470–860)

| Peak (MHz) | dB |
|------------|-----|
| 480,02 | 50,3 |
| 478,49 | 41,3 |
| 476,74 | 41,3 |

Nur 474–490 MHz gesampelt (voller 470–860-Scan hing zuvor).

### Stützstellen (enge Fenster, Vergleichsbasis für B)

| Stützpunkt | MHz | Gain | Peak (dB) | SNR (dB) | Hinweis |
|------------|-----|------|-----------|----------|---------|
| FM 90,7 | 90,700 | 25 | 64,8 | **35,4** | Margin +22,9 dB |
| FM 95,8 | 95,800 | 25 | 65,8 | **37,6** | Margin +22,4 dB |
| FM 103,0 | 103,000 | 25 | 61,2 | **29,1** | |
| FM 104,4 | 104,400 | 25 | 69,9 | **43,4** | stärkster UKW-Stützpunkt |
| K2 ATIS | 118,855 | 36 | 70,6 | **40,7** | Dauerträger |
| DAB 10A Rockantenne | 209,936 | 30 | 55,9 | **17,7** | OFDM ~1,5 MHz; FFT-Energie |
| DAB 11D Bayern 3 | 222,064 | 30 | 54,1 | **17,5** | OFDM ~1,5 MHz; FFT-Energie |
| PMR446 Ch8 (TX) | 446,09375 | 36 | — | **rel. 61,1** | `watch_channels`: primary=8, power 43,3 dB, confidence 1,0 |

PMR: maßgeblich ist `relative_db` aus dem PMR-Watcher (Nahfeld-TX; Peek-SNR übersteuert).
DAB: kein Ensemble-Decode, nur Kanalenergie um 10A/11D.

### Kurzfazit Antenne A

- **UKW-Stützpunkte:** 29–43 dB SNR, klar detektiert.
- **ATIS 118,855:** ~41 dB SNR.
- **DAB 10A/11D:** ~18 dB über Out-of-Band-Floor (Claim-Band).
- **PMR Ch8 bei TX:** sicher erkannt (primary 8, relative ~61 dB).

---

## Antenne B — bisherige Antenne (folgt)

Gleiche Stützpunkte, Gains, PPM, Position. PMR erneut mit TX auf Ch8.

| Stützpunkt | Status |
|------------|--------|
| FM 90,7 / 95,8 / 103,0 / 104,4 | ausstehend |
| K2 ATIS 118,855 | ausstehend |
| DAB 10A / 11D | ausstehend |
| PMR446 Ch8 TX | ausstehend |

---

## Vergleichstabelle Stützpunkte (A vs. B)

| Ziel | A Peak | A SNR / rel | B Peak | B SNR / rel | Δ |
|------|--------|-------------|--------|-------------|---|
| FM 90,7 | 64,8 | 35,4 | — | — | — |
| FM 95,8 | 65,8 | 37,6 | — | — | — |
| FM 103,0 | 61,2 | 29,1 | — | — | — |
| FM 104,4 | 69,9 | 43,4 | — | — | — |
| K2 ATIS | 70,6 | 40,7 | — | — | — |
| DAB 10A | 55,9 | 17,7 | — | — | — |
| DAB 11D | 54,1 | 17,5 | — | — | — |
| PMR Ch8 TX | 43,3 pwr | **61,1 rel** | — | — | — |

Nach Messung B: Δ = B − A (SNR bzw. `relative_db`).

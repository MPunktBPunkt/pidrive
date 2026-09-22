# Antennen-Vergleich 2026-09-22

Spektrum-Messungen (RTL-SDR über PiDrive `/api/spectrum/capture`) im Dachboden.
Ziel: AliExpress-DVB-T-Antenne (A) gegen Teleskop ausziehbar (B).

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

## Antenne B — Teleskop (ausziehbar)

Gleiche Position (Dachboden), PPM 49, gleiche Gains. PMR Ch8 mit TX.
Rohdaten: `antenna-b-anchors.json`, `antenna-b-anchor-*.json`, `comparison-anchors.json`.

| Stützpunkt | Peak (dB) | SNR / rel | vs. A |
|------------|-----------|-----------|-------|
| FM 90,7 | 49,3 | **47,0** SNR | Peak −15,6 / SNR **+11,6** |
| FM 95,8 | 47,1 | **43,1** SNR | Peak −18,7 / SNR **+5,5** |
| FM 103,0 | 47,2 | **46,2** SNR | Peak −14,0 / SNR **+17,0** |
| FM 104,4 | 47,2 | **46,0** SNR | Peak −22,7 / SNR **+2,6** |
| K2 ATIS | 53,8 | **49,3** SNR | Peak −16,8 / SNR **+8,7** |
| DAB 10A | 47,0 | 34,6 SNR* | Peak −9,0 |
| DAB 11D | 47,0 | 32,1 SNR* | Peak −7,1 |
| PMR Ch8 TX | 43,3 pwr | **54,5 rel** | rel **−6,6** |

\* DAB-SNR B mit etwas breiterem Floor-Fenster; Peak-Δ ist der robustere DAB-Vergleich.

### Kurzfazit Antenne B (Teleskop)

- Ohne USB-LNA: **niedrigerer Peak**, aber **höherer SNR** (ruhigerer Rauschboden).
- **PMR Ch8:** klar erkannt, relative ~6,6 dB unter A (LNA-Vorteil von A).

---

## Vergleichstabelle Stützpunkte (A vs. B Teleskop)

Δ = B − A. Positives Δ SNR: B „sauberer“. Negatives Δ Peak / PMR-rel: A stärker (LNA).

| Ziel | A Peak | A SNR/rel | B Peak | B SNR/rel | Δ Peak | Δ SNR/rel |
|------|--------|-----------|--------|-----------|--------|-----------|
| FM 90,7 | 64,8 | 35,4 | 49,3 | 47,0 | −15,6 | **+11,6** |
| FM 95,8 | 65,8 | 37,6 | 47,1 | 43,1 | −18,7 | **+5,5** |
| FM 103,0 | 61,2 | 29,1 | 47,2 | 46,2 | −14,0 | **+17,0** |
| FM 104,4 | 69,9 | 43,4 | 47,2 | 46,0 | −22,7 | **+2,6** |
| K2 ATIS | 70,6 | 40,7 | 53,8 | 49,3 | −16,8 | **+8,7** |
| DAB 10A | 55,9 | 17,7 | 47,0 | 34,6* | −9,0 | (+)* |
| DAB 11D | 54,1 | 17,5 | 47,0 | 32,1* | −7,1 | (+)* |
| PMR Ch8 TX | — | **61,1 rel** | — | **54,5 rel** | — | **−6,6** |

### Bewertung

- **Antenne A (DVB-T + USB-LNA):** mehr absolute Feldstärke (Peak), besser bei PMR; LNA hebt auch den Rauschboden.
- **Antenne B (Teleskop ausziehbar):** oft besserer SNR trotz schwächerem Peak — weniger Verstärkerrauschen.
- Für schwache Signale (Airband idle / Randlagen) kann A durch Gain helfen; für UKW bei starkem Sender reicht B und klingt/misst „sauberer“.

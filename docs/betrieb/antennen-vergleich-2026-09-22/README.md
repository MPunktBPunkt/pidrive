# Antennen-Vergleich 2026-09-22

Spektrum-Messungen (RTL-SDR über PiDrive `/api/spectrum/capture`) im Dachboden.
Ziel: A AliExpress-DVB-T, B Teleskop, C Bingfu, D RTL-Stockantenne.

| | |
|---|---|
| Datum | 2026-09-22 |
| Position | Dachboden |
| PPM | 49 |
| Empfänger | RTL-SDR (PiDrive) |
| TX | PMR446 Ch8 nur während Stützpunkt-Messung (Nahfeld) |

Rohdaten: `antenna-{a,b,c,d}-*.json`. Stützpunkte: `antenna-*-anchors.json`, `comparison-anchors.json`.

---

## Übersicht Antennen

| ID | Typ | Claim / Hinweis |
|----|-----|-----------------|
| **A** | AliExpress DVB-T AT-01 | VHF 172–240 / UHF 470–860, USB-LNA 5 V, 75 Ω |
| **B** | Teleskop (ausziehbar) | passiv |
| **C** | Bingfu Magnetfuß 7 dBi | VHF 136–174 / UHF 400–470, 50 Ω, SMA, 3 m RG174 |
| **D** | RTL-SDR Beipack (kurz) | Stockantenne am Stick, vermutl. DVB-T-Beipack |

---

## Antenne A — AliExpress DVB-T AT-01

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

## Antenne C — Bingfu Magnetfuß (7 dBi)

**Claim:** VHF 136–174 MHz / UHF 400–470 MHz, 7 dBi, VSWR &lt;2, 50 Ω, omni, Magnetfuß,
3 m RG174, SMA-Buchse. **Im Claim:** PMR446 und oberes Airband-Ende; **außerhalb:** UKW, ATIS 118,855, DAB.

Rohdaten: `antenna-c-anchors.json`, `antenna-c-anchor-*.json`.

| Stützpunkt | Peak (dB) | SNR / rel | Rang Peak | Rang SNR/rel |
|------------|-----------|-----------|-----------|--------------|
| FM 90,7 | 52,0 | 46,8 | 2. (nach A) | ≈B |
| FM 95,8 | 47,1 | 39,0 | ≈B | 3. |
| FM 103,0 | 47,2 | 39,3 | ≈B | 3. |
| FM 104,4 | 47,2 | 37,7 | ≈B | 3. |
| K2 ATIS | **58,2** | 46,5 | 2. (nach A) | 2. |
| DAB 10A | 47,2 | 30,5 | ≈B | 3. |
| DAB 11D | 47,2 | 26,5 | ≈B | 3. |
| PMR Ch8 TX | 43,3 pwr | **56,8 rel** | — | 2. (A&gt;C&gt;B) |

### Kurzfazit Antenne C (Bingfu)

- **PMR (Claim-Band):** stark — zwischen A und B (rel. 56,8).
- **ATIS:** besserer Peak als Teleskop B, unter A-LNA.
- **UKW/DAB (außerhalb Claim):** ähnlich B, SNR meist unter Teleskop.

---

## Antenne D — RTL-SDR Beipack (kurze Stockantenne)

Kurze Whip, die dem RTL-Stick beilag (typisch DVB-T-Beipack). Passiv, direkt am Stick.
Rohdaten: `antenna-d-anchors.json`, `antenna-d-anchor-*.json`.

| Stützpunkt | Peak (dB) | SNR / rel | Einordnung |
|------------|-----------|-----------|------------|
| FM 90,7 | 47,3 | **48,3** | Peak schwach; SNR oft best |
| FM 95,8 | 47,2 | **46,8** | wie B, SNR hoch |
| FM 103,0 | 47,2 | **46,7** | wie B, SNR hoch |
| FM 104,4 | 47,2 | 46,1 | ≈B |
| K2 ATIS | **48,8** | 46,7 | schwächster ATIS-Peak |
| DAB 10A | 47,1 | 32,5 | ≈B/C Peak |
| DAB 11D | 47,2 | 31,0 | ≈B Peak |
| PMR Ch8 TX | — | **54,2 rel** | ≈B (schwächstes PMR mit B) |

### Kurzfazit Antenne D (RTL-Stock)

- **UKW:** SNR oft am höchsten, Peak aber flach (~47 dB) — wenig absolute Feldstärke.
- **ATIS:** klar schwächster Peak der Serie.
- **PMR:** ≈ Teleskop B, unter Bingfu und A.
- Als Referenz-/Baseline sinnvoll, nicht als Primärantenne.

---

## Vergleichstabelle Stützpunkte (A / B / C / D)

Werte: Peak / SNR (bzw. `relative_db` bei PMR). ★ = best in Zeile.

| Ziel | A | B | C | D | Peak★ | SNR/rel★ |
|------|---|---|---|---|-------|----------|
| FM 90,7 | 64,8 / 35,4 | 49,3 / 47,0 | 52,0 / 46,8 | 47,3 / **48,3** | **A** | **D** |
| FM 95,8 | 65,8 / 37,6 | 47,1 / 43,1 | 47,1 / 39,0 | 47,2 / **46,8** | **A** | **D** |
| FM 103,0 | 61,2 / 29,1 | 47,2 / 46,2 | 47,2 / 39,3 | 47,2 / **46,7** | **A** | **D** |
| FM 104,4 | 69,9 / 43,4 | 47,2 / 46,0 | 47,2 / 37,7 | 47,2 / **46,1** | **A** | **D**≈B |
| K2 ATIS | **70,6** / 40,7 | 53,8 / **49,3** | 58,2 / 46,5 | 48,8 / 46,7 | **A** | **B** |
| DAB 10A | **55,9** / 17,7 | 47,0 / **34,6*** | 47,2 / 30,5* | 47,1 / 32,5* | **A** | **B*** |
| DAB 11D | **54,1** / 17,5 | 47,0 / **32,1*** | 47,2 / 26,5* | 47,2 / 31,0* | **A** | **B*** |
| PMR Ch8 | **61,1** rel | 54,5 | 56,8 | 54,2 | — | **A** |

\* DAB-SNR B/C/D mit breiterem Floor; Peak robuster für DAB.

### Bewertung

- **A (DVB-T + USB-LNA):** stärkste Peaks, bestes PMR und DAB-Peak; LNA hebt den Rauschboden.
- **B (Teleskop):** bestes ATIS-SNR; starkes UKW-SNR ohne LNA.
- **C (Bingfu):** gutes PMR (Claim-UHF), ATIS-Peak Platz 2; UKW mittel.
- **D (RTL-Stock):** Baseline — hohe UKW-SNR-Zahlen bei schwachem Peak; ATIS/PMR schwach.
- Praxis: schwach → A (Gain) oder C (PMR/VHF-Claim); UKW stark → B; D nur Notbehelf.

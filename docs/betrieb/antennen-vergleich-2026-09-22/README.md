# Antennen-Vergleich 2026-09-22

Spektrum-Messungen (RTL-SDR über PiDrive `/api/spectrum/capture`) im Dachboden.
Ziel: aktive AliExpress-DVB-T-Antenne (A) gegen die bisherige Antenne (B, folgt).

| | |
|---|---|
| Datum | 2026-09-22 |
| Position | Dachboden |
| PPM | 49 |
| Empfänger | RTL-SDR (PiDrive) |
| TX | keiner (PMR nur Empfang) |

Rohdaten: `antenna-a-*.json` in diesem Ordner.

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

### Kurzfazit Antenne A

- **UKW:** sehr stark (mehrere Sender >40 dB SNR).
- **Airband:** K2 ATIS und K6 klar; idle-Kanäle erwartungsgemäß niedrig.
- **DAB B3 / UHF-Stichprobe:** Energie im Claim-Band vorhanden.
- **PMR446:** Idle, kein TX — Vergleichswert für Antenne B.

---

## Antenne B — bisherige Antenne (folgt)

Messung nach Antennenwechsel mit denselben Bändern, Gains und PPM.
Spalten „Δ SNR vs. A“ werden hier ergänzt.

| Band | Status |
|------|--------|
| UKW | ausstehend |
| Airband | ausstehend |
| DAB Band III | ausstehend |
| PMR446 | ausstehend |
| UHF-TV-Stichprobe | ausstehend |

---

## Vergleichstabelle (A vs. B)

| Ziel | A Peak (dB) | A SNR (dB) | B Peak | B SNR | Δ SNR |
|------|-------------|------------|--------|-------|-------|
| FM 90,7 | 73,2 | 42,6 | — | — | — |
| FM 95,8 | 67,1 | 41,1 | — | — | — |
| FM 104,4 | 73,5 | 48,3 | — | — | — |
| K2 ATIS | 71,7 | 42,3 | — | — | — |
| K6 Radar | 47,2 | 22,4 | — | — | — |
| PMR K1 (idle) | 29,0 | 6,8 | — | — | — |
| DAB top (~208) | 74,6 | — | — | — | — |
| UHF ~480 | 50,3 | — | — | — | — |

Nach Messung B: Spalten füllen und Δ = SNR_B − SNR_A.

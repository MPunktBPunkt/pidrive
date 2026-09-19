# pidrivectl spectrum — UKW-Peak-Scan

## Kommando

```bash
# Top-10 im UKW-Band (Defaults aus settings.json)
pidrivectl spectrum scan

# Bereich + Anzahl Peaks
pidrivectl spectrum scan 87.5-108 -n 10
pidrivectl spectrum scan 102.5:103.5 -n 3
pidrivectl spectrum scan --start 87.5 --stop 108 --peaks 1

# Einzelkanal (Offset-Fenster, DC-sicher)
pidrivectl spectrum peek 106.9
pidrivectl spectrum peek 100.2 --gain 30

# Letztes Ergebnis
pidrivectl spectrum last
pidrivectl spectrum last --json
```

## Parameter

| Option | Bedeutung | Default |
|--------|-----------|---------|
| `RANGE` / `--start`/`--stop` | Scanbereich MHz | `spectrum_start/stop_mhz` (87.5–108) |
| `-n` / `--peaks` | wie viele Top-Cluster | `spectrum_peaks` (10) |
| `--gain` | Tuner-Gain dB, `-1`=AGC | `scanner_gain` / `fm_gain` |
| `--ppm` | Quarzkorrektur | `ppm_correction` |
| `--avg` | Averaging-Frames | `spectrum_avg` (2) |

## Ergebnis

Kanalenergie (±75 kHz) → Cluster (~180 kHz) → sortiert nach Stärke.  
Bekannte Frequenzen werden annotiert (RT1, Bayern 1/2/3, FM4, SWR3, Antenne, BR24/B5, …).

## FM-Empfang Settings (`config/settings.json`)

Aus der UKW-Untersuchung 2026-09-19:

- `fm_gain`: **25**
- `scanner_gain`: **25**
- `ppm_correction`: **49**
- `spectrum_*`: Scan-Defaults

`fm.py` liest `ppm_correction` (nicht nur Alias `ppm`).

# Lab HU-Mimic Feld 15:41 · Fenster-Miss

**ESP:** `192.168.178.88` · FW `0.4.45-dev` · `/dev/sda` · Artefakt: `lab88-hu-mimic-1617/`
**Tool:** `tools/m3_lab_hu_mimic_1541.py` · Semantik: [`STREAM-COUNTER-SEMANTIK.md`](STREAM-COUNTER-SEMANTIK.md)

## Feldreferenz (status-1541)
- hostAbs=253952 abs=161944..211096
- underruns=streamBytes=253952 · ring size=49152

## Szenarien (HU 4 KiB @ 4.5 ms)

| Sc | Idee | max_live | max_ahead | full_und_phase | mirrors_1541 |
|----|------|----------|-----------|----------------|--------------|
| **A** | Race (kaum Prefill → Mid-Burst) | 4096 | 285696 | ~98 % und | **nahe** (`REPORT.mirrors_1541=false`: live≠0, und≠sb exakt) |
| **B** | Fill dann Pace (Positiv) | 373760 | 34816 | False | False |
| **C** | Fill dann schneller Outrun | 472576 | 268288 | False | False |

## Kernbefunde

1. **Szenario A ≈ Feld 15:41:** Mid-Burst bei dünnem Prefill → `hostAbs` ≈ 311 KiB, `absEnd` nur ~26 KiB, `und≈307 KiB` / `live=4 KiB` (~98 % Underrun). GPT-Frage „wer bewegt sich?“: **beide**, aber Cursor outran den Producer.
2. **Szenario B (Positiv):** Ring vorher füllen + Pace → `liveBytes` ≫ 0 — Fenster-Hit im Lab erreichbar (HU-Decode/Ohr noch nicht).
3. **Szenario C:** erst Live, dann schneller Outrun → `ahead` groß bei kumuliertem live (anders als Feld: dort war live≈0).
4. Zeitreihen (`series-*.jsonl`) widerlegen „Fenster statisch“ als alleinige Erklärung; der Feldzustand ist **Cursor vor absEnd nach Mid-Race**.

## Maßnahmen daraus

- Feld: Correlate mit `--dense --interval 0.5` (Tool aktualisiert).
- Nächster Lab-Schritt: Arm-Diagnose (cold mid ohne audio_start) separat; kein Detect-Umbau.
- Freeze hält.


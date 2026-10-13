# Lab — HU-ähnlicher Body-Burst · 21:43 · PD0042

**FW:** `0.4.45-dev` · Seed aus · `tools/m3_lab_av_burst_sim.py --step-kib 8`  
**Artefakt:** `docs/betrieb/artifacts-2026-10-04-lab/lab88-av-burst-2143/`  
**Fenster:** 176128…225280

## Ampel

| Prüfpunkt | Status | Beleg |
|-----------|--------|-------|
| Sequentieller Burst im Fenster | **PASS** | 6× 8 KiB-Steps; `hostAbs` 184320→225280 |
| `liveBytes` während Burst | **PASS** | 159744→200704, `underruns=0` |
| Prefill-Zone LBA **761** (fileOff 348160) | **PASS (Kontrast)** | außerhalb Fenster → `underruns` **+32768**, `liveΔ=0` |

## Deutung

1. Lab kann den HU-Cold-Body-Stil nachbilden: Cursor läuft mit, Live-Bytes steigen ohne Underrun.  
2. Genau die Feld-typische Prefill-LBA **761** liefert bei spät liegendem Fenster **nur Underrun** — passt zur Cursor-/Fenster-Hypothese und zu `not_from_head`-Bursts weit hinter dem Kopf.  
3. Für morgen AV: Producer-Fenster muss die **tatsächlich gelesenen** HU-`fileOff`s abdecken (nicht nur „Ring voll irgendwo“).

## Freeze

Unverändert.

# Lab — AV Fenster-Grenzen · 21:24 · PD0042

**FW:** `0.4.45-dev` · Seed aus · `tools/m3_lab_av_window_bounds.py`  
**Artefakt:** `docs/betrieb/artifacts-2026-10-04-lab/lab88-av-window-2124/`  
**Fenster:** abs 155648…204800 · Ring `size=49152`

## Ampel

| Prüfpunkt | Status | Beleg |
|-----------|--------|-------|
| Mehrpunkt **im** Fenster | **PASS** | 3× Reads mit MPEG-Syncs; `live` 24576→**61440** (`underruns` bleibt 0) |
| Reads **außerhalb** Fenster | **PASS (Telemetrie)** | `underruns` +**24576** bei below/above; `live` bleibt 61440 |
| Sync-Fingerprint außen vs innen | **schwach** | Auch außerhalb Sync-Kandidaten / ffmpeg dekodiert (Mp3Silence ≈ gültige Silence-Frames) |
| ffmpeg-Smoke innen | **PASS** | `sample-in0` → WAV 88 KiB / 1 s |

## Kernbefund

1. **Fenster-Hypothese lab-seitig gestützt über Underrun-Buchhaltung**, nicht über „Sync ja/nein“: außerhalb des Live-Fensters zählt der Serve als Underrun; innerhalb steigt `liveBytes`.  
2. **Fingerprint allein reicht nicht** zur Abgrenzung Live-MPEG vs. Silence-Fill — beide können `0xFFEx`-Syncs und ffmpeg-WAV erzeugen. Feld-Stufe C braucht `liveBytes`/`underruns` + Fensterkorrelation (+ Ohr), nicht nur Sync-Zähler.  
3. Tool für morgen: `tools/feld_av_correlate.py` (`hostAbs` ∈ Fenster, `liveBytes`).

## Freeze

Unverändert. Kein Sequenz-GO.

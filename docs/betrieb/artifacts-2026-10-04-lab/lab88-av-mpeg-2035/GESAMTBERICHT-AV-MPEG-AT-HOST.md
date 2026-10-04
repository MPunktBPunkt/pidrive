# Lab — AV MPEG am Host-Read · 20:35 · PD0042

**FW:** `0.4.45-dev` · Seed **aus** · Tool `tools/m3_lab_av_mpeg_at_host.py`  
**Artefakt:** `docs/betrieb/artifacts-2026-10-04-lab/lab88-av-mpeg-2035/`  
**Feed:** `L1.mp3` 180 KiB via Pump-TCP → fav0

## Ampel

| Stufe | Status | Beleg |
|-------|--------|-------|
| **A** Producer → Ring | **PASS** | `stream.active`, `size=49152` (voll), `underruns=0` vor Body-Hit |
| **B** MPEG an Host-LBA | **PASS** | Live-Read LBA **369** (`fileOff=147456`): MPEG-Syncs (`0xfffb…`); Head LBA 81: **ID3**; `liveBytes=24576`, `underruns=0` |

## Zahlen (Stage B nach dd)

| Metrik | Wert |
|--------|------|
| abs window | 135168 … 184320 |
| hostAbsCursor | 142848 (im Fenster) |
| streamBytes / underruns / live | 24576 / 0 / **24576** |
| live prefix | `55…` + `fffb` (MPEG) |
| head post | `ID3…` |

## Deutung

1. Mit Seed aus und gültigem Pump-MP3 liefert MSC **echte MPEG-Bytes** an den Host — nicht nur Silence/Underrun.  
2. Feld-Muster `streamBytes==underruns` (live≈0) ist damit ein **Daten-/Fenster-Problem** (Producer/Cursor), kein generelles „MSC kann kein MPEG“.  
3. Nächster Engpass für Auto: denselben Nachweis unter HU-Reads (Stufe C/D) — Ring muss am **HU-fileOff** gefüllt sein, nicht nur im Lab-dd-Fenster.

## Freeze

Ring/PSRAM/Pacing/Detect unverändert. Sequenz-GO weiter bis Feld-Hörtest.

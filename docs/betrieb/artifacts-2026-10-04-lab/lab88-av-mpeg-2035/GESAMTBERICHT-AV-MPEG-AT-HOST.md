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

1. Mit Seed aus und Pump-MP3 liefert MSC am **gezielt ins Live-Fenster gelegten** Host-dd MPEG-*kompatible* Bytes (Sync/ID3-Indiz) — nicht nur Silence/Underrun. Kein Decoder-/Hörtest.  
2. Feld-Stille als reines „kein MPEG möglich“ ist widerlegt; **Cursor/Fenster** ist die beste **Hypothese** bis zur HU-Korrelation — nicht abschließend bewiesen.  
3. Nächster Engpass: Stufe C/D im Auto — HU-`fileOff` × Fenster × Inhalt × Ohr.

## Freeze

Ring/PSRAM/Pacing/Detect unverändert. Sequenz-GO weiter bis Feld-Hörtest.

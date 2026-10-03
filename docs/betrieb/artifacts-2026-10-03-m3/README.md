# Artefakte M3 — Lab 2026-10-03 (ohne Auto)

**Kontext:** Nutzer nicht im Auto → nur Lab `.88` / Proxmox `.108`.  
**FW Lab aktuell:** **`0.4.41-dev`** FAT16 **16 MiB** / 4 MiB-Slots + PDMK-Marker.  
**Bridge:** `.105` · Host `.108`

## Assets (ffmpeg)

| Datei | Größe | Marker |
|-------|------:|--------|
| `mp3/L1.mp3` + markers | ~524 KiB | hörbar 30 s |
| `mp3/L2.mp3` + markers | ~2.0 MiB | hörbar 30 s |

ESP nutzt algorithmische **PDMK**-Stamps in `Mp3Silence` (nicht die ffmpeg-Dateien).

## Passes

| Ordner | FW | Ergebnis |
|--------|-----|----------|
| `lab88-timeline-142120/` | 0.4.37 | Sweep→Idle A/E; paced forced-C |
| `lab88-markers-1503/` | 0.4.40 4 MiB | PDMK verify **6/6** |
| `lab88-timeline-markers-1503/` | 0.4.40 | erneut A/E + paced-C |
| `lab88-marker-pace-151344/` | 0.4.40 | Marker-Kreuzungen ~0.7 s / **30.3 s** / **60.4 s** (≈6 KiB/s) |
| `lab88-16m-markers/` | **0.4.41** | Host `file -s`: **FAT (16 bit)**; PDMK **8/8**; sectors=32768 |
| `lab88-16m-timeline/` | 0.4.41 | siehe report — Lab-Host Sweep/Idle/Paced |

## Folgerung

1. Marker↔Zeit-Korrelation im Lab belastbar (Pace ~30 s).  
2. **Echtes FAT16** auf 16 MiB validiert (nicht nur BPB-String).  
3. 4 MiB-Slots = L2-Skala; Idle nach Sweep weiter ohne Reads (Lab-Host).  
4. NBT-A–E weiter **Auto-only**. Nächstes Lab: optional 8 MiB-Einzelslot / L3 — oder Feld.

## Tools

- `tools/m3_make_marked_mp3.py`
- `tools/m3_lab_host_timeline.py`
- `tools/m3_lab_verify_markers.py`
- `tools/m3_lab_marker_pace.py`

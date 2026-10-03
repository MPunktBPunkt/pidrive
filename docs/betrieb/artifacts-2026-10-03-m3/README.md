# Artefakte M3 — Lab 2026-10-03 (ohne Auto)

**Kontext:** Nutzer nicht im Auto → nur Lab `.88` / Proxmox `.108`.  
**FW Lab:** **`0.4.40-dev`** FAT12 L0 + **PDMK-Marker** in `Mp3Silence` (alle ~30 s / 180 KiB).  
**Bridge:** `.105` · Host `.108`

## Assets (ffmpeg, für spätere Hörtests)

| Datei | Größe | Marker |
|-------|------:|--------|
| `mp3/L1.mp3` + `L1.markers.json` | ~524 KiB | alle 30 s (hörbar) |
| `mp3/L2.mp3` + `L2.markers.json` | ~2.0 MiB | alle 30 s |

ESP-Slot nutzt vorerst **algorithmische** PDMK-Stamps (nicht die ffmpeg-Dateien).

## Marker-Verify `lab88-markers-1503/`

Tool: `tools/m3_lab_verify_markers.py`  
**PASS:** 6/6 Marker `PDMK`+idx auf fav0 (Stream muss **aus** sein — sonst Overlay statt Silence).

## Timeline `lab88-timeline-142120/` (vorher, 0.4.37 Silence)

Sweep→Idle A/E; Paced forced-C (Lab-Host ≠ NBT).

## Timeline `lab88-timeline-markers-1503/` (0.4.40 + Marker)

Gleiche Methodik nach Marker-OTA — siehe `report.json`.

## Folgerung

1. Messpipeline + M0-Bilanz ok.  
2. Marker im Slot **lab-verifiziert** (Ebene-1-Anker für spätere Cursor-Korrelation).  
3. Lab-Host nach Sweep idle = A/E; paced = forced C — **kein** NBT-Urteil.  
4. Nächstes: Feld A–E am Auto **oder** Lab L3-Geometrie; kein Ring/BT.

## Tools

- `tools/m3_make_marked_mp3.py`
- `tools/m3_lab_host_timeline.py`
- `tools/m3_lab_verify_markers.py`

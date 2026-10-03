# Artefakte M3 — Lab 2026-10-03 (ohne Auto)

**Aktuelle Lab-FW:** **`0.4.42-dev`** · FAT16 · 16 MiB Disk · **fav0 = 8 MiB (L3)** + 2×512 KiB · PDMK-Marker  
**Session-Bericht (ausführlich):** [`SESSION-LAB-2026-10-03.md`](SESSION-LAB-2026-10-03.md)  
**Host:** Proxmox `.108` · Bridge `.105` · ESP `.88`

## Pass-Übersicht

| Ordner | FW | Kernbefund |
|--------|-----|------------|
| `mp3/` | — | ffmpeg L1/L2 hörbare Marker-Assets |
| `lab88-timeline-142120/` | 0.4.37 | Sweep→Idle A/E; paced forced-C |
| `lab88-markers-1503/` | 0.4.40 | PDMK **6/6** (1 MiB) |
| `lab88-timeline-markers-1503/` | 0.4.40 | A/E + paced-C |
| `lab88-marker-pace-151344/` | 0.4.40 | Crossings ~30 s / 60 s |
| `lab88-16m-markers/` | 0.4.41 | Host **FAT16**; PDMK 8/8; 4 MiB-Slots |
| `lab88-16m-timeline/` | 0.4.41 | Idle Δ0; paced forced-C |
| **`lab88-l3-1526/`** | **0.4.42** | **fav0=8 MiB**; FAT16; PDMK **12/12**; Timeline A/E+paced; Pace 0/30/60/90 s |
| **`lab88-l3-langpace-1535/`** | **0.4.42** | **360 s** Langpace; **12** Kreuzungen m0–m11; spacing_mean **29.979 s** |
| **`lab88-l3-fat-verify-1615/`** | **0.4.42** | BPB+`fsck.fat`: **4087 Cluster = FAT16** (Margin +2); fav0 SHA dokumentiert |
| **`lab88-export-calib-1835/`** | **0.4.42** | **Kalib A+B PASS**: Pre-Connect-Lücke `export_frac=0`; Burst 10/50/100 ms vollständig; M0 `Δrc=Σn` |
| **`lab88-m3seq-rehearsal-1905/`** | **0.4.42** | Lab-M3seq-Rehearsal: Idle quiet; Select-fav1 ohne Remount; Remount passiv Δ0 / +Nudge Δ256 |
| **`auto89-m3seq-2042/`** | **0.4.42 Auto** | Feld-M3seq Rohdaten; siehe Trace-Korrektur-Bericht |
| **`GESAMTBERICHT-AUTO-M3SEQ-TRACE-KORREKTUR-2026-10-04.md`** | — | **Normativ:** Q2 warm-konfundiert; Select/Resume-Vollreads; Sequenz vs BT |
| **`GESAMTBERICHT-AUTO-M3-NACH-REVIEW-2026-10-03.md`** | — | älterer Gesamtbericht (vor Trace-Korrektur) |
| **`AUTO-M3-FELD-2026-10-03.md`** | **0.4.42 Auto** | Feld **A_then_E**: Play ~8 min Δrc=0; Artefakte `auto89-m3-static-170625/`, seq `auto89-m3seq-1728/` |

## L3-Geometrie (0.4.42)

Siehe `lab88-l3-1526/geometry.json`:

- Disk 32768×512 = 16 MiB, Host `FAT (16 bit)`  
- fav0: 16384 Sektoren = **8.0 MiB**  
- fav1/fav2: je 1024 Sektoren = 0.5 MiB  
- Ready: `FAT16 L3 16MiB fav0=8M`

## Lab-Host-Muster (wiederholt)

Nach Mount/Remount-Sweep: **Idle ohne weitere Reads**.  
Cursor-nahe Reads nur unter **Lab-Paced-Consume @ 6 KiB/s**.  
→ Klassifikation `A_then_forced_C` (**nicht** NBT-A–E).

## Tools

`m0_lab_mount_sweep.py` · `m3_make_marked_mp3.py` · `m3_lab_verify_markers.py` · `m3_lab_host_timeline.py` · `m3_lab_marker_pace.py` · `m3_lab_export_calib.py` · **`m3_lab_m3seq_rehearsal.py`**

## Nächstes

→ Normativ: [`GESAMTBERICHT-AUTO-M3SEQ-TRACE-KORREKTUR-2026-10-04.md`](GESAMTBERICHT-AUTO-M3SEQ-TRACE-KORREKTUR-2026-10-04.md) · Plan Rev.4.  
P0 Menü-Lock → P1 kalter Auto-Next → parallel Q3-Lab + BT-UX. Ring Freeze bis P1 grün.

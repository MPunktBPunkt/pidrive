# Artefakte M3 — Lab 2026-10-03 (ohne Auto)

**Kontext:** Nutzer nicht im Auto → nur Lab `.88` / Proxmox `.108`.  
**FW:** `0.4.37-dev` L0 · Bridge `.105` · **Inhalt:** weiterhin `Mp3Silence` (markierte MP3s als Assets vorbereitet, noch nicht in ESP injiziert).

## Assets

| Datei | Größe | Marker |
|-------|------:|--------|
| `mp3/L1.mp3` + `L1.markers.json` | ~524 KiB | alle 30 s |
| `mp3/L2.mp3` + `L2.markers.json` | ~2.0 MiB | alle 30 s |

Generator: `tools/m3_make_marked_mp3.py`

## Timeline-Pass `lab88-timeline-142120/`

Tool: `tools/m3_lab_host_timeline.py`

| Phase | Ergebnis |
|-------|----------|
| 1 Sweep (Remount+Nudge) | Δrc=167 = Σn; ~0,7 s Burst; Bilanz ok |
| 2 Idle 90 s | **Δrc=0** — keine weiteren Reads |
| 3 Paced 60 s @ 6 KiB/s fav0 | Δrc=704 = Σn; LBA 57→755 |

**Lab-Host-Klassifikation:** `A_then_forced_C`  
→ Nach Sweep wie Cache/fertig (A/E); cursor-nahe Reads **nur**, wenn der Lab-Host bewusst paced nachliest.  
**Nicht** BMW-NBT-A–E.

Ebenen: 1 ja · 2 ungeklärt · 3 nur unter Lab-Pacing · 4 nein (kein Live).

## Folgerung

1. Messpipeline (Sweep-Ende / Idle / Paced) funktioniert mit M0-Gleichung.  
2. Linux-Host allein belegt nicht NBT-Verhalten — bestätigt nur: ohne Nachlese-Stimulus = still.  
3. Nächste Lab-Schritte: markierte MP3 in Slot bringen (kleine FW-/Payload-Änderung) **oder** Feld M3 am Auto mit gleicher Timeline-Methodik.  
4. Kein Ring/BT.

## Tools

- `tools/m3_make_marked_mp3.py`
- `tools/m3_lab_host_timeline.py`

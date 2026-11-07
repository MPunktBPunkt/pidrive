# Spec · Sender-Untermenü Play / Stop / Live · 2026-10-11

**Status:** Spike · FW Freeze `0.4.46-dev` (kein OTA) · Bridge-Änderung erlaubt  
**Ziel:** Produktpfad **ohne OTG-Replug** — Stream vorwärmen, dann Kopf lesen.

## 1. Problem

Replug war nur Mess-Trick. Produkt: OTG steckt, Pi bootet, Stream startet später.  
Heute: Tip auf Sender-Datei = Play-Detect **und** Audio-Read → Henne-Ei (B5).

## 2. Menümodell (≤4 MSC-Slots)

Flach, **msc-lock-tauglich** (eine Seal-Map, kein Drill-Down nötig):

| Slot | Name (Beispiel) | uid | kind | Wirkung |
|------|-----------------|-----|------|---------|
| 0 | `Radio BOB` | `fav2` | station | **Großer** Slot — Live-Datei; Tip erst **nach** Prefill |
| 1 | `Play BOB` | `pump:arm:fav2` | action | Stream + ID3 vorwärmen (kurzer Nav-Stub) |
| 2 | `Stop` | `pump:stop` | action | `audio_stop` |
| 3 | `Menue` | `pump:page_next` | action | weitere Sender-Seiten später |

Slot0 muss Live sein (feste FAT-Geometrie: nur Index 0 ist groß).

Gleiche Struktur für fav0/fav1 auf Folgeseiten (Mehr…).  
Echte FAT-Ordner pro Sender sind optional später; flach reicht für Spike und Feld.

## 3. Bridge-Verhalten

1. `play_uid=pump:arm:<uid>` → `audio_start` für `<uid>` (Preset/URL), **kein** `activate`/`audio_stop`-Nav.  
2. `play_uid=<uid>` während bereits `audio.uid==<uid>` → **kein** erneutes `audio_start` (sonst `clearId3`/Ring weg).  
3. `play_uid=pump:stop` → Stop (bestehend).  
4. Folder/andere Actions: unverändert Navigation (kein unbeabsichtigtes Arming).

## 4. Ablauf (Lab / Feld)

```
OTG an → Bridge seal (Play/Live/Stop/Menue)
  → Tip Play     → Prefill ≥ Ring (~12 s @32k / ~8 s @48k)
  → Tip Live     → Head-from-0, Ring voll → Tonfenster
  → Tip Stop     → aus
```

Kein physisches OTG-Ziehen. Soft-Remount **während** Stream bleibt FW-`remount_skip` (Lab 09.10.) — deshalb Live-Tip statt Remount.

## 5. Lab-Gate (dieses Spike)

Skript: `docs/betrieb/artifacts-2026-10-11-lab/lab-station-arm-play/run.py`

| Check | Soll |
|-------|------|
| Arm via `pump:arm:fav2` (Host-Head-Read Action-Slot) | `stream_active`, `absEnd` wächst |
| Prefill | Ring ≈ 48 KiB / `absEnd` ≥ Ring |
| Head-Read Live **ohne** zweiten `audio_start` | Live-Bytes > 0 @ Host-Dump |
| Stop | `stream_active=false` |
| Soft-Reset | 0 (Serial/Uptime stabil) |

## 6. Nicht in diesem Spike

- Stall / Dauerstrom  
- FW Remount-mit-Stream  
- P-Reset (Name/Größe)  
- Echte BMW-Ordner-UX  
- Feld s6

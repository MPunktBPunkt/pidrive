# Feld · OTA 0.4.53 + OTG · 2026-10-17 ~12:09–12:16

**ESP `.89` · FW `0.4.53-dev` · Bridge `.105` · Stall aus**

## Ablauf

| Zeit | Ereignis |
|------|----------|
| ~12:09 | Online `0.4.52-dev`, OTG aus → OTA **0.4.53** OK |
| 12:10/11 | OTG an — Klasse A (`reset`≠panic, `led=otg`, WLAN hält) |
| 12:12 | NBT: **nur Dateien**, keine Ordner (Stick zeigt sonst Ordner) |
| ~12:13–14 | Erster Steckzyklus **Antenne Bayern** — Stream `fav1`, Bridge forwadet Audio |

## Status

- Panic/Weiß bei diesem Plug: **nein** (Klasse A)
- Favoriten-Ordner-UI am NBT: **nein** (ESP-Pfade `FAVORITEN/…` ok; HU flach / alte Titel)
- LIVE Bayern: **ja** (Operator + `stream.uid=fav1`)

## Offen / nächstes Feld

1. M8 Panic systematisch (UART, VBUS) — heute nur ein guter Zyklus
2. Warum NBT keine Ordner zeigt (vs. Stick) — DIR/LFN/Vol vs. Alle-Titel
3. Stall-Leiter am NBT erst nach mehr Klasse-A-Stabilität

Artefakte: `status-*-ota.json`, `otg-1210/`, `nbt-flat-1212/`, `klasse-a-bayern-1214/`

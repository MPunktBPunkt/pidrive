# Lab-Weiterarbeit — Seed-Gate / Survive / AV-Vorbereitung · 2026-10-04 Abend

**Kontext:** Feld 1738 C′ FAIL — Seed schon bei GO tot (Reboot ~4 s nach Arming), nicht erst RST 17:43. Auto erst morgen.

## Tools (neu)

| Tool | Zweck |
|------|--------|
| `tools/feld_q3b_next_prepare.sh` | + Settle-Gate + `status-03-go` + EAR „kein RST nach Seed“ |
| `tools/feld_q3b_seed_watchdog.py` | Feld: bricht ab bei `active→False` / Uptime-Collapse; PASS bei `bytesServed↑` |
| `tools/m3_lab_seed_survive.py` | Lab: Arm → 30 s Survive → optional `--hit` dd LBA 761 |

## Lab-Lauf (wenn `.88` wieder da)

```bash
# 1) Survive-Gate (ohne Host-Hit)
python3 tools/m3_lab_seed_survive.py --esp http://192.168.178.88 --settle-s 30

# 2) Survive + bytesServed-Hit (DebianCursor, disk group)
sg disk -c 'python3 tools/m3_lab_seed_survive.py --esp http://192.168.178.88 --dev /dev/sda --hit --settle-s 20'
```

Erwartung: Oracle A PASS, Survive PASS; mit `--hit` `bytesServed` steigt.

## Feld morgen (C′-Retry)

1. Letzte RST **zuerst** (nur wenn nötig).  
2. `tools/feld_q3b_next_prepare.sh` — muss **GATE PASS** drucken.  
3. Sofort Watchdog starten (siehe EAR).  
4. Auto-Next ohne RST/USB.  
5. PASS nur `bytesServed↑` + Body-LBAs im Trace.

## AV Lab 20:35 — A+B PASS

[`lab88-av-mpeg-2035/GESAMTBERICHT-AV-MPEG-AT-HOST.md`](lab88-av-mpeg-2035/GESAMTBERICHT-AV-MPEG-AT-HOST.md): Pump `L1.mp3` → Ring voll → Host-dd LBA 369 mit MPEG-Sync, `liveBytes=24576`, `underruns=0`.  
→ MSC-Pfad kann MPEG; Feld-`live≈0` ist Cursor/Producer-Fenster, nicht „kein MPEG möglich“.

**Offen:** C/D am Auto (HU-Reads + Ohr). Seed-Diagnose getrennt halten.

## Stand Seed-Gate 20:29

`lab88-seed-survive-2029/` — Survive + Hit **PASS**.

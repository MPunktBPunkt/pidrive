# Feld 60s Live-Read Passes — 2026-10-02

**Zentrale Frage:** Liest die BMW-NBT während der Wiedergabe kontinuierlich Live-MSC-Daten, oder nur Burst + Cache?

## Lab-Dryrun (Pipeline-Check)

| Pass | Ergebnis |
|------|----------|
| `fav0-145621` | Tool OK: `streamBytes_delta=356352`, 214 read-events over 60s, `underruns=0`. Paced MSC on Proxmox (not BMW). |

## Auto (pending)

Wenn ESP `.89` online: `./tools/feld_prepare_homecoming.sh` dann je UID:
`python3 tools/feld_60s_live_pass.py --uid fav0|fav1|fav2 --note "HH:MM"`

FW `0.4.36` liegt auf Pi `dist/` und Hub `iobroker.esp-hub/firmware/` (Auto war schon 0.4.36 — OTA nur falls nötig).

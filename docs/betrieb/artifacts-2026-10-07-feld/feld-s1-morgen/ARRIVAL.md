# Ankunft — Feld Stufe 1 Morgen (2026-10-07)

**Kein Stall-OTA.** FW **0.4.46-dev** L3. Lab vorbereitet: F1/F2-Tools + Q4-Dry-Run.

**Kalibrierung:** [`../../artifacts-2026-10-06-lab/KALIBRIERUNG-LAB-HU-2026-10-06.md`](../../artifacts-2026-10-06-lab/KALIBRIERUNG-LAB-HU-2026-10-06.md)  
**Q4 später:** [`EXPERIMENTKATALOG-Q4…`](../../artifacts-2026-10-06-feld/EXPERIMENTKATALOG-Q4-CACHE-MARKER-2026-10-07.md)

## Binaries
- OTA: `/home/martin/projects/esphub/esp32.pidrive/dist/pidrive.0.4.46-dev.ota.esp32s3.bin`
- SHA256: `0d35bf1051b8828a143ab653bc77a172872a4320042cf6bc50eb1df8a5c73edf`

## Prep (Zuhause / vor Losfahren)
```bash
./tools/feld_av_session_prep.sh --out docs/betrieb/artifacts-2026-10-07-feld/feld-s1-morgen
# OTA nur wenn nötig:
# ./tools/feld_av_session_prep.sh --ota --skip-ssh --out docs/betrieb/artifacts-2026-10-07-feld/feld-s1-morgen
```

## Im Auto (~45–60 min)

```bash
cd docs/betrieb/artifacts-2026-10-07-feld/feld-s1-morgen
./run-gate-check.sh
# Terminal A:
./run-status-poll.sh 400
# Terminal B — F1 (Bridge STOPPEN):
./run-f1-log.sh fav0          # Tasten: s=t_sel  t=t_timer  e=t_eof  q=quit
# Video auf Spielzeit!
# Gegenprobe:
./run-f1-log.sh fav1
# Terminal B — F2:
./run-f2-watch.sh 300         # fav1→fav2→fav1, dann OTG remount→fav1
./run-ingest.sh
```

### F1 Entscheidung
| Ergebnis | Bedeutung |
|----------|-----------|
| t_timer ≪ t_eof (fav0) | **inkrementell** → Stall-Pfad |
| t_timer ≈ t_eof | **after_eof** → Fallback Dateikette |

### F2
- fav1→fav2→fav1: `cold_burst` vs `cache_hit_like` im f2-watch  
- OTG remount: `remount_or_rst` dann erneut cold?

## PASS heute
F1 eindeutig + F2a/c notiert. Q4a–c **nicht** nötig für Stall-Go.

## Lab-Vorbereitung (bereits gelaufen)
- `tools/feld_f1_log.py` / `feld_f2_watch.py`
- `tools/nbt_marker_file.py` — Marker-Dateien unter `lab-prep/`
- `tools/m3_lab_q4_cache_matrix.py` — 3-Slot Dry-Run auf .88

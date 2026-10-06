# Ankunft — Feld Stufe 1 (feld-s1-1700)

**Kein Stall-OTA.** FW bleibt **0.4.46-dev** L3 (Lab Golden G1–G5 2× PASS).

## Binaries
- OTA: `/home/martin/projects/esphub/esp32.pidrive/dist/pidrive.0.4.46-dev.ota.esp32s3.bin`
- SHA256: `0d35bf1051b8828a143ab653bc77a172872a4320042cf6bc50eb1df8a5c73edf`
- Nur flashen wenn `.89` noch nicht `0.4.46-dev` ist

## Reihenfolge (~45 min)
1. Zündung / WLAN → `.89` und Pi `.105` online  
2. Bridge deploy:  
   `./tools/feld_av_session_prep.sh --out docs/betrieb/artifacts-2026-10-06-feld/feld-s1-1700`  
3. OTA nur bei Bedarf:  
   `./tools/feld_av_session_prep.sh --ota --skip-ssh --out docs/betrieb/artifacts-2026-10-06-feld/feld-s1-1700`  
4. USB OTG → Gate: `cd …/feld-s1-1700 && ./run-gate-check.sh`  
5. **F1:** fav0 / Silence — Spielzeit vs `slotMap.fav0.b` + Video  
6. Parallel: `./run-status-poll.sh 180` — `clock_sync` in `run.yaml` aus erster Zeile  
7. **F2 Cache:** fav1→fav2→fav1 — liest HU neu?  
8. `heard` / observations in `run.yaml` → `./run-ingest.sh`

## PASS heute
F1 **inkrementell vs after_eof** eindeutig + F2 Cache-Notiz. Ton nice-to-have; Stall wartet auf Go.

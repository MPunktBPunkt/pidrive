# Ankunft — Feld Stufe 1 (morgen / F1+F2 nachholen)

**Kein Stall-OTA.** FW bleibt **0.4.46-dev** L3.

**Lab-Stand (Overnight):** C1 strikt (`und=hostAbs=438272`) · C2 Klassifikator OTHER→0 · ALL G1–G5 PASS (`lab88-nbt-hu-sim-all-c2`) · G6 Lab-F2-Rehearsal PASS (Sim-Cache; Feld-Remount weiter offen).

## Binaries
- OTA: `/home/martin/projects/esphub/esp32.pidrive/dist/pidrive.0.4.46-dev.ota.esp32s3.bin`
- SHA256: `0d35bf1051b8828a143ab653bc77a172872a4320042cf6bc50eb1df8a5c73edf`
- Nur flashen wenn Fahrzeug-ESP noch nicht `0.4.46-dev` ist

## Reihenfolge (~45–60 min)

1. Zündung / WLAN → Fahrzeug-ESP und Pi online  
2. Bridge deploy:  
   `./tools/feld_av_session_prep.sh --out docs/betrieb/artifacts-2026-10-06-feld/feld-s1-1700`  
   *(oder neues `feld-s1-<HHMM>`-Verzeichnis anlegen und `run.yaml` kopieren)*  
3. OTA nur bei Bedarf  
4. USB OTG → Gate: `./run-gate-check.sh`  
5. **Bridge für F1 stoppen** (Silence-Datei ohne Live-Arm)  
6. Handy-Video: HU-Display mit **Spielzeit-Zähler** sichtbar  
7. Parallel: `./run-status-poll.sh 300` — `clock_sync` aus erster Poll-Zeile  

### F1 (Priorität — entscheidet Stall-Pfad)

| Schritt | Aktion | Notieren |
|---------|--------|----------|
| a | fav0 (8 MiB Silence) wählen | **t_sel** (Video + Wanduhr) |
| b | Erster sichtbarer Spielzeit-Tick 0:01 | **t_timer** |
| c | Poll: `slotMap.fav0.b` steigt nicht mehr (≥ 8 MiB) | **t_eof** |
| d | Gegenprobe fav1 (512 KiB) | dieselben drei Zeiten |
| e | 2–3 Wiederholungen | Streuung |

**Entscheidung:** `t_timer ≪ t_eof` (fav0) → **inkrementell** · `t_timer ≈ t_eof` → **after_eof**.  
Nicht aus `hostAbs`/LED ableiten.

### F2 (danach)

| Schritt | Aktion | Frage |
|---------|--------|-------|
| a | fav1 → EOF → fav2 → fav1 | Liest HU fav1 neu? (`readCount` / `slot.b`) |
| b | OTG raus 10 s → rein → Index → fav1 | Cache über Remount? |
| c | LED nur Hilfsindikator | Blink ≈ cold body / MSC — **kein** Cache-Orakel (R14) |

## PASS heute
- F1 eindeutig (Video + drei Zeitpunkte)  
- F2a + F2c mindestens notiert  
- `heard` / observations in `run.yaml` → `./run-ingest.sh`

Stall-Go erst nach F1 + Lab C1/C2 (bereits grün).

## Nicht morgen (parken)

- Multi-File-Cache-Matrix / 64×512 KiB (Q4b) — lohnt, aber eigener Termin  
- Eager-Leiter bis 64 MiB (Q4a)  
- Marker-Offset-Diagnose / Live-Grenze@300 KiB — braucht Stall-FW oder reine Diagnose ohne Silence-Zukunft  
→ [`EXPERIMENTKATALOG-Q4-CACHE-MARKER-2026-10-07.md`](../EXPERIMENTKATALOG-Q4-CACHE-MARKER-2026-10-07.md)

# Lab-Morgen — Pump-Kalibrierung fortgesetzt · 2026-10-08

**ESP:** Lab `.88` · FW `0.4.46-dev` · Host `192.168.178.187`  
**Nacht:** [`../lab88-pump-calib-night/GESAMTBERICHT-PUMP-CALIB-NIGHT.md`](../lab88-pump-calib-night/GESAMTBERICHT-PUMP-CALIB-NIGHT.md)  
**Freeze:** unverändert — kein Stall-OTA.

## Kurzfazit

**Echte Bridge+ffmpeg ist grün** (Webradio und Lokaldatei). Idle-Soak 120 s bei Feld-Rate ebenfalls.  
Fix in `esp32.pidrive` `pump_bridge.py`: `-reconnect*` nur noch für `http://` / `https://`.

## Läufe

| Lauf | Was | Ergebnis |
|------|-----|----------|
| `bridge-48k-l1` | Bridge 48k · lokal L1.mp3 (vor Fix) | **FAIL** · ffmpeg Exit 8 (`Option reconnect not found`) |
| `bridge-48k-l1-retest` | dasselbe **nach Fix** · ~30 s | **PASS** · ~**8,8 kB/s** · underruns 0 · listen ~62 KiB · kein Exit 8 |
| `bridge-48k-rock` | Bridge 48k · Rock-HTTPS · ~80 s | **PASS** · ~**6,8 kB/s** · underruns 0 · SoftAP listen ok |
| `bridge-96k-rock` | Bridge 96k · Rock · ~36 s | **PASS** · ~**17,3 kB/s** (target 18 k) · underruns 0 |
| Rock-Regression nach L1-Retest | fav1 umschalten | **PASS** · underruns 0 |
| `bridge-48k-marker` | Rock + `--marker` ~25 s | **PASS** · ~8,7 kB/s · marker_t0 gesetzt · underruns 0 |
| `bridge-48k-bob` | BOB nach Marker-Switch | **PASS** · fav2 aktiv · underruns 0 |
| `soak-9k-120s` | `m3_lab_pump_idle` batch=8 · 120 s | **PASS** · **8932 B/s** = absEnd |

Bridge-Forward bei 48k typisch ~8–9 kB/s (`target_bps=9000`); absEnd etwas darunter, wenn Ring am Cap und kein Host liest.

## Stellschrauben

| Parameter | Beobachtung |
|-----------|-------------|
| `--bitrate 48k` | stabil, Ring füllt, SoftAP-Listen ok |
| `--bitrate 96k` | ~2× schneller (`target_bps=18000`), underruns 0 |
| lokale Datei als `meta.url` | nach Fix **ok** (kein `-reconnect` mehr) |
| Idle-Pump Feld-Rate | 120 s ohne Drift |

## Bewusst nicht

- Kein HU-Hörtest, kein Stall, kein Flash

## Artefakte

`bridge-48k-l1/`, `bridge-48k-l1-retest/`, `bridge-48k-rock/`, `bridge-96k-rock/`, `soak-9k-120s/`

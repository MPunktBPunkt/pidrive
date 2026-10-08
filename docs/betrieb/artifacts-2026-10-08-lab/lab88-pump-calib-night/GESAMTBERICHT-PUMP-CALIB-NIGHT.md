# Lab-Nacht — Pi→ESP Pump-Kalibrierung · 2026-10-07/08

**ESP:** Lab `.88` · FW `0.4.46-dev` · Serial `PD0229` · SoftAP `pidrive-29339C`  
**Ziel:** Lieferkette Pi→ESP absichern (nicht HU-Hörbarkeit, nicht Stall).  
**Freeze:** unverändert — kein Stall-OTA.

## Kurzfazit

**Pump-Pfad grün.** Bei feldnaher Rate (~9 kB/s) wächst `absEnd` 1:1 mit gepumpten Bytes, `underruns=0`. SoftAP-Listen/`/api/lab/stream` liefert danach gültiges MPEG. Das ist **kein** Dauer-Ton an der HU.

## Läufe

| Lauf | Config | Ergebnis |
|------|--------|----------|
| `burst-8s` | gap=0, batch=4, 8 s | **PASS** · 6 592 300 B · ~824 kB/s · absEnd Δ gleich |
| `fieldrate-20s` | gap=0.45 **pro Frame** (batch=1) | **FAIL/Fehlconfig** · nur ~1,1 kB/s (zu langsam) |
| `fieldrate-9k-25s` | gap=0.455 **pro 4 KiB** (batch=8) | **PASS** · 225 280 B · **8998 B/s** · absEnd 0→225280 · underruns 0 |

Korrekte Feld-Rate-Formel: eine Pause pro Chunk (`batch = chunk/frame_max`), nicht pro Frame.

## SoftAP / Listen (nach Pump)

| Probe | HTTP | Größe | Deutung |
|-------|------|-------|---------|
| `listen` (früh) | 503 | 51 B | Ring leer / kein aktiver Stream |
| `stream` (früh) | 204 | 0 | noch nichts zu streamen |
| `listen2` | 200 `audio/mpeg` | 100 KiB | Browser-Listen nach Fill ok |
| `stream-sample2.mp3` | 200 | 12 KiB | gültiges MPEG (ID3 + MP3 56 kbps / 44.1 kHz mono) |

## Was das *nicht* sagt

- Kein Beweis für HU-Wiedergabe oder Live-Radio.  
- Kein Poti für Dauer-Ton — Engpass bleibt HU-Cursor/Stall (Freeze).  
- Feld-ESP `.89` war in dieser Nacht nicht Teil der Messung.

## Artefakte

- `burst-8s/`, `fieldrate-20s/`, `fieldrate-9k-25s/` — `REPORT.json` + Kurzbericht  
- `status-mid.json` — Status während/nach Fill  
- `listen*.bin`, `stream-sample*.mp3`, `*.headers`

## Nächster Schritt (Feld s3, morgen)

P-Quelle im Auto, nur ESP — siehe  
[`../../artifacts-2026-10-08-feld/FELDPROTOKOLL-P-QUELLE-ESP.md`](../../artifacts-2026-10-08-feld/FELDPROTOKOLL-P-QUELLE-ESP.md)  
Pocket: `feld-s3-prep/GO.md`.

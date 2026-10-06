# Feld AV — Operator (2026-10-06, kurz im Auto)

**Ziel:** Erstburst-Länge bei **gültigem MP3** + Ton (Ohr).  
**FW-Ziel:** `0.4.46-dev` (Bulk-Pump, Lab ~840 KB/s) — Feld war `0.4.45-dev`.  
**PASS:** `live>0 ∧ und=0 ∧ behind=0` anhaltend + hörbar.

---

## Vor dem Einsteigen (Laptop)

```bash
cd /home/martin/projects/pidrive
./tools/feld_av_session_prep.sh
# optional wenn .89 schon online:
./tools/feld_av_session_prep.sh --ota
```

Merke dir den ausgegebenen `OUT=.../feld-av-XXXX`-Ordner.

---

## Im Auto (Reihenfolge)

1. **Zündung / WLAN** — ESP `.89` pingbar:  
   `curl -sS http://192.168.178.89/api/status | python3 -c "import sys,json;d=json.load(sys.stdin);print(d['version'],d.get('playingUid'))"`

2. **OTA (falls noch 0.4.45):**  
   `./tools/feld_av_session_prep.sh --ota --skip-ssh --out <DEIN-OUT-ORDNER>`

3. **USB OTG** an HU — Scan abwarten, Favoriten sichtbar.

4. **Gate** (Pflicht):  
   `cd <OUT> && ./run-gate-check.sh`  
   Namen: Rock Antenne, Rock Antenne Bayern, Radio BOB!  
   Bridge-Log: erste `MSC_MAP_FROZEN` dieser Session sichern.

5. **RST** (empfohlen, sauberer Arm): ESP soft-RST oder Bridge-Neustart laut Abend-EAR — dann Gate erneut.

6. **Ein Sender** (z. B. Bayern) — **~30 s** abspielen, **Ohr** notieren.

7. **Correlate** (parallel starten beim Tippen):  
   `cd <OUT> && ./run-correlate.sh`  
   Danach: `cat correlate-run/burst-summary.json`

8. **Artefakte sichern:**  
   `status-*.json`, `correlate-run/`, Operator-Notiz in `OPERATOR-NOTES.txt`.

---

## Was wir aus dem Lauf lesen

| Größe | Bedeutung |
|-------|-----------|
| `hostAbs_delta` / `duration_s` | effektive Leserate |
| `max_host_step_bytes` | größter Sprung zwischen 0,5‑s-Samples (Burst-Hinweis) |
| `final.liveBytes` | echte Ring-Treffer |
| `final.underruns` | Silence-Bytes |
| `final.host_behind_base` | Cursor vor Fenster → nächster Read Miss |

**Entscheidung:** Erstburst ≤48 KiB + Ton → Bridge-Pfad plausibel. ≫248 KiB ohne Live → Slot/Geometrie, nicht nur Timing.

---

## Verboten / Freeze

- Kein Detect-Umbau, kein Lock-Code im Feld
- Kein AV-Interpret bei Gate FAIL
- Sequenz-GO bleibt gesperrt bis hörbar

Siehe auch [`FELD-ABEND-EAR-2026-10-05.md`](../artifacts-2026-10-05-feld/FELD-ABEND-EAR-2026-10-05.md).

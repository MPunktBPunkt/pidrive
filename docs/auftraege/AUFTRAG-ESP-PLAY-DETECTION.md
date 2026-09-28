# Auftrag: ESP USB-MSC — Menü-State & Live-Stream am BMW

**Stand:** 2026-09-28 Abend · aktiv  
**Repos:** `esp32.pidrive` (Firmware) + `tools/pump_bridge.py` · Abnahme im Fahrzeug  
**Feldbericht:** [`../betrieb/FELDTEST-ESP-MSC-BMW-2026-09-28.md`](../betrieb/FELDTEST-ESP-MSC-BMW-2026-09-28.md) · FW **0.4.24-dev**  
**Multi-Review:** Feldbericht §18 (Claude / GPT / Gemini / Grok)  
**Rohanalyse (alt):** [`../archiv/analysen/ANALYSE-ESP32-PLAY-DETECTION-GPT-2026-09-22.txt`](../archiv/analysen/ANALYSE-ESP32-PLAY-DETECTION-GPT-2026-09-22.txt)

---

## Symptom

Zwei getrennte Baustellen:

| ID | Symptom |
|----|---------|
| **A** | Menü-Navigation bricht „mitten durch“; Bridge loggt `stale/unknown uid` nach TCP-Reconnect |
| **B** | BMW zeigt korrekte Dateien (`PD0001`), spielt aber **Stub-Testton** aus dem HU-Cache — kein Live-FM/Web über MSC |

**Feld 2026-09-28:** Listing/LFN/Serial ok; `play.guess`/`play_uid` mehrfach (auch Auto-Play); Overlay liefert **0 Live-Bytes** an den Host (`streamBytes == underruns`); Bridge-Reconnects häufig (RSSI −76 dBm).

## Diagnose (aktuell)

| Frühere Hypothese | Stand |
|-------------------|--------|
| Host-Reads erfüllen Play-Detect nicht → kein `play.guess` | **widerlegt** für diesen Feldtest — Detector feuert |
| Stub-Cache + HU-Readahead → Overlay nie konsumiert | **bestätigt** (Baustelle B) |
| TCP-Reconnect verwirft Nav-State → `stale/unknown` | **bestätigt** (Baustelle A, Primär für Menü-UX) |

Listing-Leere durch FAT-Mutation ist **gelöst** (static FAT ab 0.4.12; Root-Destroy Fix **0.4.19**) — nicht erneut anfassen. Slot-Geometrie ist konsistent — nicht die Ursache.

---

## Iterationen

### I0 — Sichtbarkeit (Firmware 0.4.14–0.4.24)

- [x] Reject-Reason-Logging (`play.reject`)
- [x] Heuristik-Schwellen runtime/NVS-parametrierbar (Config/WebUI)
- [x] Bridge `[trace]` Timeline `play_uid → audio.start`
- [x] Host-Analyse / `msc.phase` / Feld-Korrelation
- [x] BMW-Trace mit Events (Feld 2026-09-28) → siehe Feldbericht
- [x] Diagnose von „Play-Detect-Engpass“ auf **A+B** umgestellt

### I1 — Feld-A/B (teils erledigt)

1. [x] `playPlugWindowMs` 2500 → 500 (+ `indexSettled_`, 0.4.22)
2. [ ] ~~`playMinSeqBytes` 6000 → 2048~~ — **zurückgestellt** (bringt für Audio nichts)
3. [~] SoftAP `/api/lab/play` — Stream armed, BMW hört Stub (Cache)
4. [x] Slot ≥512 KiB (0.4.21) — reicht allein nicht gegen Cache

### I2a — Baustelle A zuerst (P0)

- [ ] Bridge: Navigations-Snapshot über TCP-Reconnect **behalten**
- [ ] Grace-Period: UIDs aus letztem `menu_set` nach Reconnect weiter akzeptieren
- [ ] `menu sync deferred` ersetzen durch atomaren Snapshot + sofortiges `menu_set` des aktuellen Stands
- [ ] Feldtest: SoftAP-direkt oder UART priorisieren (weniger STA-Reconnects)
- [ ] Test: volle Menütiefe ohne Reconnect; dann Reconnect provozieren und Lookup loggen

### I2b — Baustelle B (P0 nach A bzw. parallel messbar)

- [ ] Pulse-Monitor vs. FM/DAB-Pipeline messen (`volumedetect` + ffmpeg-stderr)
- [ ] Stub: Silence-Frames + Xing/Info über Slot-Länge (nicht entkernen)
- [ ] Readahead-Messung (große Silence-Datei / FAT32)
- [ ] Pacing: bei leerem Ring Silence statt Nullen; Host ggf. busy/retry
- [ ] Cursor / feste ID3 statt rein absolutem Ring-Offset
- [ ] Warmup vor Overlay (`bufferTargetMs`); Serial **pro Attach** hochzählen (NVS)

### I3 — Warmup / Overlay-Härtung

- Overlay erst bei warmem Buffer; Underrun-/ffmpeg-Stabilität

## Abnahme

| ID | Kriterium | Stand 2026-09-28 |
|----|-----------|------------------|
| A1 | Dateiauswahl/Auto-Play → `play.guess` mit UID | **pass** |
| A2 | innerhalb weniger Sekunden Live-Audio (nicht Stub-Testton) | **offen** (B) |
| A3 | Listing bleibt während Stream sichtbar | **ok** |
| A4 | ≥2 Menüebenen + `page_next` ohne `stale/unknown` bei stabiler TCP-Session | **teilweise** (A) |

## Nicht jetzt

Volles Score-`looksLikePlayV2`, Host-Profil-Framework, PiDrive-Menü-Umbau, Play-Detect-Feintuning (`minSeqBytes`).

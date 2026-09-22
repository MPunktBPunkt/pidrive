# Auftrag: ESP Play-Detection / Live-Stream am BMW

**Stand:** 2026-09-22 · aktiv  
**Repos:** `esp32.pidrive` (Firmware) + `tools/pump_bridge.py` · Abnahme im Fahrzeug  
**Rohanalyse:** [`../archiv/analysen/ANALYSE-ESP32-PLAY-DETECTION-GPT-2026-09-22.txt`](../archiv/analysen/ANALYSE-ESP32-PLAY-DETECTION-GPT-2026-09-22.txt)

---

## Symptom

BMW sieht und spielt virtuelle/Demo-MP3s. Live-FM/Webradio über denselben MSC-Slot startet **nicht zuverlässig**.

## Hypothese

Kette reißt vorne ab: Host-Reads erfüllen `looksLikePlay()` oft nicht → kein `play.guess` / `play_uid` → Bridge startet keinen Live-Overlay. Verstärker: kleine Stub-Slots (~64 KiB) + Caching; sekundär kalter StreamBuffer.

Listing-Leere durch FAT-Mutation ist **gelöst** (static FAT ab 0.4.12) — nicht erneut anfassen.

## Iterationen

### I0 — Sichtbarkeit (Firmware 0.4.14-dev)

- [x] Reject-Reason-Logging (`play.reject`)
- [x] Heuristik-Schwellen runtime/NVS-parametrierbar (Config/WebUI)
- [x] Bridge `[trace]` Timeline `play_uid → audio.start`
- [ ] BMW-Trace mit Events korrelieren (Feld)

### I1 — Feld-A/B (nächste Fahrt)

Ein Parameter pro Versuch; Erfolg = `play.guess` + hörbarer Live-Ton:

1. `playPlugWindowMs` 2500 → 500 (oder 0 nach erstem DIR)
2. `playMinSeqBytes` 6000 → 2048
3. Bypass: SoftAP `/api/lab/play` — wenn Live hörbar → Audio/Overlay ok, Detector = Engpass
4. Slot-Größe ≥512 KiB (separater FW-Spike)

### I2 — gezielter Fix (nach I1-Daten)

- Candidate → Confirm / Prewarm
- größeres Stub-/Slot-Layout
- Bridge: Timeline `play_uid → activate → audio_start → first_bytes`

### I3 — Warmup (nur wenn Trigger ok, Ton trotzdem Stub)

- Overlay erst bei warmem Buffer bzw. Mindestpuffer vor `audio_start`

## Abnahme

| ID | Kriterium |
|----|-----------|
| A1 | Dateiauswahl am BMW → Event `play.guess` mit UID |
| A2 | innerhalb weniger Sekunden Live-Audio (nicht nur Stub-Testton) |
| A3 | Listing bleibt während Stream sichtbar (Regression static FAT) |

## Nicht jetzt

Volles Score-`looksLikePlayV2`, Host-Profil-Framework, PiDrive-Menü-Umbau.

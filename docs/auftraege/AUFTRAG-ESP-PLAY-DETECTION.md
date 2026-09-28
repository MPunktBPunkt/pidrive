# Auftrag: ESP Play-Detection / Live-Stream am BMW

**Stand:** 2026-09-28 · aktiv  
**Repos:** `esp32.pidrive` (Firmware) + `tools/pump_bridge.py` · Abnahme im Fahrzeug  
**Rohanalyse:** [`../archiv/analysen/ANALYSE-ESP32-PLAY-DETECTION-GPT-2026-09-22.txt`](../archiv/analysen/ANALYSE-ESP32-PLAY-DETECTION-GPT-2026-09-22.txt)  
**Feldbericht heute:** [`../betrieb/FELDTEST-ESP-MSC-BMW-2026-09-28.md`](../betrieb/FELDTEST-ESP-MSC-BMW-2026-09-28.md) · FW **0.4.24-dev**

---

## Symptom

BMW sieht und spielt virtuelle/Demo-MP3s. Live-FM/Webradio über denselben MSC-Slot startet **nicht zuverlässig**.

**Feld 2026-09-28:** Listing/LFN/Serial-Bump (`PD0001`) ok — Ton bleibt Stub-Testton bei Auto-Play; `play.guess`/`audio_start` kommen zeitweise, Overlay **underrunt** massiv.

## Hypothese

Kette reißt vorne ab: Host-Reads erfüllen `looksLikePlay()` oft nicht → kein `play.guess` / `play_uid` → Bridge startet keinen Live-Overlay. Verstärker: Stub-Cache + HU-Auto-Play; sekundär kalter/`underrun`-StreamBuffer nach `audio_start`.

Listing-Leere durch FAT-Mutation ist **gelöst** (static FAT ab 0.4.12; Root-Destroy Fix **0.4.19**) — nicht erneut anfassen.

## Iterationen

### I0 — Sichtbarkeit (Firmware 0.4.14-dev)

- [x] Reject-Reason-Logging (`play.reject`)
- [x] Heuristik-Schwellen runtime/NVS-parametrierbar (Config/WebUI)
- [x] Bridge `[trace]` Timeline `play_uid → audio.start`
- [x] Host-Analyse 0.4.17: SCSI-Zähler, `msc.phase`/`msc.quiet`, BOOT/FAT/DIR, Slot-Profile (Feld-Korrelation)
- [x] BMW-Trace mit Events korreliert (Feld 2026-09-28) → siehe Feldbericht

### I1 — Feld-A/B

Ein Parameter pro Versuch; Erfolg = `play.guess` + hörbarer Live-Ton:

1. [x] `playPlugWindowMs` 2500 → 500 (+ `indexSettled_` nach quiet, 0.4.22)
2. [ ] `playMinSeqBytes` 6000 → 2048
3. [~] Bypass SoftAP `/api/lab/play` — Stream armed, BMW hört Stub (Cache)
4. [x] Slot-Größe ≥512 KiB (0.4.21) — reicht allein nicht gegen Cache-Auto-Play

### I2 — gezielter Fix (nächster Schritt nach Feldbericht)

- Stub-Head entkernen / erzwingen Re-Read nach Cache
- Overlay-Warmup + Underrun-/ffmpeg-Härtung
- Bridge: Timeline `play_uid → activate → audio_start → first_overlay_read`

### I3 — Warmup (nur wenn Trigger ok, Ton trotzdem Stub)

- Overlay erst bei warmem Buffer bzw. Mindestpuffer vor `audio_start`

## Abnahme

| ID | Kriterium | Stand 2026-09-28 |
|----|-----------|------------------|
| A1 | Dateiauswahl am BMW → Event `play.guess` mit UID | teilweise |
| A2 | innerhalb weniger Sekunden Live-Audio (nicht nur Stub-Testton) | **offen** |
| A3 | Listing bleibt während Stream sichtbar (Regression static FAT) | ok |

## Nicht jetzt

Volles Score-`looksLikePlayV2`, Host-Profil-Framework, PiDrive-Menü-Umbau.

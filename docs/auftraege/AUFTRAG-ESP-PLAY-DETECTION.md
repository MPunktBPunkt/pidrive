# Auftrag: ESP USB-MSC — Menü-State & Live-Stream am BMW

**Stand:** 2026-09-30 Abend · aktiv  
**Repos:** `esp32.pidrive` (Firmware) + `tools/pump_bridge.py` · Abnahme im Fahrzeug  
**Feldbericht (einziger Review-Ort):** [`../betrieb/FELDTEST-ESP-MSC-BMW-2026-09-28.md`](../betrieb/FELDTEST-ESP-MSC-BMW-2026-09-28.md) — §3.10 v1 · §11.1–11.3 Feld · §11.2 ESP2 · §15 Messplan · FW **0.4.28-dev**  
**Rohanalyse (alt):** [`../archiv/analysen/ANALYSE-ESP32-PLAY-DETECTION-GPT-2026-09-22.txt`](../archiv/analysen/ANALYSE-ESP32-PLAY-DETECTION-GPT-2026-09-22.txt)

---

## Symptom

Zwei getrennte Baustellen:

| ID | Symptom |
|----|---------|
| **A** | Menü-Navigation bricht „mitten durch“; Bridge loggte `stale/unknown uid` nach TCP-Reconnect; HU-Play für Actions oft `seq_short`/`cooldown` |
| **B** | BMW zeigt korrekte Dateien, spielt **Stub-Testton** / Auto-Playlist — kein Live über MSC |

## Diagnose (aktuell)

| Frühere Hypothese | Stand |
|-------------------|--------|
| Host-Reads erfüllen Play-Detect nicht → kein `play.guess` | **widerlegt** für Stationen Feld 2026-09-28; **teilweise wahr** für Actions 2026-09-29 |
| Stub-Cache + HU-Readahead → Overlay nie konsumiert | **bestätigt** (B) |
| TCP-Reconnect verwirft Nav-State → stale/unknown | **bestätigt** (A) — Snapshot/Grace ok; Feld 2026-09-30 bedingt |
| Action/Zurueck: minSeq 6000 + Cooldown nach Auto-Play | **bestätigt** 2026-09-29 — Fix **0.4.26** |
| `hello_ok_until` blockiert `menu_set` nach 60 s | **behoben** 2026-09-30 |
| BMW zeigt neue MSC-Namen ohne OTG-Replug | **widerlegt** — Unplug nötig |
| Voller PiDrive-Dateibaum auf MSC | **verworfen** — v1 Snapshot/Slots |
| Serial `PDnnnn` steigt pro Unplug am Display | **NVS-Fix 0.4.27** — Feld Pass D noch offen; Lab `.88` Identity sticky |
| Pulse-Monitor = Stille bei FM/DAB | **widerlegt Lab 09-30** — Monitor trägt Webradio (−15 dB); Car-Only user-Pulse masked, System-Pulse ok |

---

## Iterationen

### I0 / I1

Siehe Feldbericht — Telemetrie, Plug-Window, 512 KiB Slots erledigt.

### I2a — Baustelle A (Feld 2026-09-30 Abend)

- [x] Snapshot resent nach `hello_ack`; UID-Grace 180 s; kein Blind-Audio bei unknown  
- [x] Serial-Bump bei Unplug (0.4.25) — Log ok; **Persistenz fehlt**  
- [x] Nav Play-Detect 0.4.26  
- [x] Fix `hello_ok_until` + Redeploy Pi  
- [x] Feld A–D Abend ([§11.3](../betrieb/FELDTEST-ESP-MSC-BMW-2026-09-28.md#113-feldtest-2026-09-30-abend-16371705--ad-mit-fix)): A bedingt, B/C Lab+OTG grün, D rot/bedingt  
- [x] **`remountGen_` in NVS** — FW **0.4.27-dev** (Feldtest Pass D nach OTA)  
- [ ] MSC-Export an **v1 Snapshot/Slots** halten (kein Vollbaum)  
- [ ] Produkt-PUMP-Link festlegen: SoftAP \| STA \| UART (Abnahme A5)  
- [ ] Folgeauftrag: atomarer `MenuSnapshot` (Grace = Übergang)

### I2b — Baustelle B (erst nach A-Rest; streng B0→B5)

- [x] **B0** Pulse — Lab 09-30: System-Pulse-Monitor ok (Tone/Webradio); siehe Feldbericht §15.2  
- [x] **B1** Readahead Lab-Host `.88`: 512 KiB Slot @ ~0,57 MB/s in 0,9 s; danach **0** Reads (wie NBT-Burst)  
- [x] **B2** Silence+Xing volle Slot-Länge — FW **0.4.28-dev** (Lab verifiziert; Feld Auto-Play)  
- [x] **B3** Pacing Underrun→Silence — FW **0.4.29-dev** (Lab: paced read `underruns≈0` bei ~Realtime)  
- [ ] **B4** Cursor / fester ID3-Kopf  
- [x] **B5** Warmup vor Overlay — FW **0.4.29** `msc.overlay_warm` ab 8 KiB Ring  
- [ ] Optional: 1-Slot-Geometrie vs. 3×512 KiB (Messung)  
- [x] Optional parallel: ESP2 Lab **`.88`** + Host-Burst/`lab_overlay_consume.py` am Proxmox

### I3

Warmup/Underrun-Härtung = B5; nicht vor B0/B1.

## Abnahme

| ID | Kriterium | Stand |
|----|-----------|-------|
| A1 | `play.guess` + UID | **pass** Stationen; Lab Actions ok; HU nach Quiet oft kein Guess |
| A2 | Live nach Warmup/Play-Read | **offen** (B0→B5) |
| A3 | Listing während Stream | **ok** |
| A4 | A/B/C ohne `unknown uid` | **bedingt grün** Abend 09-30 (§11.3) |
| A5 | Produkt-PUMP-Link dokumentiert | **offen** |

## Nicht jetzt

Vollbaum-MSC, Architektur-Reviews, Silence/Xing vor B0/B1 / vor Serial-NVS-Fix.

# Auftrag: ESP USB-MSC — Menü-State & Live-Stream am BMW

**Stand:** 2026-09-30 · aktiv  
**Repos:** `esp32.pidrive` (Firmware) + `tools/pump_bridge.py` · Abnahme im Fahrzeug  
**Feldbericht (einziger Review-Ort):** [`../betrieb/FELDTEST-ESP-MSC-BMW-2026-09-28.md`](../betrieb/FELDTEST-ESP-MSC-BMW-2026-09-28.md) — §3.10 v1-Zielbild · §11.1 Feld · §11.2 ESP2-Lab · §15 Messplan · FW **0.4.26-dev**  
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
| `hello_ok_until` blockiert `menu_set` nach 60 s | **behoben** 2026-09-30 Nachmittag (`pump_bridge.py` auf Pi deployed) |
| BMW zeigt neue MSC-Namen ohne OTG-Replug | **widerlegt** Feld 2026-09-30 — Unplug nötig |
| Voller PiDrive-Dateibaum auf MSC | **verworfen** — v1 = Snapshot/Slots ([Feld §3.10](../betrieb/FELDTEST-ESP-MSC-BMW-2026-09-28.md#310-zielbild-v1-review-konsens-2026-09-30--bmw-robustes-msc-menü)) |

---

## Iterationen

### I0 / I1

Siehe Feldbericht — Telemetrie, Plug-Window, 512 KiB Slots erledigt.

### I2a — Baustelle A (Code da, Feldtest teilweise)

- [x] Snapshot resent nach `hello_ack`; UID-Grace 180 s; kein Blind-Audio bei unknown  
- [x] Serial-Bump bei Unplug (0.4.25)  
- [x] Nav Play-Detect: `navMinSeqBytes=4096`, Cooldown nicht für action/folder (0.4.26)  
- [x] Feldtest 2026-09-30 mit 0.4.26 — A bedingt, C Lab grün, D bedingt ([§11.1](../betrieb/FELDTEST-ESP-MSC-BMW-2026-09-28.md#111-feldtest-2026-09-30-vormittag-0426))  
- [x] **Fix `hello_ok_until`** in `pump_bridge.py` + Redeploy Pi (2026-09-30)  
- [ ] Pass A/B nachziehen (HU-`play_uid` weiter Cache-limitiert)  
- [ ] MSC-Export an **v1 Snapshot/Slots** halten (kein Vollbaum)  
- [ ] Produkt-PUMP-Link festlegen: SoftAP \| STA \| UART (Abnahme A5)  
- [ ] Folgeauftrag: atomarer `MenuSnapshot` (Grace = Übergang)

### I2b — Baustelle B (erst nach A grün; streng B0→B5)

- [ ] **B0** Pulse (`tools/check_pulse_monitor.sh`)  
- [ ] **B1** Readahead-Messung (1 lange Silence-Datei)  
- [ ] **B2** Silence+Xing volle Slot-Länge  
- [ ] **B3** Pacing (Silence/Busy statt Nullen)  
- [ ] **B4** Cursor / fester ID3-Kopf  
- [ ] **B5** Warmup vor Overlay  
- [ ] Optional: 1-Slot-Geometrie vs. 3×512 KiB (Messung)  
- [ ] Optional parallel: ESP2@Debian + Host-Burst-Sim ([§11.2](../betrieb/FELDTEST-ESP-MSC-BMW-2026-09-28.md#112-lab-rolle-zweiter-esp-review-2026-09-30))

### I3

Warmup/Underrun-Härtung = B5; nicht vor B0/B1.

## Abnahme

| ID | Kriterium | Stand |
|----|-----------|-------|
| A1 | `play.guess` + UID | **pass** Stationen 09-28; Actions Lab ok; HU nach Quiet oft **kein** Guess (09-30) |
| A2 | Live nach Warmup/Play-Read (Zahl festlegen) | **offen** (B0→B5) |
| A3 | Listing während Stream | **ok** |
| A4 | A/B/C ohne `unknown uid` | **bedingt** 09-30 — Lab-Paging; `hello_ok_until`-Bug; OTG für HU-Namen |
| A5 | Produkt-PUMP-Link dokumentiert | **offen** |

## Nicht jetzt

Vollbaum-MSC, allgemeine Architektur-Reviews, Silence/Xing **vor** B0/B1 / vor A-Fix.

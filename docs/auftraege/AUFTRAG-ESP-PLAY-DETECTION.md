# Auftrag: ESP USB-MSC — Menü-State & Live-Stream am BMW

**Stand:** 2026-09-29 · aktiv  
**Repos:** `esp32.pidrive` (Firmware) + `tools/pump_bridge.py` · Abnahme im Fahrzeug  
**Feldbericht:** [`../betrieb/FELDTEST-ESP-MSC-BMW-2026-09-28.md`](../betrieb/FELDTEST-ESP-MSC-BMW-2026-09-28.md) · FW-Ziel **0.4.26-dev**  
**Multi-Review:** Feldbericht §18 · Plan-Schärfung §15.0–15.2 / §18.5  
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
| TCP-Reconnect verwirft Nav-State → stale/unknown | **bestätigt** (A) — Bridge-Fix da; Feldtest Pass B offen |
| Action/Zurueck: minSeq 6000 + Cooldown nach Auto-Play | **bestätigt** 2026-09-29 — Fix **0.4.26** |

---

## Iterationen

### I0 / I1

Siehe Feldbericht — Telemetrie, Plug-Window, 512 KiB Slots erledigt.

### I2a — Baustelle A (Code da, Feldtest teilweise)

- [x] Snapshot resent nach `hello_ack`; UID-Grace 180 s; kein Blind-Audio bei unknown  
- [x] Serial-Bump bei Unplug (0.4.25)  
- [x] Nav Play-Detect: `navMinSeqBytes=4096`, Cooldown nicht für action/folder (0.4.26)  
- [ ] **Feldtest A/B/C + Serial-D** mit FW ≥0.4.26 ([§15.0–15.1](../betrieb/FELDTEST-ESP-MSC-BMW-2026-09-28.md#150-mini-checkliste-vor-jedem-feldtest))  
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

### I3

Warmup/Underrun-Härtung = B5; nicht vor B0/B1.

## Abnahme

| ID | Kriterium | Stand |
|----|-----------|-------|
| A1 | `play.guess` + UID | **pass** (Stationen); Actions: Lab-Pass 2026-09-29, HU offen bis 0.4.26-Feld |
| A2 | Live nach Warmup/Play-Read (Zahl festlegen) | **offen** (B0→B5) |
| A3 | Listing während Stream | **ok** |
| A4 | A/B/C ohne `unknown uid` | **offen** |
| A5 | Produkt-PUMP-Link dokumentiert | **offen** |

## Nicht jetzt

Host-Profil-Framework, PiDrive-Menü-Umbau, Silence/Xing **vor** B0/B1.

# Maßnahmen aus hu-probe / Tech-Audit → PiDrive (2026-10-22)

**Quellen:**  
- [`technology-audit/docs/reports/2026-10-22-hu-probe-media-ladder.md`](../../../technology-audit/docs/reports/2026-10-22-hu-probe-media-ladder.md)  
- [`technology-audit/docs/reports/2026-10-21-hu-probe-psram-board-free.md`](../../../technology-audit/docs/reports/2026-10-21-hu-probe-psram-board-free.md)  
- hu-probe Feld: Trip-Upload Hang / Thread-Safety (`0.3.9`–`0.3.17`), free Offline `0.2.40`, Media-Leiter  
- Profil: [`hu-probe/profiles/bmw_nbt_evo.json`](../../../hu-probe/profiles/bmw_nbt_evo.json)

**Umsetzung:** Docs in diesem Repo + Firmware in `esphub/esp32.pidrive` **0.4.54-dev**.

---

## 1. Kurzfazit (was übernommen wird)

| Bereich | Maßnahme | Status |
|---------|----------|--------|
| Host-Grammatik | Media-Leiter FACTs (Head-160, TUR 2238,78 ms, Elevator, Vertrag Struktur+Head) in Matrix/Facts | Docs |
| Rejects | Prefetch-Lead 15 s auf demo_v1; „nur Ordnerstruktur“; TUR≈1 Hz als Idle-Konstante | Docs |
| PSRAM | `qio_qspi` + `BOARD_HAS_PSRAM`; Ring 160 KiB in PSRAM | FW 0.4.54 |
| Thread-Safety | `StreamBuffer::readAt` unter Mutex (R13); Pump `WiFiClient` Single-Owner-Kommentar | FW 0.4.54 |
| Debug | PanicTail + PhaseGate + DiagLog + HwInfo → `/api/status`, `/api/diag/log` | FW 0.4.54 |
| Producer-Vertrag | ≥ ~80 KiB gültiger Dateikopf; Body dynamisch unter Size/EOF | Docs + Ring-Headroom |

**Nicht** übernommen: Offline-Capture/TripStore/Collector-Stack (Messpfad bleibt hu-probe).

**Nicht** annehmen: PSRAM heilt USB↔WiFi-Coex (Audit FACT).

---

## 2. PiDrive-Vertrag (Media-Leiter)

```text
Directory/FAT  → stabil
File head      → ~80 KiB gültig (typ. READ10 32+128 = 160 Blöcke)
Kleine Files   → oft schon im Scan vollständig gelesen
Großer Rest    → Prefetch/Bulk später, Size/FAT/EOF konsistent
Browse UI      → aus Directory (8.3)
Player UI      → ID3 aus Head (nicht Dir-Name)
```

**REJECTED:** „HU liest nur Ordnerstruktur.“

---

## 3. Firmware-Änderungen (`esp32.pidrive` 0.4.54-dev)

1. **PSRAM an** in allen Envs (`board_build.arduino.memory_type = qio_qspi`, `-DBOARD_HAS_PSRAM`).
2. **`HuMem` / `StreamBuffer`:** Ring + ID3 prefer-PSRAM; Cap 160 KiB wenn PSRAM da (sonst 48 KiB DRAM).
3. **R13:** `push` / `readAt` / Cursor / ID3 unter demselben `portMUX`.
4. **Diagnostik (hu-probe-Muster):**
   - `PanicTail` — RTC-Breadcrumbs (USB mount/umount, soft-detach, stall, OTA, restart)
   - `PhaseGate` — ENTER/PASS für Soft-USB / OTA; `last_crash` nach Reset
   - `DiagLog` — Serial + PSRAM-Ring + RTC-Tail; `GET /api/diag/log`
   - `HwInfo` — Modul `N8R2` auch wenn Build früher PSRAM aus hatte
5. **PumpServer:** dokumentierte Ownership-Regel (kein zweiter Task auf `WiFiClient`; Mutex statt Critical um TCP).

Feld-Check nach Flash: `/api/status` → `hw.psram.build_enabled=true`, `psramSize>0`, `stream.cap=163840`, `panic_tail` / `phase_gate` vorhanden.

---

## 4. Docs / Profile (dieses Repo)

| Datei | Änderung |
|-------|----------|
| [`fahrzeug/HU-PARAMETER-MATRIX-2026-10-16.md`](../fahrzeug/HU-PARAMETER-MATRIX-2026-10-16.md) | Media-Leiter FACTs, Rejects, PSRAM an |
| [`fahrzeug/HU-Technical-Facts.md`](../fahrzeug/HU-Technical-Facts.md) | Phasenmodell, Head-160, TUR idle, Vertrag |
| [`referenz/ESP32-S3-BOARD.md`](../referenz/ESP32-S3-BOARD.md) | PSRAM Build an |
| [`betrieb/MSC-AKTUELL.md`](../betrieb/MSC-AKTUELL.md) | Einstieg auf 22.10. Stand |
| [`planung/Stufenplan.md`](Stufenplan.md) | R13 erledigt; PSRAM Option b entblockt |
| [`tools/profiles/nbt_evo_media_ladder_2026-10-22.json`](../../tools/profiles/nbt_evo_media_ladder_2026-10-22.json) | Transport+Host-Grammar Profil |

---

## 5. Offen (nicht in diesem Schnitt)

- Cache-Key / Identity F0 (`ident_*`, Feldplan 0.3.18) — weiter hu-probe zuerst  
- Prefetch-Lead als **VARIABLE** (nicht 8 s / 15 s Konstante) — Audible-Tap  
- A8 / `seq_size` formal OPEN  
- Option-b Zeitversatz-Producer (≥512 KiB Vergangenheit) — PSRAM jetzt da, Logik noch nicht

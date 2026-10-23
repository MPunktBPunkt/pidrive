# ESP32-S3 Board — Speicher / Modul (Feld & Lab)

**Stand:** 2026-10-22  
**Board:** ESP32-S3-DevKitC-1 · Modulvariante **N8R2**  
**Firmware:** `esp32.pidrive` **0.4.54-dev** / `hu-probe` ≥0.2.35  
**Beleg:** Laufzeit `hw` in `/api/status` (`module`, Flash-/PSRAM-/Heap-Felder); Naming Espressif DevKitC-1-N8R2 = WROOM-1 mit 8 MB Quad-Flash + 2 MB Quad-PSRAM

Kurz: Hardware hat **8 MiB Flash + 2 MiB PSRAM**. Ab **esp32.pidrive 0.4.54** und hu-probe ≥0.2.35 ist PSRAM im Build **aktiviert** (`qio_qspi` + `BOARD_HAS_PSRAM`).

---

## 1. Kurzüberblick

| Feld | Wert |
|------|------|
| Chip | ESP32-S3 |
| Modul | **N8R2** |
| Package | QFN56 |
| CPU | 240 MHz |
| Flash | 8 MiB (voll nutzbar) |
| PSRAM physisch | 2 MiB (eFuse) |
| PSRAM im Build | **an** (`build_enabled: true`) → Laufzeit typ. 2 MiB |

### Was bedeutet N8R2?

- **N8** = 8 MB Flash  
- **R2** = 2 MB PSRAM (Quad-SPI, 3,3 V)

---

## 2. Build (SoT)

```ini
board_build.arduino.memory_type = qio_qspi
board_upload.flash_size = 8MB
build_flags = … -DBOARD_HAS_PSRAM
```

| Schlüssel (`/api/status` → `hw.psram`) | Erwartung ab 0.4.54 |
|----------------------------------------|---------------------|
| `bytes_efuse` | `2097152` |
| `bytes_enabled` | `> 0` (typ. 2 MiB) |
| `build_enabled` | `true` |
| `memory_type_needed` | `qio_qspi` |

Stream-Ring: bei PSRAM **160 KiB** (sonst Fallback 48 KiB DRAM) — siehe `StreamBuffer`.

---

## 3. Flash

| | |
|--|--|
| Real / Configured | 8 MiB / 8 MiB |
| JEDEC (Beispiel) | `0x204017` (XMC/Micron) |

---

## 4. PSRAM — wofür / wofür nicht

| Nutzen | Ja |
|--------|----|
| Live-Ring / Option-b Zeitversatz-Puffer | ja |
| DiagLog-Ring, sticky ID3 | ja |
| hu-probe Offline-Capture 1 MiB | ja (Messpfad) |

| Nicht | |
|-------|--|
| USB↔WiFi-Coex „heilen“ | **nein** (Audit 2026-10-21 FACT) |

---

## 5. Bezug

| Thema | Wo |
|-------|----|
| Maßnahmen-Schnitt | [`planung/MASSNAHMEN-HU-PROBE-2026-10-22.md`](../planung/MASSNAHMEN-HU-PROBE-2026-10-22.md) |
| PSRAM-Audit | [`technology-audit/…/2026-10-21-hu-probe-psram-board-free.md`](../../../technology-audit/docs/reports/2026-10-21-hu-probe-psram-board-free.md) |
| Parametermatrix | [`fahrzeug/HU-PARAMETER-MATRIX-2026-10-16.md`](../fahrzeug/HU-PARAMETER-MATRIX-2026-10-16.md) |
| Schaltplan Dual-USB | [Espressif SCH DevKitC-1 v1.1](https://dl.espressif.com/dl/schematics/SCH_ESP32-S3-DevKitC-1_V1.1_20220413.pdf) |

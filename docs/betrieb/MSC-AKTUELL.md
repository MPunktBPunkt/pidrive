# MSC / BMW — aktueller Stand (Lesereihenfolge)

**Stand:** 2026-10-22 — Media-Leiter + PSRAM + Debug-Port in esp32.pidrive **0.4.54-dev**  
**Phase:** Host-Grammatik (hu-probe) geschärft → PiDrive-Vertrag Struktur+Head; Identity F0 / Audible-Lead weiter offen

Dies ist der **Einstieg**, wenn du wissen willst, wo wir stehen und warum.

---

## 1. Jetzt lesen (normativ)

| # | Dokument | Rolle |
|---|----------|--------|
| 0 | [`planung/MASSNAHMEN-HU-PROBE-2026-10-22.md`](../planung/MASSNAHMEN-HU-PROBE-2026-10-22.md) | **Maßnahmen-Schnitt** hu-probe → PiDrive/FW |
| 1 | [`fahrzeug/HU-PARAMETER-MATRIX-2026-10-16.md`](../fahrzeug/HU-PARAMETER-MATRIX-2026-10-16.md) | Ops-Matrix (Head-160, TUR 2239 ms, Rejects) |
| 2 | [`fahrzeug/HU-Technical-Facts.md`](../fahrzeug/HU-Technical-Facts.md) | Normative HU-Fakten |
| 3 | [`planung/Stufenplan.md`](../planung/Stufenplan.md) | Stufen 0–6 / Stall-Hebel |
| 4 | [`referenz/ESP32-S3-BOARD.md`](../referenz/ESP32-S3-BOARD.md) | N8R2, **PSRAM an** |
| 5 | [`../../tools/profiles/nbt_evo_media_ladder_2026-10-22.json`](../../tools/profiles/nbt_evo_media_ladder_2026-10-22.json) | Host-Grammar-Profil |
| 6 | Tech-Audit Reports | [`media-ladder`](../../../technology-audit/docs/reports/2026-10-22-hu-probe-media-ladder.md) · [`psram`](../../../technology-audit/docs/reports/2026-10-21-hu-probe-psram-board-free.md) |

Historische Lab/Feld-Ketten (Okt 4–17) bleiben unter `artifacts-2026-10-*` — nicht als aktuelle Ampel lesen.

---

## 2. Ampel (22.10.)

| Thema | Stand |
|-------|--------|
| Track-Atom 240+69 | **grün** [B] |
| Head-Scan 32+128=160 (~80 KiB) | **grün** [B] |
| TUR idle 2238,78 ms | **grün** [B] |
| PiDrive-Vertrag Struktur+Head | **grün** (Soll) |
| Prefetch-Lead Konstante (8/15 s) | **rot/verworfen** — Lead VARIABLE / demo_v1=0 |
| „Nur Ordnerstruktur“ | **REJECTED** |
| PSRAM Build (esp32.pidrive) | **grün** ab 0.4.54 |
| StreamBuffer R13 Mutex | **grün** ab 0.4.54 |
| PanicTail / PhaseGate / DiagLog | **grün** ab 0.4.54 |
| Identity / Cache-Key F0 | **gelb** — hu-probe Identity-Plan |
| Option-b Zeitversatz-Producer | **gelb** — PSRAM da, Logik offen |
| USB↔WiFi Coex | **offen** (PSRAM heilt das nicht) |

---

## 3. Feld-Smoke nach 0.4.54-Flash

1. `/api/status` → `hw.psram.build_enabled=true`, `psramSize>0`, `stream.cap` ≈ 163840  
2. Nach Soft-Remount/OTA: `panic_tail` / `phase_gate.last_crash` prüfen  
3. `GET /api/diag/log` liefert Text (PSRAM-Ring oder leer wenn kein PSRAM-Ring)

---

## 4. Architektur (kurz)

| Schicht | Repo | Rolle |
|---------|------|--------|
| Pi-Brain | `pidrive` | Quellen, Encode, PUMP-Client, Docs/Tools |
| MSC-Gadget | `esphub/esp32.pidrive` | TinyUSB MSC + Stall + Stream-Ring |
| Messsonde | `hu-probe` | Host-Oracle (CBW/Atom/Offline) |
| Evidence | `technology-audit` | Sheets / Audits / Reports |

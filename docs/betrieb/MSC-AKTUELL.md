# MSC / BMW — aktueller Stand (Lesereihenfolge)

**Stand:** 2026-11-07 — HU-Beschreibung ergänzt; Facts (Heimfahrt R46–R52, Analyzer E18/F15); Größenleiter Q16 weiter offen (27.10. Capture-Fail); Lab PiDrive **0.4.60+**  
**Phase:** Soft-Paging abgelöst; Soft-Remount **REJECTED**; Prefetch-Lead-Konstante **REJECTED**; Eager ≠ Play; **P0 = Audible + Größenleiter-Retest**  
**Feld / Audits:** [`GO Größenleiter`](../../../hu-probe/docs/feld/MSC-GROESSENLEITER-GO.md) · [`Heimfahrt`](../../../hu-probe/docs/feld/MSC-HEIMFAHRT.md) · [`Analyzer-Feldmatrix`](../../../usb-analyzer/docs/reports/2026-11-06-field-host-matrix.md) · [`Cross-Check`](2026-11-02-esp-usb-analyzer-crosscheck.md)

Dies ist der **Einstieg**, wenn du wissen willst, wo wir stehen und warum.

---

## 1. Jetzt lesen (normativ)

| # | Dokument | Rolle |
|---|----------|--------|
| 0 | [`planung/MENUESTRUKTUR-MSC.md`](../planung/MENUESTRUKTUR-MSC.md) | **Finales MSC-Menü-Zielbild** (Baum, Cycle, Stall) |
| 1 | [`planung/MASSNAHMEN-MSC-FULLMENU.md`](../planung/MASSNAHMEN-MSC-FULLMENU.md) | Maßnahmen-Schnitt 23.10. + FW 0.4.55 |
| 2a | [`archiv/planung/MASSNAHMEN-HU-PROBE-2026-10-22.md`](../archiv/planung/MASSNAHMEN-HU-PROBE-2026-10-22.md) | Archiv: Vortag Media-Leiter / PSRAM |
| 3 | [`fahrzeug/HU-Technical-Facts.md`](../fahrzeug/HU-Technical-Facts.md) | Normative HU-Fakten (R37–R52, E18) |
| 3a | [`fahrzeug/HU-BESCHREIBUNG.md`](../fahrzeug/HU-BESCHREIBUNG.md) · [`fahrzeug/README`](../fahrzeug/README.md) | Narrative Zwei-Plane + Lesereihenfolge |
| 4 | [`fahrzeug/HU-PARAMETER-MATRIX.md`](../fahrzeug/HU-PARAMETER-MATRIX.md) | Ops-Matrix |
| 5 | [`planung/Stufenplan.md`](../planung/Stufenplan.md) | Stufen 0–6 / Stall-Hebel |
| 6 | [`referenz/ESP32-S3-BOARD.md`](../referenz/ESP32-S3-BOARD.md) | N8R2, **PSRAM an** |

---

## 2. Ampel (23.10.)

| Thema | Stand |
|-------|--------|
| Track-Atom 240+69 | **grün** [B] |
| Head-Scan 32+128 (+EOF Fresh) | **grün** [B] |
| Soft-Remount als HU-Reset | **rot** — wirkungslos (R37) |
| Serial/Label/Vol als Resume-Key | **rot** — REJECTED (R34) |
| Cycle → FS-Enum + Body-Atom, kein Fresh | **grün** [B] |
| PiDrive: Menü via D+-Cycle | **grün** ab 0.4.55 |
| PiDrive: FULLMENU (Dir komplett, Body dynamisch) | **grün** ab 0.4.56 |
| PiDrive: Zielbaum Root+7 Ordner (`0ZULETZT`…) | **grün** ab 0.4.57 (Lab `.88`) |
| Stall + lead 120 KiB + `msc.tone` | **grün** Lab `.88` ab 0.4.58 |
| Bridge-Preroll (Ring vor Prefill-Ende) | **grün** Lab `.88` — `pump_bridge --preroll-bytes` / `lab_live_preroll_smoke` |
| Zuletzt-ID3 über Boot | **grün** ab 0.4.60 — SPIFFS `/zuletzt.id3`, MSC-Head idle; `lab_zuletzt_id3_persist` |
| Fresh als Betriebsmodus | **nicht nötig** — P1 nur Mess-Trigger |
| Remount ≠ Cold Start / Eager≠Play (Heimfahrt) | **grün** R46–R50 |
| Prefetch-Lead 8/15 s Konstante | **rot** — REJECTED (R49); Lead kontextabhängig |
| Stall-Toleranz (BUSY) | **grün** E7/R29/R51 — Arbeitsgrundlage Backpressure; Q1 nur Rest |
| CBW ≠ Callback (240 vs 4 KiB) | **grün** E5/E11 — Timing an CBW-Datenphase |
| Analyzer-MSC mountet an NBT (kein UI ohne FAT) | **grün** E18/F15 |
| Größenleiter ≫158 KiB | **gelb** — Q16 Mess-Retest (27.10. Fail) |
| Audible / Play-Intent GATE-01 | **gelb** — P0 |
| Option-b Zeitversatz-Producer | **gelb** — PSRAM da, Logik offen |

---

## 3. Vertrag (kurz)

1. **Dir/FAT** = komplettes Menü-Niveau (≤32 Dateien à 160 KiB), nicht Soft-Paging.  
2. **Dateiköpfe** ≥ ~80 KiB gültig.  
3. **Bodies** dynamisch (Live-Overlay / Silence) — nach Cycle/Auswahl liest die HU neu.  
4. Host-Reread bei Strukturwechsel = **USB-Cycle (D+)**, nicht Soft-Hide.

Zielbaum / Quellordner / Stall-Rollen: [`planung/MENUESTRUKTUR-MSC.md`](../planung/MENUESTRUKTUR-MSC.md).

---

## 4. Feld-Smoke nach 0.4.57-Flash

1. `/api/status` → `0.4.57-dev`, `slots=32`  
2. `/api/menu` → Pfade `0ZULETZT.MP3`, `FAVORIT/…`, `DAB/…`, `STEUER/…`  
3. Bridge/`menu_set` mit `path` → Event `msc.cycle`; Host re-enum  
4. Lab-Host/HU: Root zeigt `0ZULETZT` + Ordner FAVORIT/DAB/FM/MP3/SCANNER/AIRBAND/STEUER

# Plan nach Auto-M3 — A_then_E (Rev.3, 2026-10-03)

**Basis:** [`GESAMTBERICHT-AUTO-M3-NACH-REVIEW-2026-10-03.md`](artifacts-2026-10-03-m3/GESAMTBERICHT-AUTO-M3-NACH-REVIEW-2026-10-03.md) · Addendum · Semantik [`MSC-STATUS-SEMANTIK-0.4.42.md`](MSC-STATUS-SEMANTIK-0.4.42.md)

**Enger Befund (D):** `A_then_E_within_observed_window`.  
**Vollscan 8 MiB unique:** wahrscheinlich (**H**), nicht D.  
**Export-Unique ~4 MiB:** Untergrenze, **kein** Cache-Inhalt.

---

## 0. Vor dem Feld: Lab-Kalibrierung (P0, Pflicht) — **PASS 2026-10-03**

Artefakte: [`artifacts-2026-10-03-m3/lab88-export-calib-1835/`](artifacts-2026-10-03-m3/lab88-export-calib-1835/) · Tool `tools/m3_lab_export_calib.py`

### Kalibrierung A — Pre-Connect — **PASS**
- **A1** Bridge-up: `Δrc=64 = Σn`, `ov=0`, Export vollständig.  
- **A2** Blind (TCP down): `blind_rc=256`, `export_frac=0.0`, `ov=0`, `ΔreadsEmit=0` → Pre-Connect-Lücke bestätigt (kein Overflow).

### Kalibrierung B — Burst (`kBurstGapMs=50`) — **PASS**
Gaps **10 / 50 / 100 ms**: je `Δrc=48 = Σn`, `ov=0`, Export vollständig. Aggregation nur Zeilenzahl (14–16), nicht Vollständigkeit.

**Operator:** Bridge-TCP up **vor** Remount/Plug/Stimulus. Negatives Q2 ohne A+B gilt **nicht** als HU-Beweis — A+B sind jetzt lab-erledigt.


---

## 1. Drei Fragen

| ID | Frage |
|----|--------|
| **Q1** | Select ohne Remount → neue MSC-Reads? |
| **Q2** | Natürliches Trackende / Auto-Next → neue Reads? |
| **Q3** | Dabei frische (geänderte) Inhalte? |

**S0–SR** pro Arm (nicht ein Gesamtlabel).

---

## 2. Feldarme

1. **Arm1 Select** — Idle 30 s → A/B/C; kein OTG.  
2. **Arm2 Trackende** — kurze **hörbare** Titel; nicht manuell umschalten.  
3. **Arm3 Remount** — Soft-Remount separat.

Bridge vor Messfenster up. Kurze Dateien erzwingen **keine** Frische.

### Optional P1b
fav1 512 KiB (~87 s) passiv Trackende — Indikator, kein Q2-Ersatz.

---

## 3. Nach M3seq

| Ergebnis | Folge |
|----------|--------|
| S4 | Chunk vertiefen |
| nur SR | Remount skizzieren |
| S0∧¬S3 | Chunk ohne Stimulus schwach |
| kalibriert negativ | BT-Hybrid als Produktoption diskutieren |

**Langpass:** erst danach; bei Vollscan-H eher **≥25 min** @48 k + Marge — ersetzt M3seq nicht.  
**L4:** eigene Frage nach FAT-Validierung.

---

## 4. Eingefroren

Ring, PSRAM, Pacing, Remount-Impl, BT-Hybrid-Code, Live-als-M3, L4 parallel.

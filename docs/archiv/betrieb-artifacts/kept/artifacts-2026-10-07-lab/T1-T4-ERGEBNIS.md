# Lab-Probe T1–T4 Ergebnis (Feld-s2-Vorbereitung)

**Stand:** 2026-10-07 ~17:00 · ESP `.88` · FW 0.4.46-dev · Host LXC `.187`  
**Artefakte:** `docs/betrieb/artifacts-2026-10-07-lab/lab88-s2probe/`  
**Auftrag:** [`AUFTRAG-LAB-S2-PROBE-T1-T4.md`](AUFTRAG-LAB-S2-PROBE-T1-T4.md)

---

## Kurzüberblick

| Test | Ergebnis | Kernzahl |
|------|----------|----------|
| T1 Trace 4 Hz | **teilweise** | G7+Poll PASS, `sg_p50=4,0`; `lost` hoch (666 / ~33 %) |
| T1 Trace 3 Hz | **teilweise** | G7 PASS, `sg_p50=4,0`; `lost` 147 / ~6,6 % (Ziel &lt;0,5 %) |
| T2 armed fav0 → read fav1 | **PASS** | `sg_p50=4,0 ms` (wie Idle) → Kosten am **Live-Slot** |
| T3 C4b GW OOO + Live | **Messung ok / Mapping FAIL feste Zuordnung** | 207 LIVE; `abs0−off` **nicht** konstant (53 Werte) |
| T4 Generalprobe | **teilweise** | REPLAY PASS; Q8 zeigt `F8 B120…F968`; kein Pi-Bridge/`run-s2.sh` hier |

**Empfohlene Feld-Poll-Rate:** vorerst **4 Hz** (wie spezifiziert); Lücken unter Lab-G7 bleiben &gt;0,5 %. Im Feld HU-Last beobachten; bei `lost`≫0 → 5–8 Hz oder Trace nur während der Rampe. SoftAP/UART für Status parallel erwägen.

---

## T1 — Trace-Poll vs. SG-Dauer

### Mit Poll 4 Hz (`T1-1600/`)

| Größe | mit Poll | ohne Poll (bare, sticky maxSeq → G7 FAIL) |
|-------|----------|-------------------------------------------|
| `sg_duration p50` | **4,0 ms** | **4,0 ms** |
| G7 | PASS | FAIL (kein Soft-RST dazwischen) |
| Trace rows / lost | 1433 / **666** | — |

`sg_p50` unverändert → Poll verfälscht R15 **nicht** (±0 ms). Lücken: Abnahme &lt;0,5 % **nicht** erreicht.

### Mit Poll 3 Hz (`T1-3hz-1650/`)

| Größe | Wert |
|-------|------|
| G7 | PASS |
| `sg_p50` | 4,0 ms |
| lost / ΔreadCount | 147 / 2224 ≈ **6,6 %** |
| Poll-Intervall p50 | ~328 ms (Soll 333 ms) |

**Deutung:** Ring 96 × 4 KiB @ ~200 Reads/s ≈ 480 ms — 3–4 Hz sollte reichen; unter Remount/Burst und WLAN-Jitter entstehen trotzdem Drops. Für Q8 im Feld trotzdem nutzbar (Muster sichtbar); quantitative Lückenfreiheit nicht Lab-grün.

---

## T2 — C2-Zelle: armed fav0, Lesen fav1

`T2-1605/` (je 2×, Soft-RST dazwischen):

| Zustand | sg_duration p50 | rps |
|---------|-----------------|-----|
| idle (C2 1209) | **4,0** | ~195 |
| armed fav0, Lesen fav0 (C2) | **5,0** | ~160 |
| armed+prod fav0, Lesen **fav1** | **4,0** | ~178 |
| armed-noprod fav0, Lesen **fav1** | **4,0** | ~181 |

**Abnahme:** ≈ 4,0 ms → die +1 ms hängen am **Live-Slot-Read-Pfad**, nicht am globalen Play-/Producer-Zustand. Index-Reads anderer Dateien bleiben schnell.

---

## T3 — C4b: `abs0−off` bei OOO + Live

`T3-1616/` — GW `--live fav0 --live-prefill-s 30 --period-ms 700 --gw-no-eof`  
Wi-Fi brach am Ende ab (kein `REPORT.json`), aber `reads.jsonl` vollständig genug:

| Kennzahl | Wert |
|----------|------|
| Reads | 491 |
| LIVE mit abs0 | **207** (≥100 ✓) |
| unique `abs0−off` | **53** (nicht konstant) |
| Plateaus | z. B. −415744 (mehrere Reads), später −23296 |

**Deutung:** Heutige FW (zählender Cursor 0.4.46) liefert bei OOO **keine** feste Dateioffset→Stromoffset-Zuordnung. Das ist die Testvorlage für Stufe 3.2 nach Go: gleiche Lesereihenfolge, Erwartung dann `abs0−off = const`.  
CSV: `T3-1616/C4b-MAPPING.csv`, Summary: `C4b-SUMMARY.json`.

---

## T4 — Generalprobe (ohne Pi-Bridge)

`T4-1657/`:

| Schritt | Ergebnis |
|---------|----------|
| Soft-RST + Trace 4 Hz + REPLAY 364034–365907 | **PASS** (`replay/REPORT.json`) |
| `feld_q8_msc_order.py --reads` (Feld-Datei) | Muster **`F8 B120 B120 F360 B360 F968`**, Verdict `r16_resume_like`, Jump-Bursts resolved |
| `run-s2.sh` / Bridge `--no-audio` / marks.jsonl | **nicht** auf diesem Host (kein `pump_bridge` / systemd) — im Feld mit `feld-s2-prep/run-s2.sh` |

Bugfix: `no_slot_reads` ohne `stall_implication` → behoben in `feld_q8_msc_order.py`.

---

## Doc / B1

C1-Abnahme in [`C1-C7-ERGEBNIS.md`](C1-C7-ERGEBNIS.md) auf N1 umgestellt: **PASS** bei `sg_duration p50 ≤ 4,1 ms`; Wanduhr-Reads/s nur Host-Metrik.

---

## Für den Feldtermin

1. Trace-Poll mitlaufen lassen (4 Hz Start); `lost` im `*.polls.jsonl` nach Teil A prüfen.
2. Q8: `./run-q8.sh` bzw. `feld_q8_msc_order.py --reads … --trace …`.
3. T2-Befund mitnehmen: fremde Slots bleiben bei 4 ms — Stall-Budget nur für Live-Slot-Pfad kritisch.
4. Stall-FW weiter Freeze bis F1 + R10.

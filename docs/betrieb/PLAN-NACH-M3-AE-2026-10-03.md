# Plan nach Auto-M3seq — Trace-Korrektur (Rev.4, 2026-10-04)

**Normativer Gesamtbericht:** [`GESAMTBERICHT-AUTO-M3SEQ-TRACE-KORREKTUR-2026-10-04.md`](artifacts-2026-10-03-m3/GESAMTBERICHT-AUTO-M3SEQ-TRACE-KORREKTUR-2026-10-04.md)  
**Semantik:** [`MSC-STATUS-SEMANTIK-0.4.42.md`](MSC-STATUS-SEMANTIK-0.4.42.md)  
**Feld:** [`auto89-m3seq-2042/`](artifacts-2026-10-03-m3/auto89-m3seq-2042/) · Gegenindiz [`replug-1231-noselect/`](artifacts-2026-10-03-b7/replug-1231-noselect/)

---

## 0. Enger Befund (nach Voll-Trace, V)

| Aussage | Status |
|---------|--------|
| Warmes Auto-Next / Trackende → Δrc=0 | ✅ gültig gemessen, **kein** Architektur-Negativ |
| Select / Erstabspiel → Voll-Burst (~1 MB/s) | ✅ mehrfach (V) |
| Mount-Scan = nur Köpfe (+ ggf. eine volle kleine Datei) | ✅ (V) |
| Remount → Resume-Vollread ohne Select | ✅ (V) |
| Kaltes Auto-Next liest | 🔜 P1 (Morgenpass Indiz positiv) |
| Payload-Frische (Q3) | 🔜 Lab |
| MSC-Live als unendliche Overlay-Datei | weiterhin ungestützt |
| MSC-Sequenz (N Chunk-Dateien) | bedingt first-class bis P1 |

**Arbeitsmodell:** Eine Datei, ein Voll-Read beim ersten Start pro Mount.

---

## 1. Lab-Kalibrierung — unverändert PASS

A+B + M3seq-Rehearsal: siehe Rev.3. Operator: Bridge vor Plug. Neu: **Pre-Flight-Warmheits-Check** vor jedem Trigger-Fenster.

---

## 2. Offene Fragen (neu priorisiert)

| ID | Frage | Nächster Nachweis |
|----|--------|-------------------|
| **Q2c** | Liest kaltes Auto-Next Body-LBAs — und wann relativ zum Übergang? | P1 Feld 15 min |
| **Q3** | Liefert der Start-Read frische Bytes (A→B)? | P2a Lab |
| **Q1** | Select-Trigger | ✅ erledigt |
| **Q2w** | Warmes Auto-Next | ✅ Δrc=0, konfundiert für Kälte |

---

## 3. Arbeitsplan

| Prio | Arbeit | Done wenn |
|------|--------|-----------|
| **P0** | Menü-Lock / MSC-Session-Lock | Pi-UI überschreibt MSC-Namen nicht während USB-Session; Regressionstest |
| **P1** | Kalter Auto-Next Feld | Trace: kaltes Ziel, Timing, Δrc/LBA; Warmheits-Preflight dokumentiert |
| **P2a** | Q3 Lab A/B | Hash-Kette + Marker, B-Bytes belegt |
| **P2b** | BT-Abnahme inkl. Quellwechsel-UX | Checkliste pro Punkt |
| **P3** | Sequenz-Prototyp | nur nach P1 grün; dann Ring ≥ 1 Chunk erlaubt |
| **P4** | Connected-Apps / 6NR | nur Notiz/Check, kein Sprint |

**Entscheidungsregel:** P1+P2a grün → Hauptpfad Sequenz (A), BT als Fallback. Sonst → BT-Hybrid (B). Pfad C nur wenn B-UX scheitert und 6NR aktiv.

---

## 4. Eingefroren (bis P1 grün)

Ring-Vergrößerung, PSRAM-Streaming, Pacing, Remount-Karussell-Impl, Live-Overlay-Optimierung, AAIdrive-Port.

**Ausnahme nach P1 grün:** einmaliger, begründeter Ring ≥ Chunk-Größe für Sequenz-Prototyp.

# Plan nach Auto-M3 — A_then_E (Rev.2, 2026-10-03)

**Basis:** [`AUTO-M3-FELD-2026-10-03.md`](artifacts-2026-10-03-m3/AUTO-M3-FELD-2026-10-03.md) · Korrektur [`AUTO-M3-ADDENDUM-KRITIK-2026-10-03.md`](artifacts-2026-10-03-m3/AUTO-M3-ADDENDUM-KRITIK-2026-10-03.md) · Semantik [`MSC-STATUS-SEMANTIK-0.4.42.md`](MSC-STATUS-SEMANTIK-0.4.42.md)

**Enger Befund:** `A_then_E_within_observed_window`; Cache-Erschöpfung nicht erreicht; `playingUid` im Play-Fenster leer (status-10 = Reselect).

---

## 1. Drei Fragen (nicht vermischen)

| ID | Frage |
|----|--------|
| **Q1** Select-Trigger | Erzeugt manuelle Auswahl ohne Remount neue MSC-Reads? |
| **Q2** Track-Ende | Erzeugt natürliches Titelende / Auto-Next neue Reads? |
| **Q3** Frische | Liest die HU dabei **geänderte** Daten (nicht nur Cache)? |

Klassifikation ergänzend zu A–E:

| Code | Bedeutung |
|------|-----------|
| **S0** | Select ohne neue Reads |
| **S1** | nur Menü/FAT/Dir |
| **S2** | Nutzdaten Zielslot |
| **S3** | Reads bei natürlichem Übergang |
| **S4** | Frische Inhalte bestätigt |
| **SR** | Reads nur nach Remount |

---

## 2. Drei Arme (eigene Artefaktordner)

1. **Arm1 — Select:** Mount → Idle 30 s → A/B/C je ≥15 s; kein OTG.  
2. **Arm2 — Trackende:** kurze hörbare Titel, Autoplay/Reihenfolge, **nicht** manuell umschalten.  
3. **Arm3 — Remount:** Soft-Remount zwischen Selects; Kausalität, kein Produkt-Claim.

Bridge `--no-audio` für Baseline. Kurze Dateien **verkürzen** Laufzeit, erzwingen **keine** Frische.

---

## 3. Lab vorher

- Hörbare Marker pro Slot + MP3-Parser-Check  
- `m3_trace_coverage.py` gegen Volltrace (Status ≈ JSONL)  
- Geometrie/Slots unverändert reproduzierbar  

---

## 4. Entscheidung nach M3seq

| Ergebnis | Nächster Schritt |
|----------|------------------|
| S0 und kein S3 | Chunk ohne Remount schwach → Arm3 / Produkt Remount skizzieren |
| nur S1 | kein Audio-Read-Nachweis |
| S2 oder S3 | dann Q3 Frische |
| S4 | Chunk-Pfad detaillieren (Timing, UX) |
| nur SR | Remount-Pfad bewerten |
| ungültige Trace | wiederholen, keine Architektur |

---

## 5. Optional parallel (nicht statt M3seq)

**Langpass Pfad A:** ≥20 min Play, Export von Plug an vollständig, Coverage live; Ziel jenseits `maxSeq`/bekannter Gaps. Ring bleibt aus.

---

## 6. Eingefroren

Ring, PSRAM, Pacing, Remount-Implementierung, BT-Hybrid, Live als M3-Ersatz, L4 parallel, Play-Detect als alleiniger Transportnachweis.

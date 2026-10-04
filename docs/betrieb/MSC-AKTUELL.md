# MSC / BMW — aktueller Stand (Lesereihenfolge)

**Stand:** 2026-10-04 · Feld Q3b 16:53 **ausgewertet** · nächster Lauf vorbereitet (`0.4.45-dev`)  
**Phase:** Lab fertig · Feld-Oracle B **PASS** · Oracle C/AV **FAIL** (Live maskiert Seed; liveBytes=0) · nächster Test: Seed-over-Live

Dies ist der **einzige Einstieg**, wenn du wissen willst, wo wir stehen und warum.

---

## 1. Jetzt lesen (normativ)

| # | Dokument | Rolle |
|---|----------|--------|
| 0 | [`artifacts-2026-10-04-feld/feld-q3b-1653/GESAMTBERICHT-FELD-Q3B-1653.md`](artifacts-2026-10-04-feld/feld-q3b-1653/GESAMTBERICHT-FELD-Q3B-1653.md) | **Aktuelle Feld-Auswertung** |
| 1 | [`artifacts-2026-10-04-lab/GESAMTBERICHT-UEBERGABE-FELD-BEREIT-2026-10-04.md`](artifacts-2026-10-04-lab/GESAMTBERICHT-UEBERGABE-FELD-BEREIT-2026-10-04.md) | Lab-Abschluss vor Feld |
| 2 | [`artifacts-2026-10-04-feld/feld-q3b-1653/`](artifacts-2026-10-04-feld/feld-q3b-1653/) | Rohdaten PD0060 16:53–57 |
| 3 | [`PLAN-NACH-M3-AE-2026-10-03.md`](PLAN-NACH-M3-AE-2026-10-03.md) | Freeze |
| 4 | [`MSC-STATUS-SEMANTIK-0.4.42.md`](MSC-STATUS-SEMANTIK-0.4.42.md) | Counter |

---

## 2. Ampel

| Thema | Stand |
|-------|--------|
| P0 | PASS (Feld zuvor) |
| P1 Body-Next | EVIDENCED (16:55 Burst+LED) |
| Feld-Oracle B | **PASS** — HU liest ≥761 |
| Feld-Oracle C | **FAIL** — Live-Ring maskierte Seed (0.4.44) |
| AV | **FAIL** — kein Ton; liveBytes=0 |
| Detect | Cold=`not_from_head`; Play über Head |
| Nächster FW | **`0.4.45-dev`** Seed gewinnt im Body gegen Live + `bytesServed` |
| Freeze | hält (kein Ring/PSRAM/Policy) |

---

## 3. Nächste Schritte (wenn wieder im Auto)

```bash
# vom Lab-Host:
tools/feld_q3b_next_prepare.sh
# dann Operator: Kurztrack → Auto-Next Rock → Film; melden Burst/Ende
```

Erfolg dieses Laufs: `bodySeed.bytesServed` steigt im Burst (Oracle C'). Hörbare Musik mit Seed **nicht** erwartet.

---

## 4. Entscheidungsregel

```
Feld-Oracle B PASS ✓
Oracle C blockiert durch Live-Overlay → 0.4.45 seed-over-live
AV braucht gültiges MPEG/Producer (Cursor/Underrun) — getrennt von Seed
Detect nur loggen · Freeze hält · Sequenz-GO gesperrt
```

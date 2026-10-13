# Gesamtbericht — Detect `cold_body_burst` (nur Log) — 2026-10-04

**Repos:** `pidrive` (dieser Push) · FW `esp32.pidrive` **`0.4.44-dev`** / Commit-Kette Lab-Stick `.88`  
**Einstieg:** [`../MSC-AKTUELL.md`](../MSC-AKTUELL.md)  
**Vorgänger:** [`GESAMTBERICHT-Q3B-PREFILL-2026-10-04.md`](GESAMTBERICHT-Q3B-PREFILL-2026-10-04.md) (Q3b Lab PASS bleibt gültig)

---

## 1. Prüfung der Übergabe (kurz)

Der Q3b-Übergabebericht (inkl. GPT-Verschärfungen) ist **korrekt und freigabefähig**:

| Claim | Prüfung |
|-------|---------|
| Q3b Lab A/B/C/Kontrolle PASS | bestätigt (`lab88-q3b-1515/report.json`) |
| Prefill ab LBA 761 / O1 | bestätigt |
| Seed ≠ Producer | übernommen — verbindlich |
| Oracle C nur Probe-LBAs | übernommen |
| Oracle B = Lab-dd, nicht HU | übernommen |
| Pfad `artifacts/2026-10-04-lab/` | **Tippfehler** — korrekt: `artifacts-2026-10-04-lab/` |
| Nächster Schritt Detect nur loggen | **diese Runde** |

---

## 2. Erledigt diese Lab-Runde

1. **Tool-Präzisierungen** in `tools/m3_lab_q3b_prefill.py`:
   - `len(blob) == sectors * 512` Pflicht vor Muster-PASS
   - Oracle B explizit als `lab_controlled_host_dd` / Coverage-Hinweis
2. **FW `0.4.44-dev`:** Event `cold_body_burst` (Diagnose only) — kein `play.guess`, kein Stream-Arm, keine Policy.
3. **Lab-Nachweis** [`lab88-detect-cold-1536/`](lab88-detect-cold-1536/) → **PASS**
4. **Offline** [`detect-cold-vs-warm-offline/`](detect-cold-vs-warm-offline/) — PD0056/57 Cold → `not_from_head`

### Lab-Ergebnis `lab88-detect-cold-1536`

| Check | Ergebnis |
|-------|----------|
| `cold_body_burst` nach Mid-File-Read ab LBA 761 | ja (`lba=761..824 n=64 B=32768 w=0 ev=not_from_head set=1`) |
| `play.guess` nach Cold | **keine** (Policy unverändert) |
| Warm-Head-Kontrast danach | `play.guess` **feuert** — Detect-Bias reproduziert |
| Ring/PSRAM/Detect-Policy | unangetastet |

---

## 3. Warum Detect Cold verfehlt (belegt)

FW-Regel (`evaluatePlay`):

```text
startLba > lbaStart + headLbaSlop(12)  →  not_from_head
```

Feld Cold-Burst (O1): first_event ≈ **1953**, Span **753…4624** → immer `not_from_head`.  
Warm-Head nahe LBA 81…93 kann Detect armieren — Lab reproduziert beides.

---

## 4. Status Ampel

| Prüfpunkt | Status |
|-----------|--------|
| P0 | PASS |
| P1 | PASS_WEAK |
| Q3b Lab | PASS (MSC-Datenebene; Seed≠Producer) |
| **Detect Diagnose** | **`cold_body_burst` live** — Policy unverändert |
| AV / Feld-Q3b / Feld-Oracle-B+C | offen |
| Freeze | hält |
| Sequenz-GO | gesperrt |

---

## 5. Nächster Auftrag (Feld — nicht Lab)

1. Feld mit Prefill ab LBA 761 + Ohr/Film + UI-Timer.  
2. Feld-Oracle B = HU-Trace; Feld-Oracle C = an HU ausgelieferte Bytes korrelierbar.  
3. `cold_body_burst` in Feld-Session mitlaufen lassen — **weiterhin nicht schalten**.  
4. `0.4.44-dev` ist Lab-FW; Fahrzeug nur nach bewusster Freigabe / gleichem Stand.

---

## 6. Zu vermeidende Fehler (unverändert + neu)

1.–10. wie Q3b-Übergabe (Seed≠AV, Lab-B≠HU, Probe≠Vollspan, …).  
11. `cold_body_burst` als Schaltfreigabe missverstehen — **nur Log**.  
12. Event-Detail >95 Zeichen (EventLog-Limit) — Format bewusst kurz gehalten.

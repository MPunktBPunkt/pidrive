# MSC / BMW — aktueller Stand (Lesereihenfolge)

**Stand:** 2026-10-04 · Feld 17:34 **Oracle B+C' PASS** · AV FAIL (kein Ton) · FW `0.4.45-dev`  
**Phase:** Prefill/Datenfrische im Feld belegt · nächster Engpass **echtes Audio/Producer**

Dies ist der **einzige Einstieg**, wenn du wissen willst, wo wir stehen und warum.

---

## 1. Jetzt lesen (normativ)

| # | Dokument | Rolle |
|---|----------|--------|
| 0 | [`artifacts-2026-10-04-feld/feld-q3b-next-1732/GESAMTBERICHT-FELD-Q3B-1732.md`](artifacts-2026-10-04-feld/feld-q3b-next-1732/GESAMTBERICHT-FELD-Q3B-1732.md) | **Aktuell** — Seed an HU ausgeliefert |
| 1 | [`artifacts-2026-10-04-feld/feld-q3b-1653/GESAMTBERICHT-FELD-Q3B-1653.md`](artifacts-2026-10-04-feld/feld-q3b-1653/GESAMTBERICHT-FELD-Q3B-1653.md) | 16:53 Live maskierte Seed |
| 2 | [`artifacts-2026-10-04-lab/GESAMTBERICHT-UEBERGABE-FELD-BEREIT-2026-10-04.md`](artifacts-2026-10-04-lab/GESAMTBERICHT-UEBERGABE-FELD-BEREIT-2026-10-04.md) | Lab-Abschluss |
| 3 | [`PLAN-NACH-M3-AE-2026-10-03.md`](PLAN-NACH-M3-AE-2026-10-03.md) | Freeze |

---

## 2. Ampel

| Thema | Stand |
|-------|--------|
| P1 Body-Next | EVIDENCED (17:34 LED+Trace) |
| Feld-Oracle B | **PASS** |
| Feld-Oracle C' | **PASS** (`bytesServed` +8 MiB, Seed-over-Live) |
| AV / Ohr | **FAIL** — kein Ton (Seed≠MP3; Producer offen) |
| Detect | Cold=`not_from_head`; nur Log |
| Sequenz-GO | gesperrt bis hörbarer AV |
| Freeze | hält |

---

## 3. Nächste Schritte

1. **Producer/AV:** gültiges Audio in den HU-Reads (Ring-Cursor/Underrun bzw. echte Nutzdaten hinter Kopf) — getrennt von Seed-Diagnose.  
2. Seed-Override nur Diagnosepfad; für Hörtest Seed aus / echtes MPEG.  
3. Detect-Policy erst nach AV-Beweis ändern.

```
Oracle B PASS ✓
Oracle C' PASS ✓  (Seed-Bytes an MSC)
AV FAIL — braucht echtes MPEG/Producer, nicht Q3B1-Muster
Freeze · Sequenz-GO gesperrt
```

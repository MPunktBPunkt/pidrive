# MSC / BMW — aktueller Stand (Lesereihenfolge)

**Stand:** 2026-10-04 · Feld 17:32 **B+C' PASS** · Feld 17:38 **C' FAIL** (Seed nach RST weg) · AV FAIL · FW `0.4.45-dev`  
**Phase:** Prefill/Datenfrische im Feld belegt · nächster Engpass **echtes Audio/Producer** · Seed erst nach letztem RST

Dies ist der **einzige Einstieg**, wenn du wissen willst, wo wir stehen und warum.

---

## 1. Jetzt lesen (normativ)

| # | Dokument | Rolle |
|---|----------|--------|
| 0 | [`artifacts-2026-10-04-feld/feld-q3b-next-1738/GESAMTBERICHT-FELD-Q3B-1738.md`](artifacts-2026-10-04-feld/feld-q3b-next-1738/GESAMTBERICHT-FELD-Q3B-1738.md) | **Aktuell** — LED/Body PASS, C' FAIL nach RST |
| 1 | [`artifacts-2026-10-04-feld/feld-q3b-next-1732/GESAMTBERICHT-FELD-Q3B-1732.md`](artifacts-2026-10-04-feld/feld-q3b-next-1732/GESAMTBERICHT-FELD-Q3B-1732.md) | 17:32 Seed an HU (`bytesServed` +8 MiB) |
| 2 | [`artifacts-2026-10-04-feld/feld-q3b-1653/GESAMTBERICHT-FELD-Q3B-1653.md`](artifacts-2026-10-04-feld/feld-q3b-1653/GESAMTBERICHT-FELD-Q3B-1653.md) | 16:53 Live maskierte Seed |
| 3 | [`artifacts-2026-10-04-lab/GESAMTBERICHT-UEBERGABE-FELD-BEREIT-2026-10-04.md`](artifacts-2026-10-04-lab/GESAMTBERICHT-UEBERGABE-FELD-BEREIT-2026-10-04.md) | Lab-Abschluss |
| 4 | [`PLAN-NACH-M3-AE-2026-10-03.md`](PLAN-NACH-M3-AE-2026-10-03.md) | Freeze |

---

## 2. Ampel

| Thema | Stand |
|-------|--------|
| P1 Body-Next | EVIDENCED (17:34 + 17:47 LED+Trace; auch Tür 17:55) |
| Feld-Oracle B | **PASS** |
| Feld-Oracle C' | **PASS** bei 17:32 (+8 MiB); **FAIL** bei 17:38 (`bytesServed=0` nach RST) |
| AV / Ohr | **FAIL** — kein Ton (Seed≠MP3; Producer offen) |
| Detect | Cold=`not_from_head`; nur Log |
| Sequenz-GO | gesperrt bis hörbarer AV |
| Freeze | hält |

---

## 3. Nächste Schritte

1. **Feld-Prozedur:** Seed erst **nach letztem RST**, dann Auto-Next ohne Reset — sonst ist C' wertlos.  
2. **Producer/AV:** gültiges Audio in den HU-Reads (Ring-Cursor/Underrun bzw. echte Nutzdaten hinter Kopf) — getrennt von Seed-Diagnose.  
3. Seed-Override nur Diagnosepfad; für Hörtest Seed aus / echtes MPEG.  
4. Detect-Policy erst nach AV-Beweis ändern.

```
Oracle B PASS ✓
Oracle C' PASS ✓ bei Seed-über-Live (17:32); FAIL wenn RST Seed löscht (17:38)
AV FAIL — braucht echtes MPEG/Producer, nicht Q3B1-Muster
Freeze · Sequenz-GO gesperrt
```

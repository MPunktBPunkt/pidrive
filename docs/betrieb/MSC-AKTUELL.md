# MSC / BMW — aktueller Stand (Lesereihenfolge)

**Stand:** 2026-10-04 · Feld 17:32 **B+C' PASS** · Feld 17:38 **C' FAIL** (Seed schon bei GO tot / Reboot ~4 s nach Seed) · AV FAIL · FW `0.4.45-dev`  
**Phase:** Prefill/Datenfrische belegt · nächster Engpass **Seed-Gate + C′-Retry**, dann **MPEG an HU-LBAs (AV A→D)**

Dies ist der **einzige Einstieg**, wenn du wissen willst, wo wir stehen und warum.

---

## 1. Jetzt lesen (normativ)

| # | Dokument | Rolle |
|---|----------|--------|
| 0 | [`artifacts-2026-10-04-feld/feld-q3b-next-1738/GESAMTBERICHT-FELD-Q3B-1738.md`](artifacts-2026-10-04-feld/feld-q3b-next-1738/GESAMTBERICHT-FELD-Q3B-1738.md) | **Aktuell** — B PASS, C' FAIL (Seed bei GO tot); Kritik Mistral/GPT |
| 0a | [`artifacts-2026-10-04-feld/feld-q3b-next-1738/KRITIK-MISTRAL-GPT-1738.md`](artifacts-2026-10-04-feld/feld-q3b-next-1738/KRITIK-MISTRAL-GPT-1738.md) | Rohspur-Korrektur zur Mistral/GPT-Deutung |
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
| Feld-Oracle C' | **PASS** bei 17:32 (+8 MiB); **FAIL** bei 17:38 (`active=False` schon bei GO / Reboot) |
| AV / Ohr | **FAIL** — kein Ton (Seed≠MP3; Producer offen) |
| Detect | Cold=`not_from_head`; nur Log |
| Sequenz-GO | gesperrt bis hörbarer AV |
| Freeze | hält |

---

## 3. Nächste Schritte

1. **Seed-Gate + Watchdog:** GO nur bei `active=True`; Abbruch bei Reboot/`active→False` vor Burst.  
2. **C′-Retry:** letzte RST → Seed → Gate → Auto-Next ohne Reset; PASS = `bytesServed↑` + passende HU-Body-LBAs.  
3. **AV A→D:** gültiges MPEG in den **tatsächlich gelesenen** LBAs + Auslieferung + Hörtest — getrennt von Seed.  
4. Detect-Policy erst nach AV-Beweis ändern. Freeze hält.

```
Oracle B PASS ✓
Oracle C' PASS ✓ (17:32); FAIL (17:38) Seed tot vor Burst — Gate fehlt
AV FAIL — MPEG an HU-LBAs, nicht nur „Producer“
Freeze · Sequenz-GO gesperrt
```

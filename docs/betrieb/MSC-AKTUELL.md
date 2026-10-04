# MSC / BMW — aktueller Stand (Lesereihenfolge)

**Stand:** 2026-10-04 · nach Feldtermin · `esp32.pidrive` @ `2bc9055`  
**Phase:** **P0 Feld PASS** · **P1/AV offen** → nächster Engpass Lab (`bufferMs` / Cache-Detect)

Dies ist der **einzige Einstieg**, wenn du wissen willst, wo wir stehen und warum.  
Alles andere unten ist Belegkette oder Historie — nicht parallel „aktuell“ lesen.

---

## 1. Jetzt lesen (normativ, in dieser Reihenfolge)

| # | Dokument | Rolle |
|---|----------|--------|
| 0 | [`artifacts-2026-10-04-feld/FELD-ERGEBNIS-2026-10-04.md`](artifacts-2026-10-04-feld/FELD-ERGEBNIS-2026-10-04.md) | **Feld-Ampel** heute |
| 1 | [`artifacts-2026-10-04-feld/GESAMTBERICHT-FELD-P0-P1-2026-10-04.md`](artifacts-2026-10-04-feld/GESAMTBERICHT-FELD-P0-P1-2026-10-04.md) | Feld-Gesamtbericht + nächste Pakete |
| 2 | [`artifacts-2026-10-04-lab/GESAMTBERICHT-UEBERGABE-P0-Q3A-2026-10-04.md`](artifacts-2026-10-04-lab/GESAMTBERICHT-UEBERGABE-P0-Q3A-2026-10-04.md) | Lab-Übergabe vor Feld (P0 deploy, Q3a PASS_WEAK) |
| 3 | [`PLAN-NACH-M3-AE-2026-10-03.md`](PLAN-NACH-M3-AE-2026-10-03.md) | Plan **Rev.5** — Freeze, Entscheidungsregel |
| 4 | [`MSC-STATUS-SEMANTIK-0.4.42.md`](MSC-STATUS-SEMANTIK-0.4.42.md) | Counter/`readCount`/Burst-Semantik |

---

## 2. Wie die Entscheidung zustande kam (Belegkette)

| Wann | Dokument / Artefakt | Entscheidung |
|------|---------------------|--------------|
| Feldabend | [`artifacts-2026-10-03-m3/auto89-m3seq-2042/`](artifacts-2026-10-03-m3/auto89-m3seq-2042/) | Rohdaten Select/Cache/Q2 |
| Korrektur | [`artifacts-2026-10-03-m3/GESAMTBERICHT-AUTO-M3SEQ-TRACE-KORREKTUR-2026-10-04.md`](artifacts-2026-10-03-m3/GESAMTBERICHT-AUTO-M3SEQ-TRACE-KORREKTUR-2026-10-04.md) | Q2 war **warm-konfundiert** → Sequenzpfad wieder offen |
| Gegenindiz | [`artifacts-2026-10-03-b7/replug-1231-noselect/`](artifacts-2026-10-03-b7/replug-1231-noselect/) | Counter-Indiz kaltes Auto-Next (±1 s); **kein** LBA-Beweis |
| Review | [`artifacts-2026-10-04-lab/GESAMTBERICHT-MSC-STRATEGIE-REVIEW-2026-10-04.md`](artifacts-2026-10-04-lab/GESAMTBERICHT-MSC-STRATEGIE-REVIEW-2026-10-04.md) | Rev.5-Schärfung |
| Lab Q3a | [`artifacts-2026-10-04-lab/lab88-q3a-0828/`](artifacts-2026-10-04-lab/lab88-q3a-0828/) | **PASS_WEAK** |
| Lab+Deploy P0 | [`lab88-p0-lock-0832/`](artifacts-2026-10-04-lab/lab88-p0-lock-0832/) · [`lab88-p0-lock-deploy-105/`](artifacts-2026-10-04-lab/lab88-p0-lock-deploy-105/) | Lock PASS; auf `.105` |
| **Feld heute** | [`artifacts-2026-10-04-feld/`](artifacts-2026-10-04-feld/) | **P0 PASS**; P1 nicht messbar; Detect selten OK; **AV FAIL** (`bufferMs=0`) |

---

## 3. Systemstand

| Komponente | Stand | Hinweis |
|------------|-------|---------|
| Docs / Feldbericht | ✅ | dieser Index + Feld-Artefakte |
| P0 Bridge-Lock | ✅ Feld PASS | Root-Menü vor Seal; nicht mit USB schon steckend falsch siegeln |
| P1×2 | ❌ / offen | Cache-Autoplay; ±1,5 s nicht anwendbar |
| Play→ffmpeg | ⚠ selten OK | PD0058 Bayern/BOB |
| Ton/Cover HU | ❌ | auch bei Detect; `bufferMs=0` |
| ESP-FW `.89` | `0.4.42-dev` | kein Downgrade / kein homecoming-OTA |
| Freeze Ring/PSRAM/Pacing | weiter halten | bis AV + P1 belastbar |

---

## 4. Historisch / nicht mehr „aktuell“ (nicht löschen)

| Dokument | Status |
|----------|--------|
| [`FELD-P0-P1-CHECKLISTE-2026-10-04.md`](FELD-P0-P1-CHECKLISTE-2026-10-04.md) | Prep-Protokoll — Feld **durch**, Ergebnis in FELD-ERGEBNIS |
| [`UEBERGABE-MSC-BEWERTUNG-2026-10-03.md`](UEBERGABE-MSC-BEWERTUNG-2026-10-03.md) | Maßnahmen-Log 10-03 — Kopf historisch |
| [`AUTO-M3-READINESS-2026-10-03.md`](AUTO-M3-READINESS-2026-10-03.md) | überholt |
| [`artifacts-2026-10-03-m3/GESAMTBERICHT-AUTO-M3-NACH-REVIEW-2026-10-03.md`](artifacts-2026-10-03-m3/GESAMTBERICHT-AUTO-M3-NACH-REVIEW-2026-10-03.md) | historisch |
| [`FELDTEST-ESP-MSC-BMW-2026-09-28.md`](FELDTEST-ESP-MSC-BMW-2026-09-28.md) | langer Log — Referenz |

---

## 5. Entscheidungsregel (aktualisiert nach Feld)

```
P0 Feld PASS ✓
P1×2 (±1,5 s, kalt) → heute NICHT GRÜN (Cache / nicht messbar)
  + AV: Detect kann greifen, HU trotzdem stumm (bufferMs=0)
→ kein Sequenz-Hauptpfad-GO
→ Lab: AV-Buffer/MSC-Fill + Cache/Detect
→ P1-Feld wiederholen erst nach Ton an HU
Freeze: Ring/PSRAM/Pacing halten
BT-Hybrid: Fallback, nicht vor AV-Lab-Klärung als „Lösung“ verkaufen
```

Zentrale offene Fragen:
1. Warum füllt der Live-Pump die MSC-Datei nicht (`bufferMs=0`)?  
2. Wann erzwingt die NBT einen Head-Read statt Cache-Play?

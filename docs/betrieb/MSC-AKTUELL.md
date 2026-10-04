# MSC / BMW — aktueller Stand (Lesereihenfolge)

**Stand:** 2026-10-04 · `pidrive` @ `9daee7a` · `esp32.pidrive` @ `2bc9055`  
**Phase:** Lab-Blocker erledigt → **nächster Schritt = Auto (P0-Feld + P1×2)**

Dies ist der **einzige Einstieg**, wenn du wissen willst, wo wir stehen und warum.  
Alles andere unten ist Belegkette oder Historie — nicht parallel „aktuell“ lesen.

---

## 1. Jetzt lesen (normativ, in dieser Reihenfolge)

| # | Dokument | Rolle |
|---|----------|--------|
| 1 | [`artifacts-2026-10-04-lab/GESAMTBERICHT-UEBERGABE-P0-Q3A-2026-10-04.md`](artifacts-2026-10-04-lab/GESAMTBERICHT-UEBERGABE-P0-Q3A-2026-10-04.md) | **Aktuelle Übergabe** — Stand, Kritik, P0/P1-Protokoll |
| 2 | [`PLAN-NACH-M3-AE-2026-10-03.md`](PLAN-NACH-M3-AE-2026-10-03.md) | Plan **Rev.5** — Prio, Freeze, Entscheidungsregel |
| 3 | [`MSC-STATUS-SEMANTIK-0.4.42.md`](MSC-STATUS-SEMANTIK-0.4.42.md) | Counter/`readCount`/Burst-Semantik |

---

## 2. Wie die Entscheidung zustande kam (Belegkette)

Chronologisch — nicht überspringen, wenn du die Architektur-Wende verstehen musst:

| Wann | Dokument / Artefakt | Entscheidung |
|------|---------------------|--------------|
| Feldabend | [`artifacts-2026-10-03-m3/auto89-m3seq-2042/`](artifacts-2026-10-03-m3/auto89-m3seq-2042/) | Rohdaten Select/Cache/Q2 |
| Korrektur | [`artifacts-2026-10-03-m3/GESAMTBERICHT-AUTO-M3SEQ-TRACE-KORREKTUR-2026-10-04.md`](artifacts-2026-10-03-m3/GESAMTBERICHT-AUTO-M3SEQ-TRACE-KORREKTUR-2026-10-04.md) | Q2 war **warm-konfundiert** → Sequenzpfad wieder offen |
| Gegenindiz | [`artifacts-2026-10-03-b7/replug-1231-noselect/`](artifacts-2026-10-03-b7/replug-1231-noselect/) | Counter-Indiz kaltes Auto-Next (±1 s); **kein** LBA-Beweis |
| Review | [`artifacts-2026-10-04-lab/GESAMTBERICHT-MSC-STRATEGIE-REVIEW-2026-10-04.md`](artifacts-2026-10-04-lab/GESAMTBERICHT-MSC-STRATEGIE-REVIEW-2026-10-04.md) | Rev.5-Schärfung (P0 Provokation, Preflight, ±1,5 s, Q3a/b, Scan-Freeze) |
| Lab Q3a | [`artifacts-2026-10-04-lab/lab88-q3a-0828/`](artifacts-2026-10-04-lab/lab88-q3a-0828/) | **PASS_WEAK** (Bytes ändern sich; Oracle offen) |
| Lab+Deploy P0 | [`lab88-p0-lock-0832/`](artifacts-2026-10-04-lab/lab88-p0-lock-0832/) · [`lab88-p0-lock-deploy-105/`](artifacts-2026-10-04-lab/lab88-p0-lock-deploy-105/) | Lock in **pump_bridge** PASS; auf `.105` |

---

## 3. Bereitschaft bis Auto-ESP online

| Komponente | Bereit? | Hinweis |
|------------|---------|---------|
| Docs / Plan / Übergabe | ✅ | beide Repos `origin/main` sync |
| Lab-Arbeit (Blocker) | ✅ durch | Q3a Oracle / L4 optional, kein P1-Blocker |
| Bridge `.105` | ✅ | `pump_bridge` mit `--msc-lock` + Connect-Retry → `.89` |
| ESP-FW Feld `.89` | ✅ für P0/P1 | **kein neues OTA für P0** (Lock = Bridge). Feld lief schon `0.4.42-dev` L3; bei Online-Werden Version prüfen |
| Auto-ESP `.89` Netz | ⏳ offline | Bridge wartet mit Retry |
| Lab-ESP `.88` | idle ok | für optionale Oracle/L4 später |

**Lab vorerst durch** für den kritischen Pfad. Weiter im Auto: P0-Feld-Provokation → Unplug → P1×2.

---

## 4. Historisch / nicht mehr „aktuell“ (nicht löschen)

Rohartefakte und Tagesberichte bleiben liegen (Nachvollziehbarkeit).  
**Nicht** als Einstieg verwenden — nur als Beleg:

| Dokument | Status |
|----------|--------|
| [`UEBERGABE-MSC-BEWERTUNG-2026-10-03.md`](UEBERGABE-MSC-BEWERTUNG-2026-10-03.md) | Maßnahmen-Log 10-03; Footer zeigt auf aktuelle Übergabe — **Kopf historisch** |
| [`AUTO-M3-READINESS-2026-10-03.md`](AUTO-M3-READINESS-2026-10-03.md) | **überholt** (behauptet u. a. `.89` noch ohne L3; Feldabend war 0.4.42) |
| [`artifacts-2026-10-03-m3/GESAMTBERICHT-AUTO-M3-NACH-REVIEW-2026-10-03.md`](artifacts-2026-10-03-m3/GESAMTBERICHT-AUTO-M3-NACH-REVIEW-2026-10-03.md) | vor Trace-Korrektur — historisch |
| [`FELDTEST-ESP-MSC-BMW-2026-09-28.md`](FELDTEST-ESP-MSC-BMW-2026-09-28.md) | langer Feld-/Lab-Log — Referenz, nicht Entscheidungsstand |
| [`B7-MORGEN-CHECKLISTE.md`](B7-MORGEN-CHECKLISTE.md) · ältere `artifacts-2026-10-0[1-2]-*` | abgeschlossen / Kontext |

**Archiv-Verschieben:** jetzt **nicht** nötig. Physisches Verschieben bricht Links in Berichten. Stattdessen: dieser Index als Filter. Später optional `docs/archiv/betrieb-msc-2026-09/` für reine Monats-Logs — erst nach stabilem P1-Ergebnis.

---

## 5. Entscheidungsregel (kurz)

```
P0 Feld PASS → P1×2 (±1,5 s, kalt per LBA-Trace)
  GRÜN → Q3a (Oracle; Lab bisher PASS_WEAK)
    GRÜN → Sequenz-Hauptpfad, BT Fallback
    ROT  → Payload-Fix, nicht sofort MSC verwerfen
  NICHT GRÜN → BT-Hybrid
Freeze: Ring/PSRAM/Pacing bis P1×2 + Q3a grün
```

Zentrale offene Frage: **Liest die NBT beim Auto-Next eine nachweislich kalte Datei rechtzeitig?**

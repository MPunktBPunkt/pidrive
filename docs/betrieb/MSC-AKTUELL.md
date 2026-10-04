# MSC / BMW — aktueller Stand (Lesereihenfolge)

**Stand:** 2026-10-04 · Lab **fertig** · nächster Schritt **Feld** · FW Lab `0.4.44-dev`  
**Phase:** **P0 PASS** · **P1 PASS_WEAK** · **Q3b Lab PASS** · **Detect-Log PASS** · **Feld/AV offen**

Dies ist der **einzige Einstieg**, wenn du wissen willst, wo wir stehen und warum.

---

## 1. Jetzt lesen (normativ)

| # | Dokument | Rolle |
|---|----------|--------|
| 0 | [`artifacts-2026-10-04-lab/GESAMTBERICHT-UEBERGABE-FELD-BEREIT-2026-10-04.md`](artifacts-2026-10-04-lab/GESAMTBERICHT-UEBERGABE-FELD-BEREIT-2026-10-04.md) | **Aktuelle Übergabe** — Feldauftrag |
| 1 | [`artifacts-2026-10-04-lab/GESAMTBERICHT-DETECT-COLD-BODY-2026-10-04.md`](artifacts-2026-10-04-lab/GESAMTBERICHT-DETECT-COLD-BODY-2026-10-04.md) | Detect-Log Lab |
| 2 | [`artifacts-2026-10-04-lab/GESAMTBERICHT-Q3B-PREFILL-2026-10-04.md`](artifacts-2026-10-04-lab/GESAMTBERICHT-Q3B-PREFILL-2026-10-04.md) | Q3b Lab PASS |
| 3 | [`artifacts-2026-10-04-lab/lab88-detect-cold-1536/`](artifacts-2026-10-04-lab/lab88-detect-cold-1536/) | cold_body_burst PASS |
| 4 | [`artifacts-2026-10-04-lab/lab88-q3b-1515/`](artifacts-2026-10-04-lab/lab88-q3b-1515/) | Q3b Prefill Oracles |
| 5 | [`PLAN-NACH-M3-AE-2026-10-03.md`](PLAN-NACH-M3-AE-2026-10-03.md) | Freeze / Geometrie |
| 6 | [`MSC-STATUS-SEMANTIK-0.4.42.md`](MSC-STATUS-SEMANTIK-0.4.42.md) | Counter-Semantik |

---

## 2. Ampel

| Thema | Stand |
|-------|--------|
| P0 Menü-Lock | **PASS** |
| P1 kalter Body-Next | **EVIDENCED / PASS_WEAK** |
| O1 LBA | **GESCHLOSSEN** — Prefill ab **761** |
| Q3b Prefill Lab | **PASS** (Seed≠Producer; Oracle B=Lab-dd≠HU) |
| Detect | **`cold_body_burst` loggt** — Policy unverändert; Warm-Head kann noch feuern |
| Ton/Cover Feld | offen |
| `bufferMs` | tote Telemetrie — ignorieren |
| Sequenz-GO | gesperrt |
| Freeze | hält |

---

## 3. Nächste Schritte

1. **Feld** (kein weiteres Lab): Prefill ab LBA 761 + Ohr/Film + UI-Timer.  
2. Feld-Oracle B = HU-Trace · Feld-Oracle C = MSC→HU Bytes · AV = Ohr.  
3. `cold_body_burst` nur loggen · Freeze hält · `0.4.44-dev` nur bewusst auf Auto.

---

## 4. Entscheidungsregel

```
P0 PASS ✓
P1 Body-Next PASS_WEAK
Q3b Lab PASS ✓  (≠ AV, ≠ HU)
Detect: cold_body_burst log only ✓
Feld-AV + Feld-Q3b → Sequenz diskutieren
Freeze Ring/PSRAM/Pacing bis AV
bufferMs ignorieren · Seed ≠ Producer
```

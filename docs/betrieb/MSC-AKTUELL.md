# MSC / BMW — aktueller Stand (Lesereihenfolge)

**Stand:** 2026-10-04 · Q3b Lab **PASS** · FW Lab `0.4.43-dev` · Commit-Kette siehe Push  
**Phase:** **P0 PASS** · **P1 PASS_WEAK** · **Q3b Lab PASS (MSC-Datenebene)** · **AV offen** · nächster Engpass **Detect-Log + Feld Ohr/Film**

Dies ist der **einzige Einstieg**, wenn du wissen willst, wo wir stehen und warum.

---

## 1. Jetzt lesen (normativ)

| # | Dokument | Rolle |
|---|----------|--------|
| 0 | [`artifacts-2026-10-04-lab/GESAMTBERICHT-Q3B-PREFILL-2026-10-04.md`](artifacts-2026-10-04-lab/GESAMTBERICHT-Q3B-PREFILL-2026-10-04.md) | **Aktuelle Übergabe** — Q3b Lab PASS |
| 1 | [`artifacts-2026-10-04-lab/lab88-q3b-1515/`](artifacts-2026-10-04-lab/lab88-q3b-1515/) | Rohartefakte Oracles A/B/C |
| 2 | [`artifacts-2026-10-04-feld/UEBERGABE-STAND-2026-10-04-O1-Q3b.md`](artifacts-2026-10-04-feld/UEBERGABE-STAND-2026-10-04-O1-Q3b.md) | O1 LBA-Grenzen (Prefill ab 761) |
| 3 | [`artifacts-2026-10-04-feld/GESAMTBERICHT-KRITIK-MISTRAL-GPT-CLAUDE-2026-10-04.md`](artifacts-2026-10-04-feld/GESAMTBERICHT-KRITIK-MISTRAL-GPT-CLAUDE-2026-10-04.md) | Vorherige Kritik-Konsolidierung |
| 4 | [`artifacts-2026-10-04-lab/lab88-av-stream-1400/`](artifacts-2026-10-04-lab/lab88-av-stream-1400/) | `bufferMs` tot |
| 5 | [`PLAN-NACH-M3-AE-2026-10-03.md`](PLAN-NACH-M3-AE-2026-10-03.md) | Rev.5 Freeze / Geometrie |
| 6 | [`MSC-STATUS-SEMANTIK-0.4.42.md`](MSC-STATUS-SEMANTIK-0.4.42.md) | Counter-Semantik |

---

## 2. Ampel

| Thema | Stand |
|-------|--------|
| P0 Menü-Lock | **PASS** |
| P1 kalter Body-Next | **EVIDENCED / PASS_WEAK** |
| O1 LBA 753 vs 1953 | **GESCHLOSSEN** — Prefill ab LBA **761** |
| **Q3b Prefill Lab** | **PASS** (MSC-Datenebene; Oracle B = Lab-Host, nicht HU) |
| Play-Detect | offen — erst `cold_body_burst` loggen |
| Ton/Cover | **FAIL** / offen (Feld AV) |
| `bufferMs` | **tote Telemetrie** — ignorieren |
| LED | MSC-Burst-Korrelator, ≠ AV |
| Sequenz-GO | noch nein — braucht Feld-AV |
| Freeze | hält |

---

## 3. Nächste Schritte

1. Detect: `cold_body_burst` **nur loggen** (Cold vs Warm).  
2. Feld: Prefill ab LBA 761 + Ohr/Film + UI-Timer; Oracle B aus HU-Trace.  
3. BT-Hybrid nur Fallback.  
4. Kein Ring/PSRAM/Pacing bis AV-Beweis.

---

## 4. Entscheidungsregel

```
P0 PASS ✓
P1 Body-Next PASS_WEAK (LBA)
Q3b Lab PASS ✓  (≠ AV, ≠ HU-Oracle-B)
AV-Metrik = streamBytes − underruns  (nicht bufferMs)
Feld-AV + Detect-Log → Sequenz-Prototyp erwägen
sonst BT-Hybrid Fallback
Freeze Ring/PSRAM/Pacing bis belastbare AV-Evidenz
```

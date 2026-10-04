# MSC / BMW — aktueller Stand (Lesereihenfolge)

**Stand:** 2026-10-04 · O1 LBA geschlossen · Commit `878b2c9` · `esp32.pidrive` @ `2bc9055`  
**Phase:** **P0 PASS** · **P1 Body-Next EVIDENCED (PASS_WEAK)** · **AV: underruns, nicht bufferMs** · **O1 zu** · nächster Engpass **Q3b/Prefill ab LBA 761**

Dies ist der **einzige Einstieg**, wenn du wissen willst, wo wir stehen und warum.

---

## 1. Jetzt lesen (normativ)

| # | Dokument | Rolle |
|---|----------|--------|
| 0 | [`artifacts-2026-10-04-feld/UEBERGABE-STAND-2026-10-04-O1-Q3b.md`](artifacts-2026-10-04-feld/UEBERGABE-STAND-2026-10-04-O1-Q3b.md) | **Aktuelle Übergabe** (O1 gelöst, Q3b-Auftrag) |
| 1 | [`artifacts-2026-10-04-feld/GESAMTBERICHT-KRITIK-MISTRAL-GPT-CLAUDE-2026-10-04.md`](artifacts-2026-10-04-feld/GESAMTBERICHT-KRITIK-MISTRAL-GPT-CLAUDE-2026-10-04.md) | Vorherige Kritik-Konsolidierung |
| 2 | [`artifacts-2026-10-04-feld/P1-OFFLINE-REGRADE-2026-10-04.json`](artifacts-2026-10-04-feld/P1-OFFLINE-REGRADE-2026-10-04.json) | Zahlen: kalte fav0-Bursts ± Nominal |
| 3 | [`artifacts-2026-10-04-lab/lab88-av-stream-1400/`](artifacts-2026-10-04-lab/lab88-av-stream-1400/) | Lab: `bufferMs` tot; Ring füllt trotz buf=0 |
| 4 | [`artifacts-2026-10-04-feld/FELD-ERGEBNIS-2026-10-04.md`](artifacts-2026-10-04-feld/FELD-ERGEBNIS-2026-10-04.md) | Feld-Ampel |
| 5 | [`PLAN-NACH-M3-AE-2026-10-03.md`](PLAN-NACH-M3-AE-2026-10-03.md) | Rev.5 Freeze / Geometrie |
| 6 | [`MSC-STATUS-SEMANTIK-0.4.42.md`](MSC-STATUS-SEMANTIK-0.4.42.md) | Counter-Semantik |

---

## 2. Ampel (korrigiert)

| Thema | Stand |
|-------|--------|
| P0 Menü-Lock | **PASS** |
| P1 kalter Body-Next | **EVIDENCED / PASS_WEAK** (B: +0,35 s; 484+1479) — nicht „unmeasurable“ |
| O1 LBA 753 vs 1953 | **GESCHLOSSEN** — Prefill ab LBA **761** (~0,33 MiB); 1953 = first_event |
| Play-Detect | selten; oft Warm-Head; verpasst Cold-Burst |
| Ton/Cover | **FAIL**; PD0058: `streamBytes==underruns` → 0 Live-Bytes |
| `bufferMs` | **tote Telemetrie** (nie geschrieben) — ignorieren |
| LED | MSC-Burst-Korrelator, ≠ AV |
| Sequenz-GO | noch nein; Prefill/Q3b offen |
| Freeze | hält |

---

## 3. Nächste Schritte

1. Lab **Q3b / Prefill** Body ab LBA **761** (Scan-Kopf 81…760 einfrieren); Oracles A/B/C.  
2. Detect: `cold_body_burst` nur loggen (Cold vs Warm).  
3. Feld mit Ohr/Film + UI-Timer erst nach Prefill-PASS.  
4. BT-Hybrid nur Fallback.

---

## 4. Entscheidungsregel

```
P0 PASS ✓
P1 Body-Next PASS_WEAK (LBA) — voll GRÜN braucht Startuhr+Ohr/Q3b
AV-Metrik = streamBytes − underruns  (nicht bufferMs)
GRÜN Prefill/Q3b → Sequenz-Prototyp erwägen
sonst BT-Hybrid Fallback
Freeze Ring/PSRAM/Pacing bis belastbare AV-/P1-Evidenz
```

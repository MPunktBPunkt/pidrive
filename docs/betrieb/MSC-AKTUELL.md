# MSC / BMW — aktueller Stand (Lesereihenfolge)

**Stand:** 2026-10-04 · nach Kritik Mistral/GPT/Claude + Lab · `esp32.pidrive` @ `2bc9055`  
**Phase:** **P0 PASS** · **P1 Body-Next EVIDENCED (PASS_WEAK)** · **AV: underruns, nicht bufferMs** · nächster Engpass **Q3b/Prefill + Detect**

Dies ist der **einzige Einstieg**, wenn du wissen willst, wo wir stehen und warum.

---

## 1. Jetzt lesen (normativ)

| # | Dokument | Rolle |
|---|----------|--------|
| 0 | [`artifacts-2026-10-04-feld/GESAMTBERICHT-KRITIK-MISTRAL-GPT-CLAUDE-2026-10-04.md`](artifacts-2026-10-04-feld/GESAMTBERICHT-KRITIK-MISTRAL-GPT-CLAUDE-2026-10-04.md) | **Aktuelle Übergabe** an nächste KI |
| 1 | [`artifacts-2026-10-04-feld/P1-OFFLINE-REGRADE-2026-10-04.json`](artifacts-2026-10-04-feld/P1-OFFLINE-REGRADE-2026-10-04.json) | Zahlen: kalte fav0-Bursts ± Nominal |
| 2 | [`artifacts-2026-10-04-lab/lab88-av-stream-1400/`](artifacts-2026-10-04-lab/lab88-av-stream-1400/) | Lab: `bufferMs` tot; Ring füllt trotz buf=0 |
| 3 | [`artifacts-2026-10-04-feld/FELD-ERGEBNIS-2026-10-04.md`](artifacts-2026-10-04-feld/FELD-ERGEBNIS-2026-10-04.md) | Feld-Ampel (P1-Zeile korrigiert unten) |
| 4 | [`PLAN-NACH-M3-AE-2026-10-03.md`](PLAN-NACH-M3-AE-2026-10-03.md) | Rev.5 Freeze / Geometrie |
| 5 | [`MSC-STATUS-SEMANTIK-0.4.42.md`](MSC-STATUS-SEMANTIK-0.4.42.md) | Counter-Semantik |

---

## 2. Ampel (korrigiert)

| Thema | Stand |
|-------|--------|
| P0 Menü-Lock | **PASS** |
| P1 kalter Body-Next | **EVIDENCED / PASS_WEAK** (B: +0,35 s; identisches 484+1479-Muster) — nicht „unmeasurable“ |
| Play-Detect | selten; oft Warm-Head; verpasst Cold-Burst |
| Ton/Cover | **FAIL**; PD0058: `streamBytes==underruns` → 0 Live-Bytes |
| `bufferMs` | **tote Telemetrie** (nie geschrieben) — ignorieren |
| LED | MSC-Burst-Korrelator, ≠ AV |
| Sequenz-GO | noch nein; Prefill/Q3b offen |
| Freeze | hält |

---

## 3. Nächste Schritte

1. Lab **Q3b / Prefill** Body-Inhalt hinter Scan-Kopf (~0,33–0,5 MiB).  
2. Detect: Cold-Body-Burst vs Warm-Head dokumentieren (zuerst loggen).  
3. Feld mit Ohr/Film erst nach Prefill-Inhalt.  
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

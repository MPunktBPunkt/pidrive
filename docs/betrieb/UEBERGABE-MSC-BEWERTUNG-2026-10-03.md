# Übergabe — MSC-Bewertung 2026-10-03 (Maßnahmen)

**Commit-Basis:** `3364878` (+ dieser Doc-Push)  
**Quellen:** GPT-Übergabebericht + Claude-Rohdatenhinweise + Mistral-Nachtrag (Chat 2026-10-03)  
**Normative Folge:** Auftrag Rev. **4** · [`../auftraege/AUFTRAG-MSC-HOST-READ-NACHWEIS.md`](../auftraege/AUFTRAG-MSC-HOST-READ-NACHWEIS.md) · [`../auftraege/AUFTRAG-M0-MESSINTEGRITAET.md`](../auftraege/AUFTRAG-M0-MESSINTEGRITAET.md)

---

## Kurzfazit (Konsens)

1. L0: HU liest **viel und schnell** (~0,8 MB/s) — Scan/Index/Cache, **kein** Live-Nachweis.  
2. Lesevolumen **skaliert** mit Angebot → Gate „Datei > Plateau“ **streichen**.  
3. Messen: **Sweep-Ende → Play-Phase** (Muster **A–E**).  
4. Reihenfolge: **M0 → M3 Lab → Feld-Hypothese → Ring/BT**.  
5. Sequenz/Autoplay = Forschungszweig; Mid-Seq-Detect ≠ Transport-Gate.

## Evidenzklassen (bei Interpretation beachten)

| Klasse | Beispiel |
|--------|----------|
| Dokumentiert | §11.11/§11.12, Artefakt-README, Status JSON |
| Rohdaten Reviewer | konkrete Poll-Zeitreihen, Slot-Map-Vergleiche |
| Interpretation | „Vollscan“ vs. „Cache-Limit“ |

## Lokal verifiziert (diese Sitzung)

- `readCount=806` / `readsEmit=218` / `readOverflow=0` in L0-Status.  
- FW: `kBurstGapMs=50` — Burst-Aggregation; Mistral-Hypothese **plausibel und codegestützt**, Gleichung noch Lab-nachweisen.  
- B7-A `pidrive_msc_reads.jsonl` = **0 Bytes**.  
- `replug-1231` Polls: `rc` 165→293 (t=21,6), 390→421 (t≈108–110); früher 421→0 (Session-Bruch).

## Maßnahmen (verbindlich)

| # | Maßnahme | Owner | Done wenn |
|---|----------|-------|-----------|
| **1** | M0: `readCount` vs Σ`burst.n` + Export + Session-ID | Lab / `esp32.pidrive` + Tools | AUFTRAG-M0 Abnahme |
| **2** | COUNTER-SEMANTICS + Feld-Tools: Session-Marker, leerer Trace = Pass ungültig für Transport | `pidrive` Tools/Docs | Doc + Tool-Check |
| **3** | M3-Testdesign Rev.4: A–E, Marker, `readRate`/`readAheadDistance`, kein Plateau-Gate | Docs done → Lab | L1/L2 Lab-Artefakt |
| **4** | Statische MP3-Generator (gültig, Marker 30 s, Xing kontrolliert) | Lab | Datei + Offset-Tabelle |
| **5** | L1→L2→L3 schrittweise; L4 nach FAT16-Validierung | Lab `.88` | A–E je Stufe |
| **6** | Neben: Sequenztest + Mid-Seq-Detect **getrennt** | Lab optional | eigener Ordner |
| **7** | Feld nur Bestätigung der Lab-Hypothese | Auto `.89` | Trace+Session ok |
| **8** | Ring/PSRAM/Remount/BT **eingefroren** | — | bis M3 A–E |

## Nicht tun

Ring aufblasen, Live in M3, Detect als Read-Proxy, Plateau-Gate, BT-Festlegung, L4 ohne FAT16, M3 vor M0.

## Nächster konkreter Schritt

**M0 im Lab:** Mount-Sweep zweimal, Burst-JSONL wächst, Gleichung `readCount = Σ n + drops` pro Session dokumentieren — dann M3 L1.

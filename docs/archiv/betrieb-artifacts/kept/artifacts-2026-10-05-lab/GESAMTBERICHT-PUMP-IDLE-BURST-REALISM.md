# Lab: Pump-Idle-Baseline + Burst-Realismus (nach Claude/Mistral-Konsens)

**Datum:** 2026-10-05/06 · **HEAD-Basis:** `eb91d4e` · **FW:** 0.4.45-dev · **Lab:** .88  
**Anlass:** Claude widerlegte Mistrals 2,7‑MB/s-Rechnung und Cursors „MSC-Last → 100 KB/s“. Konsens-P0: Leerlauf-Pump messen → optimieren → Burst-Realismus.

---

## 1. Kurzfazit

1. **Leerlauf-Pump-Obergrenze ≈ 70–74 KB/s** (`absEnd`-Steigung = `pumped_bytes`), unabhängig von Zielrate, Gap, Batch und Chunk. Claude bestätigt.
2. **Tool-Optimierungen greifen nicht:** `gap=0`, `TCP_NODELAY`, Batch 8–32 Frames → weiterhin ~70 KB/s. **Frames >512 B werden vom ESP abgelehnt** (768 teilweise, ≥1024 praktisch tot).
3. **Burst-Realismus:** Host ~250–490 KB/s + Prefill 48 KiB + Max-Pump → `und≈195–200 KiB`, Hold hält `behind=0`, Free → `behind≈2 MiB`.
4. **Prefill ≥ Burst → Streaming-PASS:** `prefill-only-48` und `prefill-eq-burst` (40 KiB Host): `und=0 ∧ behind=0 ∧ live>0`. Das ist der erste async Streaming-PASS — ohne dass der Pump während des Bursts mithalten muss.
5. **Architektur:** Bei Faktor ~4–15 (Host-Burst vs. Pump-Ceiling) deckt Nachschieben den Burst nicht. Führend: **Vorbefüllung ≥ Burst-Umfang** (Ring/PSRAM-Frage) oder Read-Pacing (FW/Freeze). Hold bleibt Pauseschutz.

---

## 2. Idle-Matrix (kein Host)

Tool: `tools/m3_lab_pump_idle.py` · Summary: `pump-idle-matrix2-summary.jsonl`

| Label | frame | gap | batch | abs_bps | Note |
|-------|------:|----:|------:|--------:|------|
| baseline | 512 | 200 µs | 1 | **73846** | Referenz |
| gap0 | 512 | 0 | 1 | 70140 | Gap nicht der Bottleneck |
| batch8/16/32 | 512 | 0 | 8–32 | 69630–71145 | Batch hilft nicht |
| f384 / f256 | 384/256 | 0 | 8 | ~69k | kleiner = nicht schneller |
| f768 | 768 | 0 | 4 | abs **4432** vs pumped 70k | ESP reject |
| f1024 | 1024 | 0 | 4 | abs **19** | ESP reject |

Bottleneck: ESP-seitige Frame-Verarbeitung bei max. 512 B/Frame (~140 Frames/s). Ohne FW-Eingriff ist ≥300 KB/s nicht erreichbar.

---

## 3. Burst-Realismus (async)

Tool: `tools/m3_lab_async_producer.py` (Rate-Accounting korrigiert: `pump_bps_observed = pumped / producer_life_s`)

| Lauf | Host B/s | Pump obs | und | live | behind | PASS |
|------|--------:|---------:|----:|-----:|-------:|:----:|
| maxpump-free | ~307k | ~64k | 195072 | 75k | **1,99 MiB** | ❌ |
| maxpump-hold | ~291k | ~55k | 195584 | 58k | **0** | ❌ |
| hostfast-hold (gap0) | ~492k | ~55k | 199680 | 54k | **0** | ❌ |
| burst48-hold (Pump an) | ~272k | ~54k | **0** | 49k | 7168 | ❌ (behind) |
| **prefill-eq-burst** (Pump≈aus, Host 40 KiB) | ~255k | ~0 | **0** | 41k | **0** | ✅ |
| **prefill-only-48** (Pump≈aus, Host 48 KiB) | ~264k | ~0 | **0** | 49k | **0** | ✅ |

Interpretation: Sobald der Host mehr liest als vorbefüllt ist, entsteht Silence (`und`). Der async Pump (~55 KB/s) kann den Rückstand bei 250–500 KB/s Host nicht schließen. Hold verhindert nur das Davonlaufen des Fensters.

---

## 4. Abgleich Reviews

| These | Urteil |
|-------|--------|
| Mistral „Free = 2,7 MB/s“ / Hold-Polling-Artefakt | ❌ verworfen (Mistral §10) |
| Cursor „MSC-Last → 100 KB/s“ | ❌ Idle zeigt dieselbe Ceiling ohne Host |
| Claude „Pump-Pfad ~60 KB/s“ | ✅ gemessen ~70 KB/s Leerlauf |
| Claude „Vorbefüllung ≥ Burst“ | ✅ Lab-PASS mit Prefill=Burst |
| Gekoppelter 2110-PASS (~18 KB/s Host) | bleibt Mechanik-Nachweis, nicht feldtauglich |

---

## 5. Nächste Schritte

1. **Bridge:** Prefill so dimensionieren, dass der HU-Erstburst (Cache-Fill) aus Vorbefüllung kommt; Hold als Pauseschutz; Pace nur wo Raten passen.  
2. **Feld:** `d(absEnd)/dt` vs `d(hostAbs)/dt` + Burst-Länge messen — entscheidet Prefill-Größe.  
3. **Nicht jetzt:** Detect/Lock/Sequenz-GO; Ring/PSRAM ohne Feld-Burstmaß; Read-Pacing ohne NBT-Toleranztest.  
4. Pump-Pfad ≥300 KB/s braucht **FW**-Arbeit (größere Frames / schnellerer Handler) — Freeze-relevant.

Freeze hält.

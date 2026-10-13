# Lab Async Producer · 2026-10-05 ~21:30–21:50

**Tool:** `tools/m3_lab_async_producer.py` — Producer-Thread unabhängig vom Host-Burst  
**Anlass:** GPT Versuch B nach Cursor-Hold PASS (`edd2271`)  
**PASS-Ziel:** `live>0` ∧ `und=0` ∧ `behind=0` (nicht erreicht unter Concurrent-Load)

---

## Kurzfazit

1. **Async Free (ohne Hold) reproduziert 18:07:** `behind≈2 MiB` (2141/2152) — Producer läuft dem Host davon, wenn ungebremst und asynchron.
2. **Async Hold hält `behind=0` am Burst-Ende** (2140/2150) — cursor-aware Hold wirkt auch ohne pump↔read-Kopplung gegen Fenster-voraus.
3. **`und=0` async unter Concurrent-MSC nicht erreicht:** Während des Host-Bursts bricht die effektive Pump-TCP-Rate auf ~100 KiB/s ein (Target 1 MiB/s), Host beobachtet ~300 KiB/s → **Host-outruns** (`und≈200 KiB`, `in_window=false`). Das gekoppelte Lab (2039/2110) pumpte *zwischen* Reads — hier konkurrieren USB-MSC und Pump um denselben ESP.
4. **Host-Pause + Free:** ESP overload / `behind≈2 MiB`. **Pause + Hold:** `behind≈40 KiB` mid-pause (Poll-Lag ~1 Ring), Ende wieder `behind=0`.

→ Async bestätigt die **zwei Fehlrichtungen** und den Nutzen von Hold. Vollständiger Streaming-PASS braucht entweder gekoppeltes Pace (bereits belegt) **oder** Bridge/ESP-Pfad, der unter MSC-Last ≥ Host-Rate hält (offen).

---

## Kernläufe

| Run | Mode | host_bps≈ | pumped | behind | und | live | in_win | Notiz |
|-----|------|-----------|--------|--------|-----|------|--------|--------|
| 2140 | 1M hold | 306k | 90k | **0** | 202k | 52k | false | Hold ok; Pace unter Last fail |
| 2141 | 1M free | 317k | 2.2M | **1.98M** | 195k | 59k | false | **18:07 async** |
| 2150 | 1M hold armed | 316k | 94k | **0** | 196k | 58k | false | Hold erst nach Arm |
| 2151 | 1M hold+pause | — | 188k | 40k mid / **0** end | 144k | 110k | false | Hold begrenzt Pause |
| 2152 | 1M free+pause | — | 4.5M | **2.0M** | 136k | 118k | false | Free destruktiv |
| 2130 | 900k hold | 50k* | 319k | **0** | 62k | 192k | true | *Snap blockierte Host |
| 2131 | 900k free | 1.8k* | 10M | **2.1M** | 20k | 234k | false | ESP overload |

---

## Folgerung für Bridge

| Stufe | Gekoppelt (Timeline) | Asynchron (dieser Lauf) |
|-------|----------------------|-------------------------|
| Prefill | 🟢 | 🟢 Startschutz |
| Pace ≥ Host | 🟢 und=0 | 🟠 ESP-Concurrent-Limit |
| Cursor-Hold | 🟢 | 🟢 behind=0 vs Free behind≫0 |

**Nächstes:** Bridge-Implementierung mit Hold; Lab optional Pump-Pfad/Last entkoppeln (weniger Status-Polls, größere Frames). Feld: Raten `d(absEnd)/dt` unter echter ffmpeg-Last. Freeze hält.

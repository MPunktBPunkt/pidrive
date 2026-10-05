# Lab: Cursor-aware Hold · 2026-10-05 ~21:10

**Anlass:** Reviews Mistral+GPT zu `a99a830` — Gate-alone widerlegt; Cursor-Kopplung als fehlende Stufe  
**Kritik:** [`KRITIK-REVIEW-MISTRAL-GPT-WEICHE-a99a830.md`](KRITIK-REVIEW-MISTRAL-GPT-WEICHE-a99a830.md)  
**Regel:** `absEnd + chunk ≤ hostAbs + cap` und nicht `absBase ≥ hostAbs` (GPT) · Bridge-seitig, kein FW

**PASS-Kriterium:** `live>0` ∧ `und=0` ∧ `behind_base=0`

---

## Kurzfazit

1. **Cursor-Hold gegen 2050-Szenario: PASS** (`2110`): Pace-Burst + Tail-Pump 3 s → `behind=0`, `und=0`, `in_window=true`, `live=253952` (vs. 2050: `behind≈200 KiB`).
2. **Host-Pause A/B:** Free während Pause → `behind=176 KiB` (2107 mid); Hold → Pause-Ende **`behind=0`** (2111), Final PASS.
3. **Hold heilt nicht Underrun-voraus** (`2106`): Burst ohne Pump (Cursor bei 253952, Ring leer) + Tail-Hold → Fenster scrollt von 0 hinter den Cursor; Hold greift erst zu spät / Bytes sind unlesbar. Braucht Prefill+Pace **vor** dem Outrun, nicht Hold danach.
4. Erste Hold-Variante (`2105`) hatte 4 KiB Overshoot (stale Snap) — mit Check je Chunk + projected `absEnd` behoben.

---

## Tabelle

| Run | Szenario | behind | und | live | in_win | hold_p | Streaming-PASS |
|-----|----------|--------|-----|------|--------|--------|----------------|
| 2050 | pace + tail **ohne** Hold | 200704 | 0 | 253952† | false | — | ❌ |
| **2110** | pace + tail **mit** Hold | **0** | **0** | **253952** | **true** | 27 | **✅** |
| 2107 | host-pause free (mid) | 176128 mid | 0 end | 253952 | true end | 0 | mid ❌ / end ✅* |
| **2111** | host-pause **Hold** | **0** (pause+end) | **0** | **253952** | **true** | 26 | **✅** |
| 2106 | silent burst + tail Hold | 32768 | 253952 | 0 | false | 0 | ❌ (nicht heilbar) |
| 2105 | Hold v1 (stale) | 4096 | 0 | 253952 | false | 1 | ≈ |

\* End PASS nur weil Host nach Pause wieder aufholte — während Pause Fenster voraus.

---

## Folgerung

Dreistufige Bridge-Strategie jetzt **lab-belegt**:

| Stufe | Lab-Status |
|-------|------------|
| Prefill | Startschutz (2036–2038, 2045) |
| Pace ≥ Host | Burst halten (2039, 2045–2046) |
| **Cursor-Hold** | Pause/Tail ohne Fenster-voraus (**2110, 2111**) |

Als Nächstes: asynchroner Bridge-Pump (ohne Read-gekoppelte Schleife) + Feld `d(absEnd)/dt` vs `d(hostAbs)/dt`. Freeze hält.

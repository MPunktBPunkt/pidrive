# Kritik / Konsolidierung: Mistral + GPT · Lab-Weiche `03dbccf`/`a99a830`

**Datum:** 2026-10-05 · **HEAD-Basis:** `a99a830`

## Konsens

| Punkt | Urteil |
|-------|--------|
| Prefill allein | 🔴 nicht hinreichend |
| Pace ≥ Host (synthetisch) | 🟢 PASS (4k/8k); 2k FAIL |
| Gate-alone (Ring voll) | 🔴 widerlegt |
| 18:07 Fenster-voraus | 🟢 Repro 2048 |
| 2050 Burst dann zerstört | 🟢 `behind_base` als Diagnose |
| Blind-FW-Snap | ❌ Freeze hält |
| „Pace ≥ Host“ = Bridge-Beweis | 🟡 Nein — Lab ist hostgekoppelt (GPT) |

**PASS-Kriterium (beide):** `live>0` ∧ `und=0` ∧ `behind_base=0` anhaltend — nicht allein `in_window` / historisches live.

## Nächste Weiche

1. **Lab:** Cursor-aware Hold (`absEnd ≤ hostAbs+cap`) — gegen 2050/Host-Pause  
2. Asynchroner Bridge-Pump (später)  
3. Feld: `d(absEnd)/dt` vs `d(hostAbs)/dt` ab `audio_start`  
4. Bridge dreistufig: Prefill + Pace + Cursor-Hold  

Freeze hält.

# Kritik / Konsolidierung: Mistral + Claude · Async `eb91d4e`

**Datum:** 2026-10-05 · **HEAD:** `eb91d4e`

## Konsens (nach Mistral-Korrektur §10)

| Punkt | Stand |
|-------|--------|
| Cursor-Hold async: `behind=0` vs Free `behind≈2 MiB` | 🟢 |
| 18:07 async (Free) | 🟢 |
| `und=0` async | 🔴 nicht erreicht |
| Mistral „Free = 2,7 MB/s“ | ❌ Messfehler — Lebensdauer ~36 s → ~60 KB/s |
| Cursor „MSC-Last → 100 KB/s“ | ❌ nicht belegt — Rate in allen Modi ~42–78 KB/s |
| Gekoppelter PASS 2110 | 🟢 Mechanik · Host nur ~18–24 KB/s → **nicht feldtauglich** |
| Hold als Burst-Lösung | 🟡 Pauseschutz ja, Burst nein |

## Führende Architektur (Claude 5.3)

Bei Pump-Leerlauf ~60 KB/s vs. HU-Burst ~0,3–1 MB/s (Faktor ~13–17) deckt ein 48‑KiB-Ring den Burst **nicht** durch Nachschieben.

Auswege: **(a)** Vorbefüllung ≥ Burst · **(b)** Read-Pacing (FW, Freeze) · Hold bleibt Pauseschutz.

## P0 Lab (alle Reviews)

1. Leerlauf-Pump (kein Host) — Chunk/Frame/Gap-Variation, `absEnd`-Steigung  
2. Pump-Pfad optimieren (Ziel ≥300 KB/s) falls Limit bestätigt  
3. Burst-Realismus · dann Prefill-/Pacing-Entscheidung  
4. Feld: `d(absEnd)/dt` vs `d(hostAbs)/dt` + Ohr  

Freeze hält.

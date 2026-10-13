# Kurz: Burst-then-Slow (feldnah)

**Lauf:** `lab88-async-064741-burst-then-slow` · Prefill 48 · Host 48 KiB @4,5 ms → 48 KiB @800 ms · Hold+MaxPump

| Mark | und | live | behind |
|------|----:|-----:|-------:|
| after_fast (48 KiB) | **0** | 49152 | 6656 |
| after_all (96 KiB) | **0** | 98304 | 11264 |

**Befund:** Prefill deckt den Burst (`und=0`); in der trägen Phase bleibt `und=0` (Pump > Host). `behind` klein ≠0 → Hold noch nicht streng genug für PASS-Kriterium, aber **kein Silence**.

Fürs Feld: Erstburst aus Prefill + Abspielrate träge → realistischer PASS-Pfad.

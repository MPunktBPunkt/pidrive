# Lab L4e nach s4-Übergabe · 2026-10-08 ~18:37

**Maßnahme:** Dauer-Bridge 12 s vorfüllen → Bridge stop → `REPLUG` (Sim besitzt Pump, `--replug-prefill-s 12`) → Bridge neu · ×5.

| Ergebnis | Wert |
|----------|------|
| PASS/FAIL | **5/5 PASS** |
| Uptime-Drops | **0** (2h 18 → 2h 21, Serial stabil) |
| live_s @48k | 8,28 … 8,41 s |

**Deutung:** Frühere 8/10 FAIL (`ring_full_pre`) waren Infrastruktur (kein Ring-Prefill). Mit Prefill ist REPLUG grün und bestätigt weiterhin: **SG-Replug rebootet Lab-ESP nicht**; Ringfenster ~8,3 s reproduzierbar.

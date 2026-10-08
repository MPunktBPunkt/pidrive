# Lab Fenster 32k · 2026-10-08 19:17

**Ziel:** Hörfenster ohne FW-Änderung verlängern (Bridge `--bitrate 32k --target-bps 4000`).

| Check | Ergebnis |
|-------|----------|
| overall | **PASS** |
| ring_full_pre | true |
| identity_ok | true |
| live_bytes_file | 50460 |
| live_s @ 4000 B/s | **12,62 s** (Modell ~12,3 s) |
| live_s_at_48k (Feldname) | 8,41 (nur Ring-Äquivalent, nicht Hördauer bei 32k) |

Muster: Bridge-Prefill 14 s → Bridge stop → REPLUG-Sim (wie L4e).

**Fazit:** Gleiche Ringkapazität, niedrigere Bitrate → längeres Byte-Fenster im Lab messbar. Feld-Ohr-Test (O2) noch offen.

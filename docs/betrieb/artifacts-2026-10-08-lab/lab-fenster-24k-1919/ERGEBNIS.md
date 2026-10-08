# Lab Fenster 24k · 2026-10-08 19:19

**Ziel:** Hörfenster ohne FW-Änderung verlängern (Bridge `--bitrate 24k --target-bps 3000`).

| Check | Ergebnis |
|-------|----------|
| overall | **PASS** |
| ring_full_pre | true |
| identity_ok | true |
| live_bytes_file | 49920 |
| live_s @ 3000 B/s | **16,64 s** (Modell ~16,4 s) |
| live_s_at_48k (Feldname) | 8,32 (nur Ring-Äquivalent) |

**Fazit:** Bitrate-Leiter bestätigt (48k ≈8,3 s · 32k ≈12,6 s · 24k ≈16,6 s) bei gleicher Ringgröße. Feld-Ohr noch offen.

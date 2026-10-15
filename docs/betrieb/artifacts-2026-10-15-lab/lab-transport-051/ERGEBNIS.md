# Lab Transport · 0.4.51-dev · 2026-10-15

**ESP:** `192.168.178.88` · vorher hu-probe `0.2.23` → OTA **`0.4.51-dev`** · Serial `PD0457` · `stallEnable=false`

## Ergebnis

| Test | Ergebnis |
|------|----------|
| OTA 0.4.51-dev (nach MSC-Eject) | **PASS** |
| `mess_hu_capture --self-test` | **PASS** |
| `nbt_hu_sim --self-test` | **PASS** |
| `lab_d_campaign preflight` (ohne UART) | **PASS** (`pass=true`, OTG stabil) |
| REPLUG `--replug-cmd-kib 4` (CBW blocks=8) | **PASS** · 128 cmd · 524288 B · sg p50 5,0 ms |
| REPLUG `--replug-cmd-kib 120` (CBW blocks=240) | **PASS** · 6 cmd · 524288 B · cdb_blocks=240 |
| Q10-Sniff | `any_field_cbw=true` · `all_q10_4kib=false` (erwartet bei 120) |

## Hinweis

UART `/dev/ttyACM0` nicht angeschlossen — Preflight-Warnung ok. Produktpfad bleibt F0 am NBT.

Artefakte: dieses Verzeichnis (`preflight/`, `replug-4k/`, `replug-120k/`, `q10-sniff.json`).

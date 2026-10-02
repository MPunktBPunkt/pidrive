# NBT-Replay Report — b1_burst_quiet_gentle

**Overall:** WARN  
**Transport:** `sg:/dev/sg0`  
**FW:** 0.4.36-dev → 0.4.36-dev  

## Kennzahlen

| Key | Value |
|-----|-------|
| `read_count` | 4 |
| `read_bytes_total` | 16384 |
| `first_read_ms` | 1500 |
| `last_read_ms` | 1950 |
| `max_read_gap_ms` | 150 |
| `underrun_delta` | 0 |
| `stream_bytes_delta` | 4096 |
| `pre_warm_delta` | 0 |
| `live_ratio` | 1.000 |
| `head_resync_delta` | -1 |
| `esp_reboot` | False |

## Verdicts

- **PASS** `esp_reboot` — no uptime regression
- **PASS** `pre_warm_bytes` — preΔ=0 (target 0 @ warmup=0)
- **PASS** `stream_after_arm` — n/a (read_bytes=16384 < 64 KiB; not a prefetch assert)
- **PASS** `overlay_live` — live_ratio=1.000
- **WARN** `head_resync` — headResyncs 1→0
- **PASS** `io_errors` — 0 IO errors

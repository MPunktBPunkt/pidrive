# Offline Detect: Cold-Burst vs Warm-Head

**Rule:** `startLba > lbaStart + 12` → `not_from_head`

## Finding
- PD0056/57 cold burst0: first_event_lba0≈1953, span 753..4624 → **not_from_head**
- Warm/scan window near file head can satisfy from-head and fire Detect
- Therefore Detect must be diagnosed via `cold_body_burst` before any policy change

See `report.json` for per-run numbers.

# Detect cold_body_burst Lab — `lab88-detect-cold-1536`

**Verdict:** `PASS`
**FW:** `0.4.44-dev`
**coldBodyBurstCount:** 1 → 2
**cold_body_burst events:** 1
**play.guess after cold:** 0 (must be 0)
**play.guess after warm contrast:** 1 (may be >0 — Detect bias)

## Expectation
- cold_body_burst fires with `ev=not_from_head` / `w=0`
- no play.guess from mid-file cold burst (policy unchanged)
- warm head may still fire Detect — documents the field bug

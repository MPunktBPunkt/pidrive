# Detect cold_body_burst Lab — `lab88-detect-cold-1533`

**Verdict:** `PASS_WEAK`
**FW:** `0.4.44-dev`
**coldBodyBurstCount:** 1 → 2
**Events:** 1 cold_body_burst · play.guess=1

## Expectation
- cold_body_burst fires with `eval=not_from_head` / `warm=0`
- no play.guess from this mid-file burst (policy unchanged)

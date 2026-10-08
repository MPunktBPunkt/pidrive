# bridge-48k-l1 — FAIL (vor Fix)

`ffmpeg` Exit 8: `-reconnect 1 -reconnect_streamed 1` galt auch für lokale Dateien → `Option reconnect not found`.

**Fix:** `esp32.pidrive` `tools/pump_bridge.py` — reconnect nur bei `http://` / `https://`.  
**Retest:** [`../bridge-48k-l1-retest/REPORT.json`](../bridge-48k-l1-retest/REPORT.json) → PASS.

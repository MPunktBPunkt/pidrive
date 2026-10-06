#!/usr/bin/env python3
"""Summarize hostAbs burst from feld_av_correlate correlate-watch.jsonl."""
from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: feld_av_burst_summary.py correlate-watch.jsonl", file=sys.stderr)
        return 2
    path = Path(sys.argv[1])
    rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    if len(rows) < 2:
        print(json.dumps({"error": "too_few_samples", "n": len(rows)}, indent=2))
        return 1

    # Active segment only
    active = [r for r in rows if r.get("stream_active")]
    seg = active if len(active) >= 2 else rows

    t0 = seg[0]["ts"]
    h0 = int(seg[0].get("hostAbsCursor") or 0)
    h1 = int(seg[-1].get("hostAbsCursor") or 0)
    dt = max(0.001, seg[-1]["ts"] - t0)
    dh = max(0, h1 - h0)

    # Max step between consecutive samples (burst proxy)
    max_step = 0
    max_dt = 0.001
    for a, b in zip(seg, seg[1:]):
        step = int(b.get("hostAbsCursor") or 0) - int(a.get("hostAbsCursor") or 0)
        sdt = max(0.001, b["ts"] - a["ts"])
        if step > max_step:
            max_step = step
            max_dt = sdt

    last = seg[-1]
    out = {
        "samples": len(rows),
        "active_samples": len(active),
        "hostAbs_delta": dh,
        "duration_s": round(dt, 2),
        "host_bps_avg": round(dh / dt) if dt else 0,
        "max_host_step_bytes": max_step,
        "max_step_bps": round(max_step / max_dt) if max_dt else 0,
        "final": {
            "underruns": last.get("underruns"),
            "liveBytes": last.get("liveBytes"),
            "hostAbsCursor": last.get("hostAbsCursor"),
            "host_behind_base": last.get("host_behind_base"),
            "host_in_window": last.get("host_in_window"),
            "absBase": last.get("absBase"),
            "absEnd": last.get("absEnd"),
        },
        "pass_streaming_heuristic": (
            int(last.get("liveBytes") or 0) > 0
            and int(last.get("underruns") or 0) == 0
            and int(last.get("host_behind_base") or 0) == 0
        ),
    }
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

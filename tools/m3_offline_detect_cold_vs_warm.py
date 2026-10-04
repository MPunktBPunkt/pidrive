#!/usr/bin/env python3
"""Offline: show why PD0056/57 cold bursts fail evaluatePlay (not_from_head)
while warm head touches can pass — using the same headLbaSlop=12 rule as FW.

Does not require ESP. Writes a short JSON+NOTES under artifacts lab folder.
"""
from __future__ import annotations

import json
from datetime import datetime as dt
from pathlib import Path

HEAD_SLOP = 12
FILE0 = 81
FILE1 = 16464
MIN_SEQ = 6000


def sectors_of(r):
    n = r["bytes"] // 512
    return range(r["lba0"], r["lba0"] + n)


def load(path: Path):
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def analyze_burst(reads, t0, t1, label):
    ev = [r for r in reads if t0 <= r["ts"] <= t1]
    if not ev:
        return {"label": label, "events": 0}
    sec = set()
    for r in ev:
        end = r["lba0"] + r["bytes"] // 512 - 1
        if end < FILE0 or r["lba0"] > FILE1:
            continue
        sec.update(sectors_of(r))
    if not sec:
        return {"label": label, "events": len(ev), "fav0": False}
    lmin, lmax = min(sec), max(sec)
    bytes_ = sum(r["bytes"] for r in ev if not (r["lba0"] + r["bytes"] // 512 - 1 < FILE0 or r["lba0"] > FILE1))
    first = min(ev, key=lambda r: r["ts"])
    start_lba = first["lba0"]  # FW seqStartLba ≈ first of contiguous seq; approximate
    # evaluatePlay rule
    from_head = start_lba <= FILE0 + HEAD_SLOP
    span_from_head = lmin <= FILE0 + HEAD_SLOP
    eval_name = "ok" if (from_head and bytes_ >= MIN_SEQ) else (
        "not_from_head" if not from_head else "seq_short"
    )
    return {
        "label": label,
        "events": len(ev),
        "bytes": bytes_,
        "span": [lmin, lmax],
        "first_event_lba0": start_lba,
        "would_from_head_if_seq_starts_at_first_event": from_head,
        "span_min_within_head_slop": span_from_head,
        "evaluatePlay_approx": eval_name,
        "note": "FW resets seq when LBA jumps >16; cold burst often starts mid-file → not_from_head",
    }


def main() -> int:
    root = Path("docs/betrieb/artifacts-2026-10-04-feld")
    out = Path("docs/betrieb/artifacts-2026-10-04-lab/detect-cold-vs-warm-offline")
    out.mkdir(parents=True, exist_ok=True)

    runs = {}
    for name, rel in [("A", "p1-run-a/msc_reads.jsonl"), ("B", "p1-run-b/msc_reads.jsonl")]:
        p = root / rel
        if not p.is_file():
            continue
        reads = load(p)
        # From earlier O1 analysis windows (CEST wall clock on Pi traces)
        cold0 = analyze_burst(
            reads,
            dt(2026, 10, 4, 10, 51, 58).timestamp(),
            dt(2026, 10, 4, 10, 52, 1).timestamp(),
            "cold_burst0",
        )
        cold1 = analyze_burst(
            reads,
            dt(2026, 10, 4, 10, 52, 5).timestamp(),
            dt(2026, 10, 4, 10, 52, 12).timestamp(),
            "cold_burst1",
        )
        # Warm-ish: early scan / head region in first second of fav0 activity
        warm = analyze_burst(
            reads,
            dt(2026, 10, 4, 10, 49, 31).timestamp(),
            dt(2026, 10, 4, 10, 49, 33).timestamp(),
            "scan_or_warm_window",
        )
        runs[name] = {"cold0": cold0, "cold1": cold1, "warm_window": warm}

    # PD0058 path if present
    pd58 = list(root.glob("**/otg*/msc_reads.jsonl")) + list(root.glob("**/p1*/msc_reads.jsonl"))
    report = {
        "headLbaSlop": HEAD_SLOP,
        "file_lba0": FILE0,
        "rule": "evaluatePlay: startLba > lbaStart+headLbaSlop → not_from_head",
        "runs": runs,
        "implication": (
            "Cold Auto-Next body bursts (first_event ~1953, span min 753) cannot pass "
            "current Detect; warm/head touches near LBA 81..93 can. "
            "cold_body_burst logging (0.4.44-dev) surfaces these without policy change."
        ),
    }
    (out / "report.json").write_text(json.dumps(report, indent=2))
    (out / "NOTES.md").write_text(
        "\n".join(
            [
                "# Offline Detect: Cold-Burst vs Warm-Head",
                "",
                f"**Rule:** `startLba > lbaStart + {HEAD_SLOP}` → `not_from_head`",
                "",
                "## Finding",
                "- PD0056/57 cold burst0: first_event_lba0≈1953, span 753..4624 → **not_from_head**",
                "- Warm/scan window near file head can satisfy from-head and fire Detect",
                "- Therefore Detect must be diagnosed via `cold_body_burst` before any policy change",
                "",
                "See `report.json` for per-run numbers.",
                "",
            ]
        )
    )
    print(json.dumps(report, indent=2)[:2500])
    print(f"artefacts: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

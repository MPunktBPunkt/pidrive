#!/usr/bin/env python3
"""Q10 Lab-Sniffer: READ10 Größen + Kopf-Pause aus Sim-reads.jsonl (kein Kernel-USB-Sniffer).

Wertet nbt_hu_sim reads.jsonl aus — Host-seitige Kommando-Längen und Zeit zwischen
erstem (Kopf) und zweitem Read. Ergänzt optional ESP /api/status → msc.xfer Histogram.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import urllib.request
from collections import Counter
from pathlib import Path


def load_reads(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if r.get("op") == "read" and "n" in r:
            rows.append(r)
    return rows


def analyze(reads: list[dict]) -> dict:
    ns = [int(r["n"]) for r in reads]
    hist = Counter(ns)
    # wall timestamps are end-of-transfer; pause ≈ (end2-end1) - dur2
    head_pause_ms = None
    wall_gap_ms = None
    if len(reads) >= 2 and "wall" in reads[0] and "wall" in reads[1]:
        wall_gap_ms = round((float(reads[1]["wall"]) - float(reads[0]["wall"])) * 1000.0, 2)
        dur2 = float(reads[1].get("wall_ms") or reads[1].get("dur_ms") or 0)
        head_pause_ms = round(wall_gap_ms - dur2, 2)
    body = ns[1:] if ns else []
    body_mode = Counter(body).most_common(1)[0][0] if body else None
    dur = [float(r.get("wall_ms") or r.get("dur_ms") or 0) for r in reads if r.get("wall_ms") or r.get("dur_ms")]
    return {
        "n_reads": len(reads),
        "n_hist": {str(k): v for k, v in sorted(hist.items())},
        "head_n": ns[0] if ns else None,
        "body_mode_n": body_mode,
        "body_all_equal_mode": bool(body) and all(x == body_mode for x in body),
        "wall_gap_head_to_2nd_ms": wall_gap_ms,
        "head_pause_est_ms": head_pause_ms,
        "dur_ms_p50": round(statistics.median(dur), 2) if dur else None,
        "q10_candidate_4kib": body_mode == 4096 and (ns[0] == 4096 if ns else False),
    }


def fetch_xfer(esp: str) -> dict | None:
    try:
        with urllib.request.urlopen(f"{esp.rstrip('/')}/api/status", timeout=5) as r:
            d = json.load(r)
        return (d.get("msc") or {}).get("xfer")
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


def main() -> int:
    ap = argparse.ArgumentParser(description="Q10 READ10/head-pause sniff from lab reads.jsonl")
    ap.add_argument("reads", nargs="+", type=Path, help="reads.jsonl path(s)")
    ap.add_argument("--esp", default="", help="optional ESP status for msc.xfer")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    reports = []
    for p in args.reads:
        if not p.exists():
            print(f"MISSING {p}", file=sys.stderr)
            continue
        a = analyze(load_reads(p))
        a["path"] = str(p)
        reports.append(a)
        print(
            f"{p}: n={a['n_reads']} hist={a['n_hist']} head={a['head_n']} "
            f"body_mode={a['body_mode_n']} pause_est={a['head_pause_est_ms']}ms "
            f"q10_4k={a['q10_candidate_4kib']}"
        )

    out: dict = {"reads": reports}
    if args.esp:
        out["msc_xfer"] = fetch_xfer(args.esp)
        print("msc.xfer", out["msc_xfer"])

    # aggregate vote
    modes = [r["body_mode_n"] for r in reports if r.get("body_mode_n")]
    pauses = [r["head_pause_est_ms"] for r in reports if r.get("head_pause_est_ms") is not None]
    out["summary"] = {
        "body_mode_votes": dict(Counter(modes)),
        "head_pause_est_ms_median": round(statistics.median(pauses), 2) if pauses else None,
        "all_q10_4kib": all(r.get("q10_candidate_4kib") for r in reports) if reports else False,
    }
    print("summary", json.dumps(out["summary"]))

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(out, indent=2))
        print("OUT", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

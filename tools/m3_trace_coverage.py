#!/usr/bin/env python3
"""Union file-offset coverage from MSC reads JSONL (kind=2 file bursts).

Uses burst.bytes from start LBA (lba0 may equal lba1 for multi-sector).
Does NOT invent missing exports — compare to status bytesFile/slot.bytes.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


def merge(intervals):
    if not intervals:
        return []
    intervals = sorted(intervals)
    out = [list(intervals[0])]
    for a, b in intervals[1:]:
        if a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return [(a, b) for a, b in out]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("reads_jsonl")
    ap.add_argument("--slots-json", help="JSON list[{uid,lba0,lba1,size?}] or status.json")
    ap.add_argument("--gap-ms", type=int, default=60000, help="split session at ms gap")
    ap.add_argument("-o", "--out", default="")
    args = ap.parse_args()

    # default L3 slots
    slots = {
        "fav0": {"lba0": 81, "lba1": 16464, "size": 8388608, "name": "fav0"},
        "fav1": {"lba0": 16465, "lba1": 17488, "size": 524288, "name": "fav1"},
        "fav2": {"lba0": 17489, "lba1": 18512, "size": 524288, "name": "fav2"},
    }
    if args.slots_json:
        raw = json.loads(Path(args.slots_json).read_text())
        sm = raw.get("msc", raw).get("slotMap", raw if isinstance(raw, list) else [])
        slots = {}
        for s in sm:
            if s.get("uid", "").startswith("pump:"):
                continue
            nsec = int(s["lba1"]) - int(s["lba0"]) + 1
            slots[s["uid"]] = {
                "lba0": int(s["lba0"]),
                "lba1": int(s["lba1"]),
                "size": nsec * 512,
                "name": s.get("name") or s["uid"],
            }

    def slot_of(lba):
        for uid, s in slots.items():
            if s["lba0"] <= lba <= s["lba1"]:
                return uid
        return None

    rows = []
    for line in Path(args.reads_jsonl).read_text().splitlines():
        if not line.strip():
            continue
        o = json.loads(line)
        if int(o.get("kind") or -1) != 2:
            continue
        rows.append(o)

    split = None
    for i in range(1, len(rows)):
        if int(rows[i].get("ms") or 0) - int(rows[i - 1].get("ms") or 0) > args.gap_ms:
            split = i
            break
    parts = {"all": rows}
    if split is not None:
        parts["pre_gap"] = rows[:split]
        parts["post_gap"] = rows[split:]

    def analyze(events):
        iv = defaultdict(list)
        cum = defaultdict(int)
        for o in events:
            l0 = int(o["lba0"])
            l1 = int(o.get("lba1", l0))
            b = int(o.get("bytes") or 0)
            if b <= 0:
                b = max(1, l1 - l0 + 1) * 512
            uid = slot_of(l0)
            if not uid:
                continue
            s = slots[uid]
            off0 = max(0, (l0 - s["lba0"]) * 512)
            off1 = min(s["size"], off0 + b)
            if l1 > l0:
                off1 = max(off1, min(s["size"], (l1 - s["lba0"] + 1) * 512))
            if off1 <= off0:
                continue
            cum[uid] += off1 - off0
            iv[uid].append((off0, off1))
        out = {}
        for uid, s in slots.items():
            merged = merge(iv.get(uid, []))
            uniq = sum(b - a for a, b in merged)
            gaps = []
            for i in range(1, len(merged)):
                if merged[i][0] > merged[i - 1][1]:
                    gaps.append(
                        {
                            "from": merged[i - 1][1],
                            "to": merged[i][0],
                            "hole": merged[i][0] - merged[i - 1][1],
                        }
                    )
            out[uid] = {
                "name": s["name"],
                "file_size": s["size"],
                "cumulative_span_bytes": cum.get(uid, 0),
                "unique_covered_bytes": uniq,
                "coverage_frac": round(uniq / s["size"], 4) if s["size"] else None,
                "min_offset": merged[0][0] if merged else None,
                "max_offset_exclusive": merged[-1][1] if merged else None,
                "n_merged_intervals": len(merged),
                "n_gaps": len(gaps),
                "gap_bytes_total": sum(g["hole"] for g in gaps),
                "largest_gaps": sorted(gaps, key=lambda g: -g["hole"])[:8],
                "unread_prefix_bytes": merged[0][0] if merged else s["size"],
                "unread_suffix_bytes": (s["size"] - merged[-1][1]) if merged else s["size"],
            }
        return {"n_bursts": len(events), "slots": out}

    report = {
        "source": args.reads_jsonl,
        "warning": (
            "Coverage is only as complete as the JSONL export. "
            "Compare unique/cumulative to status bytesFile and slotMap.bytes; "
            "if status >> JSONL, export was incomplete (overflow/bridge gap)."
        ),
        "parts": {k: analyze(v) for k, v in parts.items()},
    }
    text = json.dumps(report, indent=2)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

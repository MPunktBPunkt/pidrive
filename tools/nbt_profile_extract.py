#!/usr/bin/env python3
"""Extract NBT-Evo HU read profile from a field artifact folder.

Reads status-*.json / runde-*/status/st-*.json (mscTrace + xfer + slotMap),
correlate-*/correlate-watch.jsonl, bridge-*.txt.

Example:
  python3 tools/nbt_profile_extract.py \\
      --in docs/betrieb/artifacts-2026-10-06-feld/feld-av-0723 \\
      --out tools/profiles/nbt_evo_2026-10-06.json
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
from collections import Counter
from pathlib import Path


def load_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def collect_status_files(root: Path) -> list[Path]:
    files: list[Path] = []
    files.extend(sorted(root.glob("status-*.json")))
    files.extend(sorted(root.glob("runde-*/status/st-*.json")))
    files.extend(sorted(root.glob("switch-run-*/st-*.json")))
    # de-dupe
    seen = set()
    out = []
    for p in files:
        if p.resolve() in seen:
            continue
        seen.add(p.resolve())
        out.append(p)
    return out


def percentile(sorted_vals: list[float], p: float) -> float | None:
    if not sorted_vals:
        return None
    if len(sorted_vals) == 1:
        return float(sorted_vals[0])
    k = (len(sorted_vals) - 1) * p
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return float(sorted_vals[f])
    return float(sorted_vals[f] * (c - k) + sorted_vals[c] * (k - f))


def extract_traces(files: list[Path]) -> dict:
    gaps: list[int] = []
    ns: list[int] = []
    tags: Counter[str] = Counter()
    kinds: Counter[str] = Counter()
    xfer_sum = Counter()
    xfer_n = 0
    slot_progress: list[dict] = []

    for p in files:
        d = load_json(p)
        if not d:
            continue
        m = d.get("msc") or {}
        tr = d.get("mscTrace") or m.get("mscTrace") or []
        for e in tr:
            if not isinstance(e, dict):
                continue
            g = e.get("gap")
            n = e.get("n")
            if g is not None:
                try:
                    gaps.append(int(g))
                except (TypeError, ValueError):
                    pass
            if n is not None:
                try:
                    ns.append(int(n))
                except (TypeError, ValueError):
                    pass
            tag = str(e.get("tag") or "")
            if tag:
                tags[tag] += 1
            kind = str(e.get("kind") or "")
            if kind:
                kinds[kind] += 1
        xfer = m.get("xfer") or {}
        if xfer:
            xfer_n += 1
            for k in ("n512", "n2k", "n4k", "n8kPlus"):
                xfer_sum[k] += int(xfer.get(k) or 0)
        slots = m.get("slotMap") or d.get("slotMap") or []
        if slots:
            slot_progress.append(
                {
                    "file": p.name,
                    "uptime": d.get("uptime"),
                    "slots": [
                        {
                            "uid": s.get("uid"),
                            "name": s.get("name"),
                            "bytes": s.get("bytes"),
                            "maxSeq": s.get("maxSeq"),
                        }
                        for s in slots
                        if isinstance(s, dict)
                    ],
                }
            )

    gaps_s = sorted(gaps)
    ns_s = sorted(ns)
    return {
        "status_files": len(files),
        "trace_entries": len(gaps),
        "gap_ms": {
            "n": len(gaps_s),
            "median": statistics.median(gaps_s) if gaps_s else None,
            "p25": percentile(gaps_s, 0.25),
            "p75": percentile(gaps_s, 0.75),
            "min": gaps_s[0] if gaps_s else None,
            "max": gaps_s[-1] if gaps_s else None,
        },
        "read_n_bytes": {
            "n": len(ns_s),
            "median": statistics.median(ns_s) if ns_s else None,
            "mode": Counter(ns_s).most_common(1)[0][0] if ns_s else None,
            "counts": dict(Counter(ns_s).most_common(8)),
        },
        "xfer_avg": {k: (xfer_sum[k] / xfer_n if xfer_n else 0) for k in ("n512", "n2k", "n4k", "n8kPlus")},
        "xfer_samples": xfer_n,
        "tags_top": tags.most_common(12),
        "kinds": dict(kinds),
        "slot_progress_samples": len(slot_progress),
        "slot_progress_tail": slot_progress[-5:],
    }


def extract_producer(root: Path) -> dict:
    rates: list[float] = []
    watches = sorted(root.glob("correlate-*/correlate-watch.jsonl"))
    for w in watches:
        rows = []
        for line in w.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        active = [r for r in rows if r.get("stream_active")]
        seg = active if len(active) >= 4 else rows
        for a, b in zip(seg, seg[1:]):
            dt = float(b.get("ts") or 0) - float(a.get("ts") or 0)
            if dt <= 0.05:
                continue
            de = int(b.get("absEnd") or 0) - int(a.get("absEnd") or 0)
            if de > 0:
                rates.append(de / dt)
    rates_s = sorted(rates)
    return {
        "correlate_watches": [str(p.relative_to(root)) for p in watches],
        "absEnd_bps_samples": len(rates_s),
        "absEnd_bps_median": statistics.median(rates_s) if rates_s else None,
        "absEnd_bps_p25": percentile(rates_s, 0.25),
        "absEnd_bps_p75": percentile(rates_s, 0.75),
    }


def extract_bridge(root: Path) -> dict:
    starts = 0
    switches: list[dict] = []
    ages: list[float] = []
    re_switch = re.compile(
        r"switch\s+(\S+)\s+→\s+(\S+)\s+\(age=([0-9.]+)s\)"
    )
    re_audio = re.compile(r"audio_start|audio\.start")
    for p in sorted(root.glob("bridge-*.txt")):
        text = p.read_text(encoding="utf-8", errors="replace")
        starts += len(re_audio.findall(text))
        for m in re_switch.finditer(text):
            age = float(m.group(3))
            ages.append(age)
            switches.append(
                {"file": p.name, "from": m.group(1), "to": m.group(2), "age_s": age}
            )
    # track content duration estimate for 512 KiB @ 48k ≈ 87.3 s; gap ≈ age - 87.3
    gaps = [a - 87.3 for a in ages if a > 60]
    return {
        "bridge_files": len(list(root.glob("bridge-*.txt"))),
        "audio_start_mentions": starts,
        "switches": switches,
        "switch_age_s": ages,
        "track_gap_s_est": {
            "n": len(gaps),
            "median": statistics.median(gaps) if gaps else None,
            "note": "age_s - 87.3 (512KiB@48k content)",
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--in",
        dest="indir",
        default="docs/betrieb/artifacts-2026-10-06-feld/feld-av-0723",
    )
    ap.add_argument("--out", default="tools/profiles/nbt_evo_2026-10-06.json")
    args = ap.parse_args()

    root = Path(args.indir)
    if not root.is_dir():
        raise SystemExit(f"missing input dir: {root}")

    status_files = collect_status_files(root)
    profile = {
        "source": str(root),
        "generated": __import__("datetime").datetime.now().astimezone().isoformat(timespec="seconds"),
        "model": "nbt_evo_file_cache_eager_read",
        "read": {
            "size_bytes": 4096,
            "gap_ms_target": 4,
            "queue_depth": 1,
        },
        "from_artifacts": extract_traces(status_files),
        "producer": extract_producer(root),
        "bridge": extract_bridge(root),
        "geometry_l3": {
            "fav0_bytes": 8388608,
            "fav1_bytes": 524288,
            "fav2_bytes": 524288,
        },
        "notes": [
            "Burst = unread file remainder, not decoder buffer",
            "Stall only on active live slot sequential cursor reads",
            "Prefetch other slots: silence immediately",
        ],
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(profile, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    gap_med = profile["from_artifacts"]["gap_ms"]["median"]
    n_mode = profile["from_artifacts"]["read_n_bytes"]["mode"]
    print(f"OUT {out}")
    print(f"status_files={len(status_files)} traces={profile['from_artifacts']['trace_entries']}")
    print(f"gap_ms median={gap_med} read_n mode={n_mode}")
    ok = (
        gap_med is not None
        and 2 <= float(gap_med) <= 8
        and n_mode == 4096
    )
    print("ACCEPT", "PASS" if ok else "CHECK")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

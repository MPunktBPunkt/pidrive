#!/usr/bin/env python3
"""Classify Quiet (Q) / Storm (S) / Normal from status-poll JSONL or status JSON.

Never uses readCount/playRejectCount alone (audit 2026-10-17: Quiet-Plateau).
Axes: ΔbytesFile, prefetchHits, ΣmidFile, guess, stream/play.

Examples:
  python3 tools/feld_qs_classify.py --poll path/to/poll.jsonl
  python3 tools/feld_qs_classify.py --status path/to/status.json --label-hint stuck
  python3 tools/feld_qs_classify.py --poll poll.jsonl --window-s 5 --out qs-report.json
  python3 tools/feld_qs_classify.py --self-test
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _i(v: Any, default: int = 0) -> int:
    try:
        return int(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def slot_sums(row: dict) -> tuple[int, int, int]:
    mid = head = nbytes = 0
    for s in row.get("slotMap") or []:
        if not isinstance(s, dict):
            continue
        mid += _i(s.get("midFile"))
        head += _i(s.get("fromHead"))
        nbytes += _i(s.get("bytes"))
    return mid, head, nbytes


def axes_from_row(row: dict) -> dict[str, Any]:
    mid, head, slot_b = slot_sums(row)
    slots = [s for s in (row.get("slotMap") or []) if isinstance(s, dict)]
    has_mid = any("midFile" in s for s in slots)
    has_head = any("fromHead" in s for s in slots)
    reads = row.get("readCount")
    rej = row.get("rej", row.get("playRejectCount"))
    inv = row.get("reads_minus_rej")
    if inv is None and reads is not None and rej is not None:
        inv = _i(reads) - _i(rej)
    return {
        "wall_iso": row.get("wall_iso"),
        "mono_s": row.get("mono_s"),
        "prefetchHits": row.get("prefetchHits"),
        "bytesFile": row.get("bytesFile"),
        "bytesDir": row.get("bytesDir"),
        "bytesFat": row.get("bytesFat"),
        "bytesMeta": row.get("bytesMeta"),
        "bytesBoot": row.get("bytesBoot"),
        "midFile_sum": mid if has_mid else None,
        "fromHead_sum": head if has_head else None,
        "slot_bytes_sum": slot_b,
        "guess": row.get("guess", row.get("playGuessCount")),
        "stream_active": row.get("stream_active"),
        "playingName": row.get("playingName") or "",
        "readCount": reads,
        "rej": rej,
        "reads_minus_rej": inv,
        "schema_version": row.get("schema_version"),
        "has_pref": row.get("prefetchHits") is not None,
        "has_mid": has_mid,
    }


def classify_snapshot(
    ax: dict[str, Any],
    *,
    d_bf_per_s: float | None = None,
    d_pref_per_s: float | None = None,
    d_mid_per_s: float | None = None,
    storm_bf_bps: float = 80_000.0,
    storm_pref_abs: int = 200,
    storm_mid_abs: int = 400,
    quiet_bf_bps: float = 8_000.0,
) -> dict[str, Any]:
    """Label one moment. Prefer rates when available; else absolute axes."""
    reasons: list[str] = []
    pref = ax.get("prefetchHits")
    mid = ax.get("midFile_sum")
    guess = _i(ax.get("guess"))
    play = bool(ax.get("playingName"))
    ear_like = play and bool(ax.get("stream_active"))

    storm_hit = False
    if d_bf_per_s is not None and d_bf_per_s >= storm_bf_bps:
        storm_hit = True
        reasons.append(f"ΔbytesFile/s={d_bf_per_s:.0f}>={storm_bf_bps:.0f}")
    if d_pref_per_s is not None and d_pref_per_s >= 20:
        storm_hit = True
        reasons.append(f"Δpref/s={d_pref_per_s:.1f}>=20")
    if d_mid_per_s is not None and d_mid_per_s >= 30:
        storm_hit = True
        reasons.append(f"Δmid/s={d_mid_per_s:.1f}>=30")
    if pref is not None and _i(pref) >= storm_pref_abs:
        storm_hit = True
        reasons.append(f"pref={pref}>={storm_pref_abs}")
    if mid is not None and _i(mid) >= storm_mid_abs:
        storm_hit = True
        reasons.append(f"midSum={mid}>={storm_mid_abs}")

    if storm_hit:
        label = "S"
        if guess > 0:
            reasons.append("guess>0_in_storm")
        if ear_like:
            reasons.append("play+stream_in_storm")
        return {"label": label, "reasons": reasons, "axes": ax}

    quiet_hit = False
    if d_bf_per_s is not None and d_bf_per_s <= quiet_bf_bps:
        quiet_hit = True
        reasons.append(f"ΔbytesFile/s={d_bf_per_s:.0f}<={quiet_bf_bps:.0f}")
    if pref is not None and _i(pref) <= 20 and (d_pref_per_s is None or d_pref_per_s < 2):
        quiet_hit = True
        reasons.append(f"pref={pref}<=20")
    if mid is not None and _i(mid) <= 40 and (d_mid_per_s is None or d_mid_per_s < 2):
        quiet_hit = True
        reasons.append(f"midSum={mid}<=40")

    if ear_like and guess > 0 and not storm_hit:
        return {"label": "Normal", "reasons": ["play+stream+guess"] + reasons, "axes": ax}

    if quiet_hit and guess == 0 and not play:
        return {"label": "Q", "reasons": reasons or ["quiet_axes"], "axes": ax}

    if quiet_hit and (guess > 0 or ear_like):
        return {"label": "Quiet-after-play", "reasons": reasons + ["post_window"], "axes": ax}

    return {"label": "Unknown", "reasons": reasons or ["insufficient_axes"], "axes": ax}


def classify_poll(
    rows: list[dict],
    *,
    window_s: float = 5.0,
) -> dict[str, Any]:
    ok = [r for r in rows if "error" not in r]
    if not ok:
        return {"error": "no_ok_rows", "n": len(rows)}

    series: list[dict[str, Any]] = []
    for r in ok:
        ax = axes_from_row(r)
        series.append(ax)

    has_pref = sum(1 for a in series if a.get("has_pref"))
    has_mid = sum(1 for a in series if a.get("has_mid"))
    gaps = {
        "schema_note": (
            "v1 polls lack prefetchHits/midFile — Storm detectable via ΔbytesFile only; "
            "upgrade to feld_status_poll schema v2 for full Q/S."
            if has_pref == 0 or has_mid == 0
            else "schema_ok"
        ),
        "rows_with_prefetchHits": has_pref,
        "rows_with_midFile": has_mid,
        "n_ok": len(ok),
        "n_err": len(rows) - len(ok),
    }

    labeled: list[dict[str, Any]] = []
    for i, ax in enumerate(series):
        mono = ax.get("mono_s")
        d_bf = d_pref = d_mid = None
        if isinstance(mono, (int, float)):
            j = i
            while j > 0 and isinstance(series[j].get("mono_s"), (int, float)):
                dt = float(mono) - float(series[j].get("mono_s"))
                if dt >= window_s:
                    break
                j -= 1
            if j < i and isinstance(series[j].get("mono_s"), (int, float)):
                dt = float(mono) - float(series[j].get("mono_s"))
                if dt > 0.2:
                    def rate(key: str) -> float | None:
                        a = ax.get(key)
                        b = series[j].get(key)
                        if a is None or b is None:
                            return None
                        return (_i(a) - _i(b)) / dt

                    d_bf = rate("bytesFile")
                    d_pref = rate("prefetchHits")
                    d_mid = rate("midFile_sum")

        lab = classify_snapshot(ax, d_bf_per_s=d_bf, d_pref_per_s=d_pref, d_mid_per_s=d_mid)
        lab["d_bytesFile_per_s"] = d_bf
        lab["d_prefetch_per_s"] = d_pref
        lab["d_mid_per_s"] = d_mid
        labeled.append(lab)

    counts: dict[str, int] = {}
    for lab in labeled:
        counts[lab["label"]] = counts.get(lab["label"], 0) + 1

    # episode spans
    episodes: list[dict[str, Any]] = []
    cur = None
    for lab in labeled:
        L = lab["label"]
        wall = (lab.get("axes") or {}).get("wall_iso")
        if cur and cur["label"] == L:
            cur["end"] = wall
            cur["n"] += 1
        else:
            if cur:
                episodes.append(cur)
            cur = {"label": L, "start": wall, "end": wall, "n": 1}
    if cur:
        episodes.append(cur)

    guess_events = []
    prev_g = None
    for lab in labeled:
        g = _i((lab.get("axes") or {}).get("guess"))
        if prev_g is not None and g > prev_g:
            guess_events.append(
                {
                    "wall_iso": (lab.get("axes") or {}).get("wall_iso"),
                    "guess": g,
                    "label_at": lab["label"],
                    "reasons": lab.get("reasons"),
                }
            )
        prev_g = g

    inv_vals = sorted(
        {
            _i(a.get("reads_minus_rej"))
            for a in series
            if a.get("reads_minus_rej") is not None
        }
    )

    # M36: alerts from Q/S axes only — never from reads−rej alone
    alerts: list[dict[str, Any]] = []
    prev_label: str | None = None
    for lab in labeled:
        for a in alerts_for_sample(lab, prev_label=prev_label):
            alerts.append(a)
        prev_label = lab["label"]
    for ge in guess_events:
        if ge.get("label_at") == "S":
            # Δguess while already in storm (enter-with-guess already covered above)
            if not any(
                a.get("kind") == "storm_guess" and a.get("wall_iso") == ge.get("wall_iso")
                for a in alerts
            ):
                alerts.append(
                    {
                        "kind": "storm_guess",
                        "severity": "INFO",
                        "wall_iso": ge.get("wall_iso"),
                        "label": "S",
                        "guess": ge.get("guess"),
                        "reasons": ge.get("reasons"),
                    }
                )

    return {
        "gaps": gaps,
        "label_counts": counts,
        "episodes": episodes,
        "guess_events": guess_events,
        "alerts": alerts,
        "reads_minus_rej_unique": inv_vals,
        "invariant_ok": set(inv_vals).issubset({31, 32}) if inv_vals else None,
        "invariant_note": (
            "reads−rej is plausibility only (Quiet-Plateau ∈{31,32}); never an alarm"
        ),
        "samples": labeled[:: max(1, len(labeled) // 12)][:12],
    }


def alerts_for_sample(
    lab: dict[str, Any],
    *,
    prev_label: str | None = None,
) -> list[dict[str, Any]]:
    """M36 alert policy: Storm enter / Storm sticky. Never alert on reads−rej."""
    out: list[dict[str, Any]] = []
    label = lab.get("label")
    ax = lab.get("axes") or {}
    wall = ax.get("wall_iso")
    reasons = list(lab.get("reasons") or [])
    # Explicitly ignore invariant for alerting
    _ = ax.get("reads_minus_rej")

    if label == "S" and prev_label != "S":
        out.append(
            {
                "kind": "storm_enter",
                "severity": "ALERT",
                "wall_iso": wall,
                "label": label,
                "reasons": reasons,
                "axes_hint": {
                    "prefetchHits": ax.get("prefetchHits"),
                    "midFile_sum": ax.get("midFile_sum"),
                    "d_bytesFile_per_s": lab.get("d_bytesFile_per_s"),
                },
            }
        )
        # Guess already present at storm enter (M35 signal) — one INFO, not sticky
        if _i(ax.get("guess")) > 0:
            out.append(
                {
                    "kind": "storm_guess",
                    "severity": "INFO",
                    "wall_iso": wall,
                    "label": label,
                    "guess": ax.get("guess"),
                    "reasons": reasons,
                }
            )
    return out


def format_dashboard_line(lab: dict[str, Any], *, inv_ok: bool | None = None) -> str:
    """One-line operator dashboard (M36)."""
    ax = lab.get("axes") or {}
    label = lab.get("label") or "?"
    mid = ax.get("midFile_sum")
    pref = ax.get("prefetchHits")
    bf = ax.get("bytesFile")
    guess = ax.get("guess")
    inv = ax.get("reads_minus_rej")
    inv_s = f"inv={inv}"
    if inv_ok is False:
        inv_s += "(plaus≠31/32)"
    elif inv is not None:
        inv_s += "(plaus)"
    d_bf = lab.get("d_bytesFile_per_s")
    d_bf_s = f"Δbf={d_bf:.0f}/s" if isinstance(d_bf, (int, float)) else "Δbf=-"
    return (
        f"{ax.get('wall_iso') or '-'}  {label:16s}  "
        f"pref={pref} mid={mid} bf={bf} {d_bf_s} guess={guess}  {inv_s}"
    )


def status_file_to_row(path: Path) -> dict:
    st = json.loads(path.read_text(encoding="utf-8"))
    if "msc" in st:
        # full /api/status dump → synthesize poll-like row
        from feld_status_poll import row_from_status

        return row_from_status(st, wall_iso=path.name, mono=0.0, run_id=path.stem)
    return st


def self_test() -> int:
    quiet = {
        "prefetchHits": 8,
        "bytesFile": 557056,
        "guess": 0,
        "playingName": "",
        "stream_active": False,
        "readCount": 167,
        "rej": 136,
        "slotMap": [
            {"uid": "fav0", "fromHead": 0, "midFile": 8, "bytes": 32768},
            {"uid": "fav1", "fromHead": 2, "midFile": 126, "bytes": 524288},
        ],
    }
    storm = {
        "prefetchHits": 1200,
        "bytesFile": 9_000_000,
        "guess": 0,
        "playingName": "",
        "stream_active": False,
        "readCount": 2000,
        "rej": 1969,
        "slotMap": [{"uid": "fav0", "fromHead": 2, "midFile": 1800, "bytes": 8_000_000}],
    }
    q = classify_snapshot(axes_from_row(quiet), d_bf_per_s=100.0)
    s = classify_snapshot(axes_from_row(storm), d_bf_per_s=200_000.0)
    assert q["label"] == "Q", q
    assert s["label"] == "S", s
    # rate-only storm without abs pref in window
    s2 = classify_snapshot(
        axes_from_row({"bytesFile": 1, "guess": 0, "playingName": "", "slotMap": []}),
        d_bf_per_s=100_000.0,
    )
    assert s2["label"] == "S", s2

    # M36: Quiet-Plateau must NOT raise alert despite reads−rej
    q_alerts = alerts_for_sample(q, prev_label=None)
    assert q_alerts == [], q_alerts
    s_alerts = alerts_for_sample(s, prev_label="Q")
    assert any(a["kind"] == "storm_enter" for a in s_alerts), s_alerts
    # sticky S: no repeat storm_enter
    sticky = alerts_for_sample(s, prev_label="S")
    assert not any(a["kind"] == "storm_enter" for a in sticky), sticky
    # guess-in-storm INFO
    s_g = classify_snapshot(axes_from_row({**storm, "guess": 1}), d_bf_per_s=200_000.0)
    g_alerts = alerts_for_sample(s_g, prev_label="Q")
    assert any(a["kind"] == "storm_guess" for a in g_alerts), g_alerts
    line = format_dashboard_line(q)
    assert "Q" in line and "plaus" in line, line

    print(
        "self-test OK",
        {
            "Q": q["label"],
            "S": s["label"],
            "S_rate": s2["label"],
            "m36_storm_enter": True,
            "m36_no_quiet_alert": True,
        },
    )
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Classify Q/S/Normal from polls or status JSON")
    ap.add_argument("--poll", type=Path, help="status-poll JSONL")
    ap.add_argument("--status", type=Path, help="single /api/status JSON")
    ap.add_argument("--window-s", type=float, default=5.0)
    ap.add_argument("--out", type=Path, help="write report JSON")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        return self_test()

    if args.status:
        row = status_file_to_row(args.status)
        ax = axes_from_row(row)
        report = {"mode": "status", "result": classify_snapshot(ax), "axes": ax}
    elif args.poll:
        rows = [json.loads(l) for l in args.poll.read_text(encoding="utf-8").splitlines() if l.strip()]
        report = {"mode": "poll", "path": str(args.poll), **classify_poll(rows, window_s=args.window_s)}
    else:
        ap.error("need --poll or --status (or --self-test)")
        return 2

    text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
        counts = report.get("label_counts") or (report.get("result") or {})
        print(f"wrote {args.out} counts={counts}", flush=True)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    # allow `from feld_status_poll` when run as script from repo root / tools/
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    raise SystemExit(main())

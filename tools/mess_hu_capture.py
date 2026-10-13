#!/usr/bin/env python3
"""Drive PiDrive mess-fw situations and dump READ10 command capture (Q10).

Soft USB (POST /api/lab/usb) toggles TinyUSB D+ pull-up — NOT VBUS / physical OTG.

Examples:
  python3 tools/mess_hu_capture.py --esp http://192.168.178.88 status
  python3 tools/mess_hu_capture.py --esp http://192.168.178.88 reset
  python3 tools/mess_hu_capture.py --esp http://192.168.178.88 sit usb_cycle --hold-ms 600
  python3 tools/mess_hu_capture.py --esp http://192.168.178.88 dump -o /tmp/mess-cmds.json
  python3 tools/mess_hu_capture.py --esp http://192.168.178.88 q10 --wait 20
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any


def http_json(url: str, method: str = "GET", body: dict | None = None, timeout: float = 8.0) -> Any:
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
        return json.loads(raw) if raw else {}


def esp_base(args: argparse.Namespace) -> str:
    return args.esp.rstrip("/")


def cmd_status(args: argparse.Namespace) -> int:
    st = http_json(f"{esp_base(args)}/api/status")
    mess = st.get("mess") or {}
    print(json.dumps({
        "version": st.get("version"),
        "labMode": st.get("labMode"),
        "otgUp": st.get("otgUp"),
        "mess": mess,
        "softUsbAttached": ((st.get("ports") or {}).get("otg") or {}).get("softUsbAttached"),
    }, indent=2))
    return 0


def cmd_reset(args: argparse.Namespace) -> int:
    out = http_json(f"{esp_base(args)}/api/lab/mess", "POST", {"reset": True, "enable": True})
    print(json.dumps({"ok": out.get("ok"), "mess": out.get("mess")}, indent=2))
    return 0 if out.get("ok") else 1


def cmd_sit(args: argparse.Namespace) -> int:
    body: dict[str, Any] = {"name": args.name}
    if args.hold_ms is not None:
        body["holdMs"] = args.hold_ms
    if args.keep_identity:
        body["keepIdentity"] = True
    if args.mark:
        body["mark"] = args.mark
    if args.max_ms is not None:
        body["maxMs"] = args.max_ms
    out = http_json(f"{esp_base(args)}/api/lab/situation", "POST", body)
    print(json.dumps(out, indent=2))
    return 0 if out.get("ok") else 1


def cmd_usb(args: argparse.Namespace) -> int:
    if args.cycle_ms is not None:
        body: dict[str, Any] = {"cycleMs": args.cycle_ms}
    else:
        body = {"attach": args.attach, "holdMs": args.hold_ms or 0}
    out = http_json(f"{esp_base(args)}/api/lab/usb", "POST", body)
    print(json.dumps(out, indent=2))
    return 0 if out.get("ok") else 1


def cmd_dump(args: argparse.Namespace) -> int:
    out = http_json(f"{esp_base(args)}/api/lab/mess")
    if args.out:
        Path(args.out).write_text(json.dumps(out, indent=2), encoding="utf-8")
        print(f"wrote {args.out} cmds={len(out.get('cmds') or [])}")
    else:
        print(json.dumps(out, indent=2))
    return 0 if out.get("ok") else 1


def summarize_q10(cmds: list[dict]) -> dict[str, Any]:
    reads = [c for c in cmds if c.get("op") == 0x28 and (c.get("bytes") or 0) > 0]
    if not reads:
        return {"n": 0, "error": "no READ10 cmds"}
    blocks = [int(c.get("blocks") or 0) for c in reads]
    bytes_ = [int(c.get("bytes") or 0) for c in reads]
    gaps = [int(c.get("gap_us") or 0) for c in reads if int(c.get("gap_us") or 0) > 0]
    durs = [int(c.get("dur_us") or 0) for c in reads]
    ctr = Counter(blocks)

    def pct(xs: list[int], p: float) -> float:
        if not xs:
            return 0.0
        s = sorted(xs)
        i = min(len(s) - 1, max(0, int(round((p / 100.0) * (len(s) - 1)))))
        return float(s[i])

    return {
        "n": len(reads),
        "blocks_mode": ctr.most_common(1)[0][0],
        "blocks_hist": dict(sorted(ctr.items())),
        "bytes_p50": pct(bytes_, 50),
        "dur_us_p50": pct(durs, 50),
        "gap_us_p50": pct(gaps, 50) if gaps else None,
        "gap_us_p95": pct(gaps, 95) if gaps else None,
        "all_4kib": all(b == 8 for b in blocks),
        "head_gaps_ms": [
            round(g / 1000.0, 2)
            for g in gaps
            if 10_000 <= g <= 40_000
        ][:12],
    }


def cmd_q10(args: argparse.Namespace) -> int:
    http_json(f"{esp_base(args)}/api/lab/mess", "POST", {"reset": True, "enable": True, "mark": "q10_start"})
    if args.sit:
        http_json(
            f"{esp_base(args)}/api/lab/situation",
            "POST",
            {"name": args.sit, "holdMs": args.hold_ms or 600},
        )
    t_end = time.time() + args.wait
    last_n = 0
    while time.time() < t_end:
        time.sleep(1.0)
        out = http_json(f"{esp_base(args)}/api/lab/mess")
        n = len(out.get("cmds") or [])
        if n != last_n:
            print(f"cmds={n}", flush=True)
            last_n = n
    out = http_json(f"{esp_base(args)}/api/lab/mess")
    summary = summarize_q10(out.get("cmds") or [])
    result = {
        "cmdCapture": out.get("cmdCapture"),
        "mess": out.get("mess"),
        "q10": summary,
    }
    if args.out:
        Path(args.out).write_text(json.dumps({"raw": out, "summary": result}, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    if not out.get("cmdCapture"):
        print("WARN: not mess-fw build — flash pidrive-s3-mess", file=sys.stderr)
        return 2
    return 0 if summary.get("n", 0) > 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--esp", required=True, help="ESP base URL, e.g. http://192.168.178.88")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="version + mess + soft USB")
    sub.add_parser("reset", help="clear capture ring")

    p_sit = sub.add_parser("sit", help="run situation")
    p_sit.add_argument("name")
    p_sit.add_argument("--hold-ms", type=int, default=None)
    p_sit.add_argument("--keep-identity", action="store_true")
    p_sit.add_argument("--mark", default=None)
    p_sit.add_argument("--max-ms", type=int, default=None)

    p_usb = sub.add_parser("usb", help="soft USB attach/detach/cycle")
    g = p_usb.add_mutually_exclusive_group(required=True)
    g.add_argument("--attach", type=lambda s: s.lower() in ("1", "true", "yes"), nargs="?", const=True)
    g.add_argument("--detach", action="store_true")
    g.add_argument("--cycle-ms", type=int, default=None)
    p_usb.add_argument("--hold-ms", type=int, default=0)

    p_dump = sub.add_parser("dump", help="dump capture ring")
    p_dump.add_argument("-o", "--out", default=None)

    p_q10 = sub.add_parser("q10", help="reset, optional situation, wait, summarize READ10 sizes")
    p_q10.add_argument("--wait", type=float, default=15.0)
    p_q10.add_argument("--sit", default=None, help="e.g. usb_cycle or media_remount")
    p_q10.add_argument("--hold-ms", type=int, default=600)
    p_q10.add_argument("-o", "--out", default=None)

    args = ap.parse_args()
    if args.cmd == "usb" and getattr(args, "detach", False):
        args.attach = False
        args.cycle_ms = None

    try:
        if args.cmd == "status":
            return cmd_status(args)
        if args.cmd == "reset":
            return cmd_reset(args)
        if args.cmd == "sit":
            return cmd_sit(args)
        if args.cmd == "usb":
            return cmd_usb(args)
        if args.cmd == "dump":
            return cmd_dump(args)
        if args.cmd == "q10":
            return cmd_q10(args)
    except urllib.error.URLError as e:
        print(f"HTTP error: {e}", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

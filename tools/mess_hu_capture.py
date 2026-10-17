#!/usr/bin/env python3
"""Drive PiDrive mess-fw situations and dump READ10 command capture (Q10).

Soft USB (POST /api/lab/usb) toggles TinyUSB D+ pull-up — NOT VBUS / physical OTG.

Examples:
  python3 tools/mess_hu_capture.py --esp http://192.168.178.88 status
  python3 tools/mess_hu_capture.py --esp http://192.168.178.88 reset
  python3 tools/mess_hu_capture.py --esp http://192.168.178.88 sit usb_cycle --hold-ms 600
  python3 tools/mess_hu_capture.py --esp http://192.168.178.88 dump -o /tmp/mess-cmds.json
  python3 tools/mess_hu_capture.py --esp http://192.168.178.88 q10 --wait 20
  python3 tools/mess_hu_capture.py --esp http://192.168.178.88 arm --sit usb_cycle --timeout 25 -o /tmp/arm.json
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


# Field NBT (hu-probe S2 / EVID-HUPROBE-2026-10-15-004): CBW blocks often 8 and 240.
FIELD_CBW_BLOCKS = (8, 240)


def summarize_q10(cmds: list[dict]) -> dict[str, Any]:
    reads = [c for c in cmds if c.get("op") == 0x28 and (c.get("bytes") or 0) > 0]
    if not reads:
        return {"n": 0, "error": "no READ10 cmds"}
    blocks = [int(c.get("blocks") or 0) for c in reads]
    bytes_ = [int(c.get("bytes") or 0) for c in reads]
    gaps = [int(c.get("gap_us") or 0) for c in reads if int(c.get("gap_us") or 0) > 0]
    durs = [int(c.get("dur_us") or 0) for c in reads]
    ctr = Counter(blocks)
    n = len(reads)
    n8 = ctr.get(8, 0)
    n240 = ctr.get(240, 0)

    def pct(xs: list[int], p: float) -> float:
        if not xs:
            return 0.0
        s = sorted(xs)
        i = min(len(s) - 1, max(0, int(round((p / 100.0) * (len(s) - 1)))))
        return float(s[i])

    return {
        "n": n,
        "blocks_mode": ctr.most_common(1)[0][0],
        "blocks_hist": dict(sorted(ctr.items())),
        "blocks_8_share": round(n8 / n, 3),
        "blocks_240_share": round(n240 / n, 3),
        "field_cbw_blocks": list(FIELD_CBW_BLOCKS),
        "field_modes_seen": sorted(b for b in FIELD_CBW_BLOCKS if ctr.get(b)),
        "matches_field_cbw": bool(n8 or n240),
        "bytes_p50": pct(bytes_, 50),
        "dur_us_p50": pct(durs, 50),
        "gap_us_p50": pct(gaps, 50) if gaps else None,
        "gap_us_p95": pct(gaps, 95) if gaps else None,
        # Legacy: True only if *every* READ10 is 4 KiB — field NBT is often mixed 8+240.
        "all_4kib": all(b == 8 for b in blocks),
        "epistemic": (
            "blocks=CBW/command size (mess-fw); not TinyUSB 4 KiB callback chunks. "
            "Do not treat all_4kib=false as lab failure when 240 is present."
        ),
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


def _stream_fields(status: dict) -> dict[str, Any]:
    m = status.get("msc") or {}
    s = m.get("stream") or {}
    return {
        "play": status.get("playingName") or "",
        "uid": status.get("playingUid") or "",
        "stream": bool(s.get("active")),
        "host": int(s.get("hostAbsCursor") or 0),
        "abs": int(s.get("absEnd") or 0),
        "und": int(s.get("underruns") or 0),
        "armed": bool(s.get("cursorArmed")),
        "ser": m.get("usbSerial"),
        "reset": status.get("resetReason"),
        "uptime": status.get("uptime"),
    }


def decide_arm_stop(
    *,
    seen_play: bool,
    play: str,
    und: int,
    baseline_und: int,
    underrun_delta: int,
    stream: bool,
    host: int,
    abs_end: int,
    host_lag_blocks: int,
    host_stuck_abs_min: int,
    elapsed_s: float,
    host_stuck_grace_s: float,
    storm: bool = False,
) -> str | None:
    """Return stop reason or None to keep watching.

    storm=True (M30): only timeout stops — play_cleared/underrun/host_stuck would
    abort a Prefetch-Livelock window before LBA evidence accumulates.
    """
    if storm:
        return None
    if seen_play and not play:
        return "play_cleared"
    if (und - baseline_und) >= underrun_delta:
        return "underrun_spike"
    host_stuck = (
        stream
        and abs_end > host_stuck_abs_min
        and host > 0
        and abs_end > host + host_lag_blocks
    )
    if host_stuck and elapsed_s >= host_stuck_grace_s:
        return "host_stuck"
    return None


def cmd_arm(args: argparse.Namespace) -> int:
    """Arm MessCapture *before* Tip/OTG (or soft sit), then auto-stop on episode end.

    Stop reasons (field lesson 16.10.): play cleared after having play, underrun spike,
    host cursor stuck while abs advances, or timeout.
    """
    base = esp_base(args)
    mark = args.mark or "arm_window"
    http_json(
        f"{base}/api/lab/mess",
        "POST",
        {"enable": True, "reset": True, "mode": "ram_local", "mark": mark},
    )
    try:
        http_json(f"{base}/api/lab/situation", "POST", {"name": "mark", "mark": f"{mark}_armed"})
    except urllib.error.URLError:
        pass

    sit_out = None
    if args.sit:
        body: dict[str, Any] = {"name": args.sit, "holdMs": args.hold_ms or 600}
        if args.keep_identity:
            body["keepIdentity"] = True
        sit_out = http_json(f"{base}/api/lab/situation", "POST", body)
        print(f"sit {args.sit} ok={sit_out.get('ok')}", flush=True)
    elif args.usb_cycle_ms is not None:
        sit_out = http_json(f"{base}/api/lab/usb", "POST", {"cycleMs": args.usb_cycle_ms})
        print(f"usb cycleMs={args.usb_cycle_ms} ok={sit_out.get('ok')}", flush=True)

    t0 = time.time()
    deadline = t0 + args.timeout
    samples: list[dict[str, Any]] = []
    seen_play = False
    baseline_und: int | None = None
    stop_reason = "timeout"
    poll = max(0.2, float(args.poll))

    while time.time() < deadline:
        st = http_json(f"{base}/api/status")
        f = _stream_fields(st)
        f["t"] = round(time.time() - t0, 2)
        samples.append(f)
        if baseline_und is None:
            baseline_und = f["und"]
        if f["play"]:
            seen_play = True
        und_delta = f["und"] - (baseline_und or 0)
        reason = decide_arm_stop(
            seen_play=seen_play,
            play=f["play"],
            und=f["und"],
            baseline_und=baseline_und or 0,
            underrun_delta=args.underrun_delta,
            stream=f["stream"],
            host=f["host"],
            abs_end=f["abs"],
            host_lag_blocks=args.host_lag_blocks,
            host_stuck_abs_min=args.host_stuck_abs_min,
            elapsed_s=time.time() - t0,
            host_stuck_grace_s=args.host_stuck_grace_s,
            storm=bool(getattr(args, "storm", False)),
        )
        if reason:
            stop_reason = reason
            break
        mode = "storm" if getattr(args, "storm", False) else "arm"
        print(
            f"t={f['t']:5.1f} [{mode}] play={f['play']!r} stream={f['stream']} "
            f"host={f['host']} abs={f['abs']} und={f['und']} (+{und_delta})",
            flush=True,
        )
        time.sleep(poll)

    stop = http_json(
        f"{base}/api/lab/mess",
        "POST",
        {"stop": True, "reason": stop_reason, "mark": f"{mark}_stop"},
    )
    mess = http_json(f"{base}/api/lab/mess")
    cmds = mess.get("cmds") or []
    # paginate if API supports after=
    after = 0
    all_cmds = list(cmds)
    for _ in range(40):
        page = http_json(f"{base}/api/lab/mess?after={after}")
        page_cmds = page.get("cmds") or []
        if not page_cmds:
            break
        all_cmds.extend(page_cmds)
        seqs = [c.get("seq") for c in page_cmds if c.get("seq") is not None]
        nxt = page.get("nextAfter") or page.get("nextSeq") or page.get("next")
        if nxt is None and seqs:
            nxt = max(seqs)
        if nxt is None or int(nxt) <= after:
            break
        after = int(nxt)
        if page.get("hasMore", page.get("more")) is False:
            break

    # de-dup by seq if present
    seen: set[Any] = set()
    uniq: list[dict] = []
    for c in all_cmds:
        key = c.get("seq")
        if key is not None:
            if key in seen:
                continue
            seen.add(key)
        uniq.append(c)
    summary = summarize_q10(uniq)
    result = {
        "ok": True,
        "stop_reason": stop_reason,
        "elapsed_s": round(time.time() - t0, 2),
        "seen_play": seen_play,
        "baseline_und": baseline_und,
        "samples": samples,
        "sit": sit_out,
        "stop": {"ok": stop.get("ok"), "mess": stop.get("mess")},
        "cmdCapture": mess.get("cmdCapture"),
        "n_cmds": len(uniq),
        "q10": summary,
    }
    if args.out:
        Path(args.out).write_text(
            json.dumps({"result": result, "commands": uniq}, indent=2),
            encoding="utf-8",
        )
        print(f"wrote {args.out}", flush=True)
    print(json.dumps({k: result[k] for k in result if k != "samples"}, indent=2))
    return 0 if mess.get("cmdCapture") else 2


def self_test() -> int:
    """Offline checks for field-aware Q10 summary (no ESP)."""
    mixed = [
        {"op": 0x28, "blocks": 8, "bytes": 4096, "gap_us": 3700, "dur_us": 3800},
        {"op": 0x28, "blocks": 8, "bytes": 4096, "gap_us": 3710, "dur_us": 3810},
        {"op": 0x28, "blocks": 240, "bytes": 122880, "gap_us": 90000, "dur_us": 95000},
        {"op": 0x28, "blocks": 240, "bytes": 122880, "gap_us": 91000, "dur_us": 96000},
    ]
    s = summarize_q10(mixed)
    assert s["n"] == 4
    assert s["all_4kib"] is False
    assert s["matches_field_cbw"] is True
    assert s["blocks_8_share"] == 0.5
    assert s["blocks_240_share"] == 0.5
    assert s["field_modes_seen"] == [8, 240]
    only8 = summarize_q10(mixed[:2])
    assert only8["all_4kib"] is True
    assert only8["matches_field_cbw"] is True
    # arm helper: stream field extraction shape
    fake = {
        "playingName": "X",
        "playingUid": "fav0",
        "resetReason": "software",
        "uptime": "1s",
        "msc": {"usbSerial": "PD0001", "stream": {
            "active": True, "hostAbsCursor": 100, "absEnd": 5000, "underruns": 10, "cursorArmed": True,
        }},
    }
    f = _stream_fields(fake)
    assert f["play"] == "X" and f["host"] == 100 and f["und"] == 10
    assert decide_arm_stop(
        seen_play=True, play="", und=0, baseline_und=0, underrun_delta=50_000,
        stream=False, host=0, abs_end=0, host_lag_blocks=8000,
        host_stuck_abs_min=20_000, elapsed_s=1.0, host_stuck_grace_s=3.0,
    ) == "play_cleared"
    assert decide_arm_stop(
        seen_play=False, play="", und=60_000, baseline_und=0, underrun_delta=50_000,
        stream=True, host=100, abs_end=100_000, host_lag_blocks=8000,
        host_stuck_abs_min=20_000, elapsed_s=1.0, host_stuck_grace_s=3.0,
    ) == "underrun_spike"
    assert decide_arm_stop(
        seen_play=False, play="", und=0, baseline_und=0, underrun_delta=50_000,
        stream=True, host=100, abs_end=100_000, host_lag_blocks=8000,
        host_stuck_abs_min=20_000, elapsed_s=4.0, host_stuck_grace_s=3.0,
    ) == "host_stuck"
    assert decide_arm_stop(
        seen_play=False, play="X", und=0, baseline_und=0, underrun_delta=50_000,
        stream=False, host=0, abs_end=0, host_lag_blocks=8000,
        host_stuck_abs_min=20_000, elapsed_s=1.0, host_stuck_grace_s=3.0,
    ) is None
    assert decide_arm_stop(
        seen_play=True, play="", und=0, baseline_und=0, underrun_delta=50_000,
        stream=False, host=0, abs_end=0, host_lag_blocks=8000,
        host_stuck_abs_min=20_000, elapsed_s=1.0, host_stuck_grace_s=3.0,
        storm=True,
    ) is None
    print("self_test OK", json.dumps({
        "mixed_all_4kib": s["all_4kib"],
        "mixed_matches_field": s["matches_field_cbw"],
        "hist": s["blocks_hist"],
        "arm_fields": f["play"],
        "storm_ignores_play_clear": True,
    }))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--esp", default="", help="ESP base URL, e.g. http://192.168.178.88")
    ap.add_argument("--self-test", action="store_true", help="offline Q10 summary checks")
    sub = ap.add_subparsers(dest="cmd", required=False)

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

    p_arm = sub.add_parser(
        "arm",
        help="arm capture BEFORE tip/OTG/soft-sit; auto-stop on play clear / underrun / host-stuck",
    )
    p_arm.add_argument("--sit", default=None, help="situation after arm, e.g. usb_cycle")
    p_arm.add_argument("--usb-cycle-ms", type=int, default=None, help="soft USB cycle after arm")
    p_arm.add_argument("--hold-ms", type=int, default=600)
    p_arm.add_argument("--keep-identity", action="store_true")
    p_arm.add_argument("--timeout", type=float, default=30.0)
    p_arm.add_argument("--poll", type=float, default=0.4)
    p_arm.add_argument("--underrun-delta", type=int, default=50000,
                       help="stop when underruns rise by this much vs baseline")
    p_arm.add_argument("--host-lag-blocks", type=int, default=8000,
                       help="abs-host lag that counts as stuck (blocks)")
    p_arm.add_argument("--host-stuck-abs-min", type=int, default=20000)
    p_arm.add_argument("--host-stuck-grace-s", type=float, default=3.0)
    p_arm.add_argument("--mark", default="arm_window")
    p_arm.add_argument(
        "--storm",
        action="store_true",
        help="M30 Storm window: ignore play_cleared/underrun/host_stuck; stop only on --timeout",
    )
    p_arm.add_argument("-o", "--out", default=None)

    args = ap.parse_args()
    if args.self_test:
        return self_test()
    if not args.esp or not args.cmd:
        ap.error("--esp and a subcommand are required (or pass --self-test)")
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
        if args.cmd == "arm":
            return cmd_arm(args)
    except urllib.error.URLError as e:
        print(f"HTTP error: {e}", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

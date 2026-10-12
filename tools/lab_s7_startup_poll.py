#!/usr/bin/env python3
"""S7 startup timing: measure time-to-usable after stall arm (scope-1 head-play gate).

Polls /api/status and records first transitions:
  firstRead, playGuess, stall.armed, playingUid, stall.retries growth.

Examples:
  python3 tools/lab_s7_startup_poll.py --esp http://192.168.178.88 --seconds 90
  python3 tools/lab_s7_startup_poll.py --esp http://192.168.178.89 --arm-stall --out artifacts/s7
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def http_json(url: str, method: str = "GET", body: dict | None = None, timeout: float = 8) -> dict:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def main() -> int:
    ap = argparse.ArgumentParser(description="S7 startup / stall-armed poll")
    ap.add_argument("--esp", default="http://192.168.178.88")
    ap.add_argument("--seconds", type=float, default=120.0)
    ap.add_argument("--hz", type=float, default=4.0)
    ap.add_argument("--arm-stall", action="store_true", help="POST stallEnable=true scope=1 maxMs=1000")
    ap.add_argument("--out", type=Path, default=Path("artifacts/lab-s7-startup"))
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    esp = args.esp.rstrip("/")

    if args.arm_stall:
        cfg = http_json(
            f"{esp}/api/config",
            "POST",
            {
                "stallEnable": True,
                "stallScope": 1,
                "stallTimer": 0,
                "stallMaxMs": 1000,
                "stallChunkBytes": 4096,
                "stallRetryMs": 2,
            },
        )
        (args.out / "config-arm.json").write_text(json.dumps(cfg, indent=2))

    t0 = time.monotonic()
    marks: dict[str, float] = {}
    rows: list[dict[str, Any]] = []
    last_serial = None
    interval = 1.0 / max(0.5, args.hz)

    print(f"S7 poll {esp} for {args.seconds}s — OTG/play now")
    while time.monotonic() - t0 < args.seconds:
        try:
            st = http_json(f"{esp}/api/status")
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            rows.append({"t": round(time.monotonic() - t0, 3), "error": str(e)})
            time.sleep(interval)
            continue
        m = st.get("msc") or {}
        stall = m.get("stall") or {}
        s = (st.get("stream") if isinstance(st.get("stream"), dict) else None) or m.get("stream") or {}
        t = time.monotonic() - t0
        serial = m.get("usbSerial")
        row = {
            "t": round(t, 3),
            "uptime": st.get("uptime"),
            "serial": serial,
            "playingUid": st.get("playingUid") or "",
            "playGuessCount": m.get("playGuessCount"),
            "playRejectCount": m.get("playRejectCount"),
            "msPlugToFirstRead": m.get("msPlugToFirstRead"),
            "msPlugToPlayGuess": m.get("msPlugToPlayGuess"),
            "stall_enable": stall.get("enable"),
            "stall_armed": stall.get("armed"),
            "stall_skipNotArmed": stall.get("skipNotArmed"),
            "stall_retries": stall.get("retries"),
            "stall_timeouts": stall.get("timeouts"),
            "absEnd": s.get("absEnd"),
            "stream_active": s.get("active"),
        }
        rows.append(row)

        def mark(name: str, cond: bool) -> None:
            if cond and name not in marks:
                marks[name] = round(t, 3)
                print(f"  MARK {name} @ {marks[name]}s  serial={serial} play={row['playingUid']}")

        if serial and serial != last_serial:
            if last_serial is not None:
                marks.clear()  # new plug episode
                print(f"  serial {last_serial} → {serial} (reset marks)")
            last_serial = serial
            mark("serial_seen", True)
        mark("first_read_fw", bool(m.get("msPlugToFirstRead")))
        mark("play_guess_fw", bool(m.get("msPlugToPlayGuess")))
        mark("stall_armed", stall.get("armed") is True)
        mark("playingUid", bool(st.get("playingUid")))
        mark("retries_gt0", int(stall.get("retries") or 0) > 0)
        time.sleep(interval)

    summary = {
        "esp": esp,
        "seconds": args.seconds,
        "marks_s": marks,
        "note": "scope=1 expects stall_armed only after play.guess; skipNotArmed should rise before that",
    }
    (args.out / "poll.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

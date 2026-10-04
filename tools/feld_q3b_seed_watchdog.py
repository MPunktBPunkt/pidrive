#!/usr/bin/env python3
"""Watch bodySeed.active / uptime / bytesServed until Auto-Next burst or timeout.

Fails loudly if the RAM seed dies (reboot or clear) before bytesServed rises.
Use after feld_q3b_next_prepare.sh GO gate.

Example:
  python3 tools/feld_q3b_seed_watchdog.py --esp http://192.168.178.89 \\
    --out docs/betrieb/artifacts-.../feld-q3b-next-XXXX --minutes 4
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.request
from pathlib import Path


def http_json(url: str, timeout: float = 4.0) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode())


def parse_uptime_s(text: str | None) -> int | None:
    if not text:
        return None
    s = 0
    for n, unit in re.findall(r"(\d+)\s*(h|min|s)", text):
        n = int(n)
        if unit == "h":
            s += n * 3600
        elif unit == "min":
            s += n * 60
        else:
            s += n
    return s if s or text.strip() == "0s" else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--esp", default="http://192.168.178.89")
    ap.add_argument("--out", required=True, help="artifact dir")
    ap.add_argument("--minutes", type=float, default=4.0)
    ap.add_argument("--interval", type=float, default=1.0)
    ap.add_argument("--min-seed-bytes", type=int, default=65536)
    args = ap.parse_args()
    esp = args.esp.rstrip("/")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    log = out / "seed_watchdog.log"

    def emit(msg: str) -> None:
        line = f"{time.strftime('%H:%M:%S')} {msg}"
        print(line, flush=True)
        with log.open("a") as f:
            f.write(line + "\n")

    try:
        st0 = http_json(f"{esp}/api/status")
    except Exception as e:
        emit(f"ABORT cannot reach ESP: {e}")
        return 2

    bs0 = (st0.get("msc") or {}).get("bodySeed") or {}
    if not bs0.get("active"):
        emit(f"ABORT seed not active at start: {bs0}")
        (out / "status-watchdog-abort.json").write_text(json.dumps(st0, indent=2))
        return 2

    up0 = parse_uptime_s(st0.get("uptime"))
    seed0 = int(bs0.get("bytesServed") or 0)
    emit(
        f"START active=True tag={bs0.get('tag')!r} seedB={seed0} "
        f"uptime={st0.get('uptime')!r} ({up0}s) cold={st0['msc'].get('coldBodyBurstCount')}"
    )
    (out / "status-watchdog-start.json").write_text(json.dumps(st0, indent=2))

    t_end = time.time() + args.minutes * 60
    prev_key = None
    while time.time() < t_end:
        try:
            st = http_json(f"{esp}/api/status")
        except Exception as e:
            emit(f"WARN status: {e}")
            time.sleep(args.interval)
            continue
        m = st.get("msc") or {}
        bs = m.get("bodySeed") or {}
        active = bool(bs.get("active"))
        seed = int(bs.get("bytesServed") or 0)
        up = parse_uptime_s(st.get("uptime"))
        play = st.get("playingUid") or "-"
        cold = m.get("coldBodyBurstCount")
        key = (play, active, seed // 4096, cold, up // 5 if up is not None else None)
        if key != prev_key:
            emit(
                f"play={play} active={active} seedB={seed} cold={cold} "
                f"uptime={st.get('uptime')!r}"
            )
            prev_key = key

        if not active:
            emit("FAIL seed became inactive (reboot or clear)")
            (out / "status-watchdog-fail.json").write_text(json.dumps(st, indent=2))
            return 1
        if up0 is not None and up is not None and up + 15 < up0:
            emit(f"FAIL uptime collapsed {up0}s → {up}s (reboot)")
            (out / "status-watchdog-fail.json").write_text(json.dumps(st, indent=2))
            return 1
        if seed - seed0 >= args.min_seed_bytes:
            emit(f"PASS bytesServed rose {seed0} → {seed} (delta {seed - seed0})")
            (out / "status-watchdog-pass.json").write_text(json.dumps(st, indent=2))
            return 0
        time.sleep(args.interval)

    emit(f"TIMEOUT {args.minutes} min — seed still active, no bytesServed rise ≥ {args.min_seed_bytes}")
    try:
        st = http_json(f"{esp}/api/status")
        (out / "status-watchdog-timeout.json").write_text(json.dumps(st, indent=2))
    except Exception:
        pass
    return 3


if __name__ == "__main__":
    sys.exit(main())

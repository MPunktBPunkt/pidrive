#!/usr/bin/env python3
"""Per-read HU trace from the ESP ring `mscTrace` (/api/metrics), no FW change.

The ESP keeps the last 96 READ10 callbacks (ms, gap, lba, n, kind, tag). At 250
reads/s the ring covers ~384 ms, so a poll at >= 3 Hz loses nothing. Unlike the
PUMP `msc.reads` bursts (merged by time/count, may hide LBA jumps) every row
here is one 4 KiB callback in host order.

Trace `ms` is ESP millis(), the same clock as PUMP `msc.reads` -> join on ms.
`wall_est` uses uptimeMs (= millis() - bootMs) and is therefore late by the
constant bootMs of that boot (setup time, typically < 2 s); use it only to
place reads next to operator marks.

Output:
  <out>             one JSON row per trace entry, deduplicated, ESP ms + wall_est
  <out>.polls.jsonl one row per poll: wall, uptimeMs, readCount, new, lost

  python3 tools/feld_trace_poll.py --esp http://192.168.178.89 --hz 4 \\
      --out docs/betrieb/artifacts-.../trace.jsonl --seconds 1800
  python3 tools/feld_trace_poll.py --self-test
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.request
from collections import deque
from datetime import datetime
from pathlib import Path

TRACE_SIZE = 96


def http_json(url: str, timeout: float) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode())


def entry_key(e: dict) -> tuple:
    return (int(e.get("ms") or 0), int(e.get("lba") or 0), int(e.get("gap") or 0))


class TraceMerger:
    """Dedupe overlapping ring snapshots; count reads the ring dropped between polls."""

    def __init__(self, memory: int = 4 * TRACE_SIZE):
        self.seen: set[tuple] = set()
        self.order: deque[tuple] = deque()
        self.memory = memory
        self.last_rc: int | None = None
        self.last_uptime: int | None = None

    def feed(self, trace: list[dict], read_count: int | None, uptime_ms: int | None) -> tuple[list[dict], int, bool]:
        """Return (new_entries, lost_estimate, reboot)."""
        reboot = (
            uptime_ms is not None and self.last_uptime is not None and uptime_ms < self.last_uptime
        )
        if reboot:
            self.seen.clear()
            self.order.clear()
            self.last_rc = None
        new = []
        for e in trace or []:
            k = entry_key(e)
            if k in self.seen:
                continue
            self.seen.add(k)
            self.order.append(k)
            new.append(e)
        while len(self.order) > self.memory:
            self.seen.discard(self.order.popleft())
        lost = 0
        if read_count is not None and self.last_rc is not None and read_count >= self.last_rc:
            lost = max(0, (read_count - self.last_rc) - len(new))
        if read_count is not None:
            self.last_rc = read_count
        if uptime_ms is not None:
            self.last_uptime = uptime_ms
        return new, lost, reboot


def main() -> int:
    ap = argparse.ArgumentParser(description="mscTrace poller (/api/metrics)")
    ap.add_argument("--esp", default="http://192.168.178.89")
    ap.add_argument("--out", help="trace JSONL")
    ap.add_argument("--hz", type=float, default=4.0)
    ap.add_argument("--seconds", type=float, default=1800.0)
    ap.add_argument("--timeout", type=float, default=1.5)
    ap.add_argument("--append", action="store_true")
    ap.add_argument("--print", action="store_true", dest="do_print")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        return self_test()
    if not args.out:
        ap.error("--out required")

    esp = args.esp.rstrip("/")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    polls_path = out.with_name(out.name + ".polls.jsonl")
    mode = "a" if args.append else "w"
    period = 1.0 / max(0.1, args.hz)
    merger = TraceMerger()
    t_end = time.monotonic() + args.seconds
    n_rows = n_lost = n_err = n_polls = 0
    with out.open(mode, encoding="utf-8") as fo, polls_path.open(mode, encoding="utf-8") as fp:
        while time.monotonic() < t_end:
            t0 = time.monotonic()
            wall = time.time()
            try:
                st = http_json(f"{esp}/api/metrics", args.timeout)
                m = st.get("msc") or {}
                rc = m.get("readCount")
                up = st.get("uptimeMs")
                new, lost, reboot = merger.feed(st.get("mscTrace") or [], rc, up)
                for e in new:
                    row = dict(e)
                    if up is not None and e.get("ms") is not None:
                        # wall time of the read: poll wall minus (uptime now - read ms)
                        row["wall_est"] = round(wall - (int(up) - int(e["ms"])) / 1000.0, 3)
                    fo.write(json.dumps(row, separators=(",", ":")) + "\n")
                fo.flush()
                n_rows += len(new)
                n_lost += lost
                poll = {"wall": round(wall, 3), "wall_iso": datetime.fromtimestamp(wall).astimezone().isoformat(timespec="milliseconds"),
                        "uptimeMs": up, "readCount": rc, "new": len(new), "lost": lost,
                        "reboot": reboot, "playingUid": st.get("playingUid") or "",
                        "rtt_ms": round((time.monotonic() - t0) * 1000.0, 1)}
            except Exception as e:  # keep polling through Wi-Fi drops / ESP reboot
                n_err += 1
                poll = {"wall": round(wall, 3), "error": str(e)[:120]}
            fp.write(json.dumps(poll, separators=(",", ":")) + "\n")
            fp.flush()
            n_polls += 1
            if args.do_print and ("error" in poll or poll.get("lost") or poll.get("new")):
                print(poll.get("wall_iso", poll["wall"]), "new", poll.get("new"), "lost", poll.get("lost"),
                      "rc", poll.get("readCount"), poll.get("error", ""), flush=True)
            sleep = period - (time.monotonic() - t0)
            if sleep > 0:
                time.sleep(sleep)
    print(f"DONE polls={n_polls} rows={n_rows} lost={n_lost} errors={n_err} out={out}", flush=True)
    return 0


def self_test() -> int:
    m = TraceMerger()

    def mk(i: int) -> dict:
        return {"ms": 1000 + 4 * i, "gap": 4, "lba": 81 + 8 * i, "n": 4096, "kind": "file"}

    new, lost, _ = m.feed([mk(i) for i in range(0, 96)], 96, 2000)
    assert len(new) == 96 and lost == 0
    new, lost, _ = m.feed([mk(i) for i in range(50, 146)], 146, 2400)
    assert len(new) == 50 and lost == 0, (len(new), lost)
    # ring overran: readCount +200 but only 96 visible, 0 overlap
    new, lost, _ = m.feed([mk(i) for i in range(250, 346)], 346, 3200)
    assert len(new) == 96 and lost == 104, (len(new), lost)
    # reboot: uptime goes back, counters restart
    new, lost, reboot = m.feed([mk(0)], 1, 500)
    assert reboot and len(new) == 1 and lost == 0
    print("self-test PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

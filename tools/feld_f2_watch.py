#!/usr/bin/env python3
"""F2 field watcher: classify cache hit/miss from 1 Hz status deltas.

Heuristics (not proof alone):
  cold_burst  — readCount jumps ≥ ~80 in ≤2 s while a fav is active
  cache_hit   — playingUid set/changed, readCount flat ≥5 s, hostAbs≈0
  remount     — readCount drops sharply (ESP reset) or serial changes

Example:
  python3 tools/feld_f2_watch.py --esp http://192.168.178.89 \\
      --out …/f2-watch.jsonl --seconds 300
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.request
from datetime import datetime
from pathlib import Path


def http_json(url: str, timeout: float = 4.0) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode())


def wall_now() -> str:
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


def snap(esp: str) -> dict:
    st = http_json(f"{esp}/api/status")
    m = st.get("msc") or {}
    stream = m.get("stream") or {}
    slots = {}
    for s in m.get("slotMap") or []:
        if isinstance(s, dict) and s.get("uid"):
            slots[s["uid"]] = {
                "b": s.get("b", s.get("bytes")),
                "maxSeq": s.get("maxSeq"),
            }
    return {
        "wall_iso": wall_now(),
        "playingUid": st.get("playingUid") or "",
        "readCount": int(m.get("readCount") or 0),
        "hostAbs": int(stream.get("hostAbsCursor") or 0),
        "underruns": int(stream.get("underruns") or 0),
        "serial": m.get("usbSerial") or "",
        "slots": slots,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="F2 cache hit/miss watcher")
    ap.add_argument("--esp", default="http://192.168.178.89")
    ap.add_argument("--out", required=True)
    ap.add_argument("--seconds", type=float, default=300.0)
    ap.add_argument("--interval", type=float, default=1.0)
    args = ap.parse_args()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    esp = args.esp.rstrip("/")
    t_end = time.monotonic() + args.seconds
    prev: dict | None = None
    flat = 0
    print(f"F2 watch → {out}  ({args.seconds}s)", flush=True)
    print("Sequence tip: fav1→EOF→fav2→fav1 then OTG remount→fav1", flush=True)

    with out.open("w", encoding="utf-8") as f:
        while time.monotonic() < t_end:
            try:
                cur = snap(esp)
            except Exception as e:
                cur = {"wall_iso": wall_now(), "error": str(e)}
            label = ""
            detail: dict = {}
            if prev and "error" not in cur and "error" not in prev:
                d_rc = cur["readCount"] - prev["readCount"]
                if cur["serial"] and prev["serial"] and cur["serial"] != prev["serial"]:
                    label = "serial_change"
                    detail = {"from": prev["serial"], "to": cur["serial"]}
                elif d_rc <= -50:
                    label = "remount_or_rst"
                    detail = {"d_rc": d_rc}
                elif d_rc >= 80:
                    label = "cold_burst"
                    detail = {"d_rc": d_rc, "≈KiB": d_rc * 4}
                elif cur["playingUid"] != prev["playingUid"]:
                    label = "uid_change"
                    detail = {"from": prev["playingUid"], "to": cur["playingUid"]}
                    flat = 0
                elif cur["playingUid"] and d_rc == 0 and cur["hostAbs"] == 0:
                    flat += 1
                    if flat == 5:
                        label = "cache_hit_like"
                        detail = {"flat_s": flat, "uid": cur["playingUid"]}
                else:
                    flat = 0 if d_rc else flat

            row = {**cur, "label": label or None, "detail": detail or None}
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            if "error" in cur:
                print(cur["wall_iso"], "ERR", cur["error"], flush=True)
            else:
                print(
                    cur["wall_iso"],
                    f"uid={cur['playingUid']!r}",
                    f"rc={cur['readCount']}",
                    f"host={cur['hostAbs']}",
                    f"label={label or '-'}",
                    flush=True,
                )
            prev = cur if "error" not in cur else prev
            time.sleep(args.interval)

    print(f"DONE out={out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

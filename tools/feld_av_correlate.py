#!/usr/bin/env python3
"""Field/Lab helper: correlate HU MSC reads vs stream window + liveBytes.

Reads status JSON (+ optional msc_reads.jsonl) and scores whether observed
body LBAs map into absBase..absEnd for a slot.

Example (live):
  python3 tools/feld_av_correlate.py --esp http://192.168.178.89 --watch-s 90

Example (offline artifact):
  python3 tools/feld_av_correlate.py --status path/status.json --reads path/pidrive_msc_reads.jsonl
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.request
from pathlib import Path


def http_json(url: str, timeout: float = 4.0) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode())


def slot_for_lba(slots: list[dict], lba: int) -> dict | None:
    for s in slots:
        a, b = int(s.get("lba0") or -1), int(s.get("lba1") or -1)
        if a <= lba <= b:
            return s
    return None


def analyze(status: dict, reads: list[dict] | None = None) -> dict:
    m = status.get("msc") or {}
    stream = m.get("stream") or {}
    slots = m.get("slotMap") or []
    abs_base = int(stream.get("absBase") or 0)
    abs_end = int(stream.get("absEnd") or 0)
    host_abs = int(stream.get("hostAbsCursor") or 0)
    sb = int(m.get("streamBytes") or 0)
    ud = int(stream.get("underruns") or 0)
    live = sb - ud
    uid = stream.get("uid") or status.get("playingUid") or ""
    seed = m.get("bodySeed") or {}

    in_window = abs_end > abs_base and abs_base <= host_abs < abs_end
    out: dict = {
        "play": status.get("playingUid"),
        "stream_uid": stream.get("uid"),
        "stream_active": stream.get("active"),
        "abs": [abs_base, abs_end],
        "hostAbsCursor": host_abs,
        "host_in_window": in_window,
        "streamBytes": sb,
        "underruns": ud,
        "liveBytes": live,
        "seed_active": seed.get("active"),
        "seed_bytesServed": seed.get("bytesServed"),
        "reads": None,
    }

    if reads is not None:
        body = []
        in_n = out_n = 0
        for r in reads:
            l0 = int(r.get("lba0") or 0)
            l1 = int(r.get("lba1") or l0)
            slot = slot_for_lba(slots, l0)
            if not slot:
                continue
            # fileOff for start of read
            file_off = (l0 - int(slot["lba0"])) * 512
            inside = abs_end > abs_base and abs_base <= file_off < abs_end and (
                not uid or slot.get("uid") == uid or slot.get("uid") == status.get("playingUid")
            )
            if inside:
                in_n += 1
            else:
                out_n += 1
            if r.get("bytes", 0) >= 8192:
                body.append(
                    {
                        "lba0": l0,
                        "lba1": l1,
                        "bytes": r.get("bytes"),
                        "uid": slot.get("uid"),
                        "file_off": file_off,
                        "in_window": inside,
                    }
                )
        out["reads"] = {
            "lines": len(reads),
            "heavy": body[-20:],
            "heavy_in_window": in_n,
            "heavy_out_window": out_n,
        }
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--esp", default="")
    ap.add_argument("--status", default="")
    ap.add_argument("--reads", default="")
    ap.add_argument("--watch-s", type=float, default=0)
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    rows = []
    if args.esp and args.watch_s > 0:
        esp = args.esp.rstrip("/")
        t_end = time.time() + args.watch_s
        prev = None
        while time.time() < t_end:
            try:
                st = http_json(f"{esp}/api/status")
            except Exception as e:
                print(f"{time.strftime('%H:%M:%S')} ERR {e}", flush=True)
                time.sleep(1)
                continue
            a = analyze(st)
            key = (
                a["play"],
                a["hostAbsCursor"] // 4096,
                a["liveBytes"] // 8192,
                a["underruns"] // 8192,
                a["seed_bytesServed"],
            )
            if key != prev:
                print(
                    f"{time.strftime('%H:%M:%S')} play={a['play']} hostAbs={a['hostAbsCursor']} "
                    f"win={a['abs']} in={a['host_in_window']} live={a['liveBytes']} "
                    f"und={a['underruns']} seedB={a['seed_bytesServed']}",
                    flush=True,
                )
                rows.append({"ts": time.time(), **a})
                prev = key
            time.sleep(1)
        st = http_json(f"{esp}/api/status")
        final = analyze(st)
    elif args.status:
        st = json.loads(Path(args.status).read_text())
        reads = None
        if args.reads:
            reads = [json.loads(l) for l in Path(args.reads).read_text().splitlines() if l.strip()]
        final = analyze(st, reads)
        print(json.dumps(final, indent=2))
    else:
        raise SystemExit("need --esp --watch-s or --status [--reads]")

    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "correlate-final.json").write_text(json.dumps(final, indent=2))
        if rows:
            (out / "correlate-watch.jsonl").write_text(
                "\n".join(json.dumps(r) for r in rows) + "\n"
            )
        print(f"OUT={out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

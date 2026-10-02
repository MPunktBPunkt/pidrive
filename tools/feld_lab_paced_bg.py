#!/usr/bin/env python3
"""Background paced MSC read for lab 60s dry-run (run on Proxmox host)."""
from __future__ import annotations

import argparse
import json
import subprocess
import time
import urllib.request


def get(esp: str) -> dict:
    return json.load(urllib.request.urlopen(esp + "/api/status", timeout=5))


def stream_of(st: dict) -> dict:
    s = st.get("stream")
    if isinstance(s, dict) and s:
        return s
    return (st.get("msc") or {}).get("stream") or {}


def dd(dev: str, lba: int, sectors: int = 8) -> None:
    for _ in range(5):
        try:
            subprocess.check_call(
                [
                    "dd",
                    f"if={dev}",
                    "bs=512",
                    f"skip={lba}",
                    f"count={sectors}",
                    "iflag=direct",
                    "status=none",
                    "of=/dev/null",
                ],
                stderr=subprocess.DEVNULL,
            )
            return
        except subprocess.CalledProcessError:
            time.sleep(0.2)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--esp", default="http://192.168.178.88")
    ap.add_argument("--dev", default="/dev/sda")
    ap.add_argument("--uid", default="fav0")
    ap.add_argument("--seconds", type=float, default=60.0)
    ap.add_argument("--kib-per-s", type=float, default=6.0)
    args = ap.parse_args()

    st = get(args.esp)
    slot = next(x for x in st["msc"]["slotMap"] if x["uid"] == args.uid)
    lba0 = int(slot["lba0"])
    interval = (8 * 512) / (args.kib_per_s * 1024.0)
    print(f"paced uid={args.uid} lba0={lba0} secs={args.seconds} interval={interval:.3f}", flush=True)
    off = 0
    t_end = time.time() + args.seconds
    n = 0
    while time.time() < t_end:
        dd(args.dev, lba0 + off, 8)
        off = (off + 8) % 900
        n += 1
        time.sleep(max(0.0, interval))
    st2 = get(args.esp)
    s = stream_of(st2)
    m = st2["msc"]
    print(
        f"done chunks={n} streamBytes={m.get('streamBytes')} under={s.get('underruns')} uid={s.get('uid')}",
        flush=True,
    )


if __name__ == "__main__":
    main()

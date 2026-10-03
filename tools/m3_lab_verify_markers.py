#!/usr/bin/env python3
"""Verify M3 PDMK markers in ESP MSC slot via Linux host dd (Lab).

Matches Mp3Silence.h: ID3+Info head 252 B, frames 156 B, marker every 180000 body bytes.
Stamp at frame bytes 4..9: 'P','D','M','K', idx_hi, idx_lo.

Example:
  python3 tools/m3_lab_verify_markers.py --esp http://192.168.178.88 --host root@192.168.178.108
"""
from __future__ import annotations

import argparse
import json
import struct
import subprocess
import urllib.request


HEAD = 252
FRAME = 156
INTERVAL = 180000  # body bytes
MAGIC = b"PDMK"


def http_json(url: str):
    with urllib.request.urlopen(url, timeout=8) as r:
        return json.loads(r.read().decode())


def ssh_bytes(host: str, cmd: str) -> bytes:
    return subprocess.check_output(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", host, cmd]
    )


def read_lba(host: str, dev: str, lba: int, sectors: int = 8) -> bytes:
    # dd to stdout
    cmd = (
        f"dd if={dev} bs=512 skip={lba} count={sectors} iflag=direct status=none 2>/dev/null"
    )
    return ssh_bytes(host, cmd)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--esp", default="http://192.168.178.88")
    ap.add_argument("--host", default="root@192.168.178.108")
    ap.add_argument("--dev", default="/dev/sda")
    ap.add_argument("--uid", default="fav0")
    ap.add_argument("--max-markers", type=int, default=6)
    args = ap.parse_args()

    st = http_json(args.esp.rstrip("/") + "/api/status")
    m = st["msc"]
    slot = next(s for s in m["slotMap"] if s["uid"] == args.uid)
    lba0 = int(slot["lba0"])
    lba1 = int(slot["lba1"])
    slot_bytes = (lba1 - lba0 + 1) * 512
    body = max(0, slot_bytes - HEAD)
    nmark = body // INTERVAL + 1
    nmark = min(nmark, args.max_markers)

    results = []
    ok_n = 0
    for idx in range(nmark):
        body_off = (idx * INTERVAL // FRAME) * FRAME
        file_off = HEAD + body_off
        if file_off + 10 > slot_bytes:
            break
        # stamp at frame+4 .. +9 → absolute file_off+4
        abs_off = file_off + 4
        lba = lba0 + abs_off // 512
        within = abs_off % 512
        blob = read_lba(args.host, args.dev, lba, 2)
        got = blob[within : within + 6]
        expect = MAGIC + struct.pack(">H", idx)
        ok = got == expect
        if ok:
            ok_n += 1
        results.append(
            {
                "idx": idx,
                "file_off": file_off,
                "stamp_off": abs_off,
                "lba": lba,
                "expect": expect.hex(),
                "got": got.hex(),
                "ok": ok,
            }
        )

    report = {
        "version": st.get("version"),
        "serial": m.get("usbSerial"),
        "uid": args.uid,
        "lba0": lba0,
        "slot_bytes": slot_bytes,
        "markers_checked": len(results),
        "markers_ok": ok_n,
        "all_ok": ok_n == len(results) and len(results) > 0,
        "results": results,
    }
    print(json.dumps(report, indent=2))
    return 0 if report["all_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

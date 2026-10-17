#!/usr/bin/env python3
"""Controlled SCSI READ(10) via SG_IO — Lab truth path (bypasses page cache).

Run ON the USB host that owns /dev/sg0 (e.g. CT100), not via plain read()/dd
on /dev/sda (those can hit Linux page cache while the ESP sees 0 MSC bytes).

Examples:
  python3 tools/sgio_read10.py --lba 81 --blocks 16 --dump /tmp/head.bin
  python3 tools/sgio_read10.py --plan q10
  python3 tools/sgio_read10.py --plan q10 --json
"""
from __future__ import annotations

import argparse
import ctypes
import fcntl
import json
import os
import struct
import sys
import time

SG_IO = 0x2285
DXFER_FROM_DEV = -3

# Default Q10 calibration sizes (blocks). Requested host CBW vs ESP-observed.
Q10_PLAN: list[tuple[str, int, int]] = [
    ("r512", 300, 1),
    ("r4k", 0, 8),
    ("r16k", 100, 32),
    ("r64k", 200, 128),
    ("r120k", 400, 240),
]


class SgIoHdr(ctypes.Structure):
    _fields_ = [
        ("interface_id", ctypes.c_int),
        ("dxfer_direction", ctypes.c_int),
        ("cmd_len", ctypes.c_ubyte),
        ("mx_sb_len", ctypes.c_ubyte),
        ("iovec_count", ctypes.c_ushort),
        ("dxfer_len", ctypes.c_uint),
        ("dxferp", ctypes.c_void_p),
        ("cmdp", ctypes.c_void_p),
        ("sbp", ctypes.c_void_p),
        ("timeout", ctypes.c_uint),
        ("flags", ctypes.c_uint),
        ("pack_id", ctypes.c_int),
        ("usr_ptr", ctypes.c_void_p),
        ("status", ctypes.c_ubyte),
        ("masked_status", ctypes.c_ubyte),
        ("msg_status", ctypes.c_ubyte),
        ("sb_len_wr", ctypes.c_ubyte),
        ("host_status", ctypes.c_ushort),
        ("driver_status", ctypes.c_ushort),
        ("resid", ctypes.c_int),
        ("duration", ctypes.c_uint),
        ("info", ctypes.c_uint),
    ]


def read10(
    fd: int,
    lba: int,
    nblocks: int,
    *,
    timeout_ms: int = 8000,
) -> tuple[bytes, dict]:
    """Issue READ(10); return (data, meta)."""
    if nblocks < 1 or nblocks > 65535:
        raise ValueError(f"nblocks out of range: {nblocks}")
    n = nblocks * 512
    buf = (ctypes.c_ubyte * n)()
    cdb = struct.pack(">BBIBHB", 0x28, 0, lba & 0xFFFFFFFF, 0, nblocks & 0xFFFF, 0)
    cmd = (ctypes.c_ubyte * len(cdb)).from_buffer_copy(cdb)
    sb = (ctypes.c_ubyte * 32)()
    hdr = SgIoHdr(
        interface_id=ord("S"),
        dxfer_direction=DXFER_FROM_DEV,
        cmd_len=len(cdb),
        mx_sb_len=32,
        dxfer_len=n,
        dxferp=ctypes.addressof(buf),
        cmdp=ctypes.addressof(cmd),
        sbp=ctypes.addressof(sb),
        timeout=timeout_ms,
    )
    t0 = time.time()
    fcntl.ioctl(fd, SG_IO, hdr)
    wall_ms = round((time.time() - t0) * 1000.0, 2)
    got = n - int(hdr.resid)
    data = bytes(buf[: max(0, got)])
    meta = {
        "lba": lba,
        "blocks": nblocks,
        "bytes_req": n,
        "got": got,
        "status": int(hdr.status),
        "host": int(hdr.host_status),
        "drv": int(hdr.driver_status),
        "resid": int(hdr.resid),
        "dur_ms": int(hdr.duration),
        "wall_ms": wall_ms,
        "sense_hex": bytes(sb[: int(hdr.sb_len_wr)]).hex() if hdr.sb_len_wr else "",
    }
    return data, meta


def run_plan(
    sg: str,
    plan: list[tuple[str, int, int]],
    *,
    timeout_ms: int = 8000,
    gap_s: float = 0.08,
) -> list[dict]:
    fd = os.open(sg, os.O_RDWR)
    out: list[dict] = []
    try:
        for tag, lba, nb in plan:
            _data, meta = read10(fd, lba, nb, timeout_ms=timeout_ms)
            meta["tag"] = tag
            out.append(meta)
            time.sleep(gap_s)
    finally:
        os.close(fd)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sg", default="/dev/sg0")
    ap.add_argument("--lba", type=int, default=None)
    ap.add_argument("--blocks", type=int, default=None)
    ap.add_argument("--plan", choices=("q10",), default=None)
    ap.add_argument("--timeout-ms", type=int, default=8000)
    ap.add_argument("--dump", default="", help="write payload of single read to path")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.plan == "q10":
        rows = run_plan(args.sg, Q10_PLAN, timeout_ms=args.timeout_ms)
        print(json.dumps(rows, indent=2 if not args.json else None))
        return 0 if all(r.get("status") == 0 and r.get("got") == r.get("bytes_req") for r in rows) else 2

    if args.lba is None or args.blocks is None:
        ap.error("need --plan q10 or both --lba and --blocks")

    fd = os.open(args.sg, os.O_RDWR)
    try:
        data, meta = read10(fd, args.lba, args.blocks, timeout_ms=args.timeout_ms)
    finally:
        os.close(fd)

    if args.dump:
        Path = __import__("pathlib").Path
        Path(args.dump).write_bytes(data)
        meta["dump"] = args.dump
        meta["dump_len"] = len(data)
        meta["starts_id3"] = data.startswith(b"ID3")
        meta["first16"] = data[:16].hex()

    print(json.dumps(meta, indent=2))
    return 0 if meta["status"] == 0 and meta["got"] == meta["bytes_req"] else 2


if __name__ == "__main__":
    sys.exit(main())

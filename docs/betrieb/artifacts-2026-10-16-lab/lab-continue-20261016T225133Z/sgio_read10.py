#!/usr/bin/env python3
"""Controlled READ10 via SG_IO on /dev/sg0 (lab Q10 calib)."""
from __future__ import annotations

import ctypes
import fcntl
import json
import os
import struct
import time

SG_IO = 0x2285


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


def read10(fd: int, lba: int, nblocks: int) -> dict:
    n = nblocks * 512
    buf = (ctypes.c_ubyte * n)()
    cdb = struct.pack(">BBIBHB", 0x28, 0, lba & 0xFFFFFFFF, 0, nblocks & 0xFFFF, 0)
    cmd = (ctypes.c_ubyte * len(cdb)).from_buffer_copy(cdb)
    sb = (ctypes.c_ubyte * 32)()
    hdr = SgIoHdr(
        interface_id=ord("S"),
        dxfer_direction=-3,
        cmd_len=len(cdb),
        mx_sb_len=32,
        dxfer_len=n,
        dxferp=ctypes.addressof(buf),
        cmdp=ctypes.addressof(cmd),
        sbp=ctypes.addressof(sb),
        timeout=8000,
    )
    fcntl.ioctl(fd, SG_IO, hdr)
    return {
        "status": hdr.status,
        "host": hdr.host_status,
        "drv": hdr.driver_status,
        "resid": hdr.resid,
        "dur_ms": hdr.duration,
        "got": n - hdr.resid,
    }


def main() -> None:
    plan = [
        ("r512", 300, 1),
        ("r4k", 0, 8),
        ("r16k", 100, 32),
        ("r64k", 200, 128),
        ("r120k", 400, 240),
    ]
    fd = os.open("/dev/sg0", os.O_RDWR)
    out = []
    try:
        for tag, lba, nb in plan:
            t0 = time.time()
            row = read10(fd, lba, nb)
            row.update(tag=tag, lba=lba, blocks=nb, wall_ms=round((time.time() - t0) * 1000, 2))
            out.append(row)
            time.sleep(0.08)
    finally:
        os.close(fd)
    print(json.dumps(out))


if __name__ == "__main__":
    main()

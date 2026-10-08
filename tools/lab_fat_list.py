#!/usr/bin/env python3
"""List FAT12/16 short (+ basic LFN) names from a PiDrive MSC block device (read-only)."""
from __future__ import annotations

import argparse
import json
import os
import struct
import sys
from pathlib import Path


def read_dev(fd: int, lba: int, nsec: int, bps: int = 512) -> bytes:
    return os.pread(fd, nsec * bps, lba * bps)


def parse_bpb(boot: bytes) -> dict:
    return {
        "bps": struct.unpack_from("<H", boot, 11)[0],
        "spc": boot[13],
        "reserved": struct.unpack_from("<H", boot, 14)[0],
        "nfats": boot[16],
        "root_ents": struct.unpack_from("<H", boot, 17)[0],
        "fatsz16": struct.unpack_from("<H", boot, 22)[0],
        "totsec16": struct.unpack_from("<H", boot, 19)[0],
        "totsec32": struct.unpack_from("<I", boot, 32)[0],
    }


def decode_entries(blob: bytes) -> list[dict]:
    """Decode directory entries; assemble LFNs when present."""
    out: list[dict] = []
    lfn_parts: list[str] = []
    for i in range(0, len(blob), 32):
        ent = blob[i : i + 32]
        if len(ent) < 32 or ent[0] == 0x00:
            break
        if ent[0] == 0xE5:
            lfn_parts = []
            continue
        attr = ent[11]
        if attr == 0x0F:
            # LFN piece
            chars = []
            for off in (1, 3, 5, 7, 9, 14, 16, 18, 20, 22, 24, 28, 30):
                c = struct.unpack_from("<H", ent, off)[0]
                if c == 0x0000 or c == 0xFFFF:
                    break
                chars.append(chr(c))
            lfn_parts.append("".join(chars))
            continue
        name8 = ent[0:8].decode("ascii", "replace").rstrip(" ")
        ext = ent[8:11].decode("ascii", "replace").rstrip(" ")
        short = f"{name8}.{ext}" if ext else name8
        lfn = "".join(reversed(lfn_parts)) if lfn_parts else None
        lfn_parts = []
        cl = struct.unpack_from("<H", ent, 26)[0]
        size = struct.unpack_from("<I", ent, 28)[0]
        out.append(
            {
                "short": short,
                "lfn": lfn,
                "name": lfn or short,
                "attr": attr,
                "dir": bool(attr & 0x10),
                "cluster": cl,
                "size": size,
            }
        )
    return out


def cluster_to_lba(cl: int, *, root_lba: int, root_secs: int, spc: int, data_start: int) -> int:
    if cl < 2:
        return root_lba
    return data_start + (cl - 2) * spc


def list_dir(fd: int, bpb: dict, cluster: int = 0) -> list[dict]:
    bps = bpb["bps"]
    spc = bpb["spc"]
    root_lba = bpb["reserved"] + bpb["nfats"] * bpb["fatsz16"]
    root_secs = (bpb["root_ents"] * 32 + bps - 1) // bps
    data_start = root_lba + root_secs
    if cluster == 0:
        blob = read_dev(fd, root_lba, root_secs, bps)
    else:
        # read a few clusters (enough for station dirs)
        lba = cluster_to_lba(cluster, root_lba=root_lba, root_secs=root_secs, spc=spc, data_start=data_start)
        blob = read_dev(fd, lba, spc * 4, bps)
    return decode_entries(blob)


def main() -> int:
    ap = argparse.ArgumentParser(description="FAT list PiDrive MSC (ro)")
    ap.add_argument("--dev", default="/dev/sda")
    ap.add_argument("--path", default="/STATIONS", help="subdir under root, or '' for root")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    fd = os.open(args.dev, os.O_RDONLY)
    try:
        boot = read_dev(fd, 0, 1)
        bpb = parse_bpb(boot)
        root = list_dir(fd, bpb, 0)
        names = [e["name"] for e in root]
        result: dict = {"bpb": bpb, "root": root, "path": args.path or "/"}
        if args.path:
            target = None
            for e in root:
                if e["dir"] and e["name"].rstrip("/").upper() == args.path.upper().rstrip("/"):
                    target = e
                    break
                if e["dir"] and e["short"].rstrip(".").upper().startswith(args.path.upper()[:8]):
                    target = e
                    break
            if not target:
                result["error"] = f"dir {args.path!r} not found in {names}"
                print(json.dumps(result, indent=2)[:500])
                return 1
            entries = list_dir(fd, bpb, target["cluster"])
            result["entries"] = entries
            result["names"] = [e["name"] for e in entries if not e["name"].startswith(".")]
            print("NAMES", result["names"])
        else:
            result["names"] = names
            print("NAMES", names)
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(json.dumps(result, indent=2))
            print("OUT", args.out)
        return 0
    finally:
        os.close(fd)


if __name__ == "__main__":
    raise SystemExit(main())

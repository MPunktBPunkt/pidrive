#!/usr/bin/env python3
"""Classify MessCapture / mess.json READ10 LBAs into MSC bands (L3 Favoriten layout).

Use on field or lab artifacts:
  python3 tools/mess_band_report.py \\
    docs/betrieb/artifacts-2026-10-17-feld/feld-ota-053/nbt-flat-1212/mess.json
"""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path


def classify(lba: int) -> str:
    if lba < 33:
        return "boot_fat"
    if 33 <= lba <= 64:
        return "root_dir"
    if lba == 65:
        return "DIR_Favoriten"
    if 66 <= lba <= 72:
        return "DIR_Favoriten_pad"
    if lba == 73:
        return "DIR_Menue"
    if 74 <= lba <= 80:
        return "DIR_Menue_pad"
    if 81 <= lba <= 16464:
        return "file_fav0"
    if 16465 <= lba <= 17488:
        return "file_fav1"
    if 17489 <= lba <= 18512:
        return "file_fav2"
    if lba >= 18513:
        return "file_menue_stub"
    return "other"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mess_json")
    ap.add_argument("-o", help="optional SUMMARY.json out")
    args = ap.parse_args()
    raw = json.loads(Path(args.mess_json).read_text())
    cmds = raw.get("cmds") or raw.get("mess", {}).get("cmds") or []
    if isinstance(cmds, int):
        print("no cmds list", cmds)
        return 2
    read10 = [c for c in cmds if int(c.get("op") or 0) == 40]
    bands = collections.Counter(classify(int(c["lba"])) for c in read10 if c.get("lba") is not None)
    blocks = collections.Counter(int(c.get("blocks") or 0) for c in read10)
    summary = {
        "source": args.mess_json,
        "read10_n": len(read10),
        "bands": dict(bands),
        "blocks_hist": dict(sorted(blocks.items())),
        "dir_favoriten": bands.get("DIR_Favoriten", 0) > 0,
        "dir_menue": bands.get("DIR_Menue", 0) > 0,
        "root_dir": bands.get("root_dir", 0) > 0,
    }
    print(json.dumps(summary, indent=2))
    if args.o:
        Path(args.o).write_text(json.dumps(summary, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

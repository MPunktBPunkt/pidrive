#!/usr/bin/env python3
"""Classify MessCapture / mess.json READ10 LBAs into MSC bands (L3 Favoriten layout).

M32: LBA → Virtual-FAT band (not lbatofile / EXT). Accepts dump shapes:
  - { "cmds": [...] }
  - { "commands": [...] }          # mess_hu_capture arm -o
  - { "mess": { "cmds": [...] } }
  - { "raw": { "cmds": [...] } }

Use on field or lab artifacts:
  python3 tools/mess_band_report.py \\
    docs/betrieb/artifacts-2026-10-17-feld/feld-ota-053/nbt-flat-1212/mess.json
  python3 tools/mess_band_report.py arm.json -o band.json
"""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path
from typing import Any


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


def extract_cmds(raw: dict) -> list[dict]:
    if isinstance(raw.get("commands"), list):
        return raw["commands"]
    if isinstance(raw.get("cmds"), list):
        return raw["cmds"]
    mess = raw.get("mess")
    if isinstance(mess, dict) and isinstance(mess.get("cmds"), list):
        return mess["cmds"]
    nested = raw.get("raw")
    if isinstance(nested, dict):
        return extract_cmds(nested)
    return []


def report(cmds: list[dict], source: str) -> dict[str, Any]:
    read10 = [c for c in cmds if int(c.get("op") or 0) == 0x28]
    bands = collections.Counter(
        classify(int(c["lba"])) for c in read10 if c.get("lba") is not None
    )
    blocks = collections.Counter(int(c.get("blocks") or 0) for c in read10)
    file_body = sum(v for k, v in bands.items() if k.startswith("file_"))
    meta = sum(
        v
        for k, v in bands.items()
        if k.startswith("DIR_") or k in ("boot_fat", "root_dir")
    )
    # rough head vs body within fav bands: first 2×4KiB-ish of each file ≈ head;
    # MessCapture doesn't always carry offset — use LBA distance from band start.
    headish = midish = 0
    fav_starts = {"file_fav0": 81, "file_fav1": 16465, "file_fav2": 17489}
    for c in read10:
        if c.get("lba") is None:
            continue
        lba = int(c["lba"])
        band = classify(lba)
        start = fav_starts.get(band)
        if start is None:
            continue
        off_blocks = lba - start
        if off_blocks < 16:  # ~8 KiB @ 512
            headish += 1
        else:
            midish += 1

    dominant = bands.most_common(1)[0][0] if bands else None
    return {
        "source": source,
        "read10_n": len(read10),
        "cmds_n": len(cmds),
        "bands": dict(bands),
        "blocks_hist": dict(sorted(blocks.items())),
        "file_body_n": file_body,
        "meta_n": meta,
        "file_body_share": round(file_body / len(read10), 3) if read10 else None,
        "fav_headish_n": headish,
        "fav_midish_n": midish,
        "dominant_band": dominant,
        "storm_hint": bool(
            read10
            and file_body >= 2
            and (file_body / len(read10)) >= 0.7
        ),
        "dir_favoriten": bands.get("DIR_Favoriten", 0) > 0,
        "dir_menue": bands.get("DIR_Menue", 0) > 0,
        "root_dir": bands.get("root_dir", 0) > 0,
        "epistemic": (
            "bands=Virtual-FAT L3 Favoriten layout (PiDrive); "
            "storm_hint=file_body dominant — correlate with qs label S, not alone."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("mess_json", nargs="?", help="mess/arm dump JSON")
    ap.add_argument("-o", help="optional SUMMARY.json out")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        cmds = [
            {"op": 40, "lba": 0, "blocks": 1},
            {"op": 40, "lba": 65, "blocks": 1},
            {"op": 40, "lba": 100, "blocks": 240},
            {"op": 40, "lba": 200, "blocks": 240},
            {"op": 40, "lba": 300, "blocks": 240},
            {"op": 40, "lba": 400, "blocks": 240},
            {"op": 40, "lba": 500, "blocks": 240},
            {"op": 40, "lba": 600, "blocks": 240},
        ]
        s = report(cmds, "self-test")
        assert s["bands"]["boot_fat"] == 1
        assert s["bands"]["DIR_Favoriten"] == 1
        assert s["bands"]["file_fav0"] == 6
        assert s["storm_hint"] is True
        # arm.json shape
        wrapped = extract_cmds({"commands": cmds})
        assert len(wrapped) == 8
        print("self-test OK", s["bands"], "storm_hint", s["storm_hint"])
        return 0

    if not args.mess_json:
        ap.error("mess_json required (or --self-test)")
    raw = json.loads(Path(args.mess_json).read_text(encoding="utf-8"))
    cmds = extract_cmds(raw)
    if not cmds:
        print(json.dumps({"error": "no_cmds", "source": args.mess_json}, indent=2))
        return 2
    summary = report(cmds, args.mess_json)
    print(json.dumps(summary, indent=2))
    if args.o:
        Path(args.o).write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

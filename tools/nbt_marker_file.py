#!/usr/bin/env python3
"""Build marker-pattern payload for Q4/cursor diagnosis (no Stall FW).

Writes a binary file tiled with recognizable 4 KiB blocks:
  bytes 0..3   = ASCII tag 'MkA0'.. per 50 KiB section
  rest         = 0x55 pad (silence-like) or optional KSIL sync every 156 B

Lab use: inspect with hexdump / feed into future geometry. Field use: after
custom MSC image support. Does NOT flash or change ESP geometry.

Example:
  python3 tools/nbt_marker_file.py --size-kib 512 --section-kib 50 --out /tmp/marker512.bin
"""
from __future__ import annotations

import argparse
from pathlib import Path

# Minimal MPEG-1 L3 silence sync (same family as nbt_hu_sim KSIL head)
KSIL_HEAD = bytes([0xFF, 0xFB, 0x30, 0x64])


def build(size: int, section: int, use_ksil: bool) -> bytes:
    out = bytearray(size)
    nsec = max(1, (size + section - 1) // section)
    for i in range(nsec):
        off = i * section
        tag = f"Mk{i:02d}".encode("ascii")[:4].ljust(4, b"0")
        end = min(size, off + section)
        chunk = end - off
        block = bytearray(b"\x55") * chunk
        block[0:4] = tag
        if use_ksil:
            for o in range(4, chunk - 4, 156):
                block[o : o + 4] = KSIL_HEAD
        out[off:end] = block
    # ID3-ish prefix optional
    if size >= 64:
        out[0:3] = b"ID3"
    return bytes(out)


def main() -> int:
    ap = argparse.ArgumentParser(description="Marker pattern file generator")
    ap.add_argument("--size-kib", type=int, default=512)
    ap.add_argument("--section-kib", type=int, default=50)
    ap.add_argument("--ksil-tiles", action="store_true")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    size = args.size_kib * 1024
    section = args.section_kib * 1024
    blob = build(size, section, args.ksil_tiles)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(blob)
    # index
    idx = []
    for i, off in enumerate(range(0, size, section)):
        idx.append({"section": i, "off": off, "tag": blob[off : off + 4].decode("ascii", "replace")})
    Path(str(out) + ".index.json").write_text(
        __import__("json").dumps({"size": size, "section": section, "sections": idx}, indent=2)
    )
    print(f"Wrote {out} ({size} B) + index ({len(idx)} sections)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

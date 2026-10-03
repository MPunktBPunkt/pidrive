#!/usr/bin/env python3
"""Generate static CBR MP3 with periodic audible markers (M3 L-Leiter assets).

Markers every --marker-s seconds: short beep; silence between.
Writes MP3 + offset map JSON (time → approx byte offset @ CBR).

Example:
  python3 tools/m3_make_marked_mp3.py --size-kib 512 --out docs/betrieb/artifacts-2026-10-03-m3/mp3/L1
"""
from __future__ import annotations

import argparse
import json
import subprocess
import wave
from pathlib import Path


def write_wav(path: Path, seconds: float, marker_s: float, sr: int = 44100) -> list[dict]:
    """PCM silence with 440 Hz beeps; return marker table (t_s, sample)."""
    import math
    import struct

    n = int(seconds * sr)
    markers = []
    # 200 ms beep
    beep_n = int(0.2 * sr)
    amp = 0.35
    frames = bytearray()
    i = 0
    next_mark = 0.0
    while i < n:
        t = i / sr
        if next_mark <= seconds and t + 1e-9 >= next_mark:
            markers.append({"t_s": round(next_mark, 3), "sample": i})
            for k in range(beep_n):
                if i + k >= n:
                    break
                s = amp * math.sin(2 * math.pi * 440.0 * (k / sr))
                frames.extend(struct.pack("<h", int(max(-1, min(1, s)) * 32767)))
            i += beep_n
            next_mark += marker_s
            continue
        frames.extend(b"\x00\x00")
        i += 1
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(bytes(frames))
    return markers


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--size-kib", type=int, required=True, help="target MP3 size KiB")
    ap.add_argument("--bitrate", default="48k")
    ap.add_argument("--marker-s", type=float, default=30.0)
    ap.add_argument("--out", type=Path, required=True, help="output prefix (no extension)")
    args = ap.parse_args()

    # CBR bytes/s ≈ bitrate/8
    br = int(str(args.bitrate).rstrip("kK")) * 1000
    bytes_per_s = br / 8.0
    target = args.size_kib * 1024
    seconds = max(args.marker_s * 2, target / bytes_per_s + 2.0)

    wav = args.out.with_suffix(".wav")
    mp3 = args.out.with_suffix(".mp3")
    meta = args.out.with_suffix(".markers.json")
    markers = write_wav(wav, seconds, args.marker_s)

    subprocess.check_call(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(wav),
            "-c:a",
            "libmp3lame",
            "-b:a",
            args.bitrate,
            "-write_xing",
            "1",
            str(mp3),
        ]
    )
    size = mp3.stat().st_size
    # trim/pad note: we keep ffmpeg output; map markers by CBR estimate
    mapped = []
    for m in markers:
        off = int(m["t_s"] * bytes_per_s)
        if off < size:
            mapped.append({**m, "approx_file_off": off})

    doc = {
        "mp3": str(mp3),
        "size_bytes": size,
        "size_kib_target": args.size_kib,
        "bitrate": args.bitrate,
        "marker_s": args.marker_s,
        "bytes_per_s_est": bytes_per_s,
        "markers": mapped,
        "note": "approx_file_off assumes CBR; verify with decoder if used for A–E cursor correlation",
    }
    meta.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    wav.unlink(missing_ok=True)
    print(json.dumps({"mp3": str(mp3), "size": size, "markers": len(mapped)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

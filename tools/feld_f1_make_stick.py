#!/usr/bin/env python3
"""F1 USB-Stick: MP3s mit Positionsmarkern alle 10 s (Feldprotokoll Teil E).

Format wie Bridge: MPEG-1/2 Layer III, 22,05 kHz, mono, 48 kbit/s CBR.

Bevorzugt espeak-ng (gesprochene Zahl). Fallback: ffmpeg-Beeps (Anzahl = Dekade),
damit t_voice trotzdem messbar ist ohne Sprachsynthese auf dem Build-Host.

  python3 tools/feld_f1_make_stick.py --out-dir /tmp/f1-stick --sizes 5mb,100mb
  python3 tools/feld_f1_make_stick.py --out-dir /tmp/f1-stick --sizes 30s   # Kurztest

Auf dem Pi (mit espeak-ng) denselben Befehl nochmal laufen lassen für gesprochene Marker.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

AR = 22050
BR = "48k"
MARKER_S = 10.0


def have(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def run(cmd: list[str], **kw: object) -> None:
    subprocess.run(cmd, check=True, **kw)


def speak_wav(text: str, wav: Path, voice: str = "de") -> str:
    """Return engine used: espeak-ng | espeak | beep."""
    if have("espeak-ng"):
        run(["espeak-ng", "-v", voice, "-w", str(wav), text], capture_output=True)
        return "espeak-ng"
    if have("espeak"):
        run(["espeak", "-v", voice, "-w", str(wav), text], capture_output=True)
        return "espeak"
    # fallback: N short beeps (N = decade+1), then pad to MARKER_S
    try:
        n = max(1, min(20, int("".join(c for c in text if c.isdigit()) or "0") // 10 + 1))
    except ValueError:
        n = 1
    # freq encodes decade: 440 + 20*n Hz, n beeps of 80 ms
    freq = 440 + 20 * n
    beep_chain = "".join(f"sine=f={freq}:d=0.08,anullsrc=r={AR}:cl=mono:d=0.08," for _ in range(n))
    # lavfi concat via asplit is awkward; generate duration then pad
    dur = min(MARKER_S - 0.2, n * 0.16)
    run(
        [
            "ffmpeg",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency={freq}:sample_rate={AR}:duration={dur}",
            "-af",
            f"apad=whole_dur={MARKER_S}",
            "-ac",
            "1",
            str(wav),
        ]
    )
    return "beep"


def make_block(sec: int, out_wav: Path, work: Path, voice: str) -> str:
    """One MARKER_S block announcing `sec` (spoken or beeps), padded to MARKER_S."""
    raw = work / f"say_{sec}.wav"
    engine = speak_wav(str(sec), raw, voice=voice)
    if engine.startswith("espeak"):
        run(
            [
                "ffmpeg",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(raw),
                "-af",
                f"apad=whole_dur={MARKER_S}",
                "-ar",
                str(AR),
                "-ac",
                "1",
                str(out_wav),
            ]
        )
    else:
        # already padded in speak_wav beep path
        if raw.resolve() != out_wav.resolve():
            shutil.copy(raw, out_wav)
    return engine


def encode_mp3(wav_list: Path, mp3: Path, title: str) -> None:
    run(
        [
            "ffmpeg",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(wav_list),
            "-c:a",
            "libmp3lame",
            "-b:a",
            BR,
            "-ar",
            str(AR),
            "-ac",
            "1",
            "-write_xing",
            "0",
            "-metadata",
            f"title={title}",
            str(mp3),
        ]
    )


def size_to_blocks(spec: str) -> tuple[str, int]:
    """Return (label, n_blocks of 10 s)."""
    s = spec.strip().lower()
    if s.endswith("s") and s[:-1].isdigit():
        sec = int(s[:-1])
        return (f"{sec}s", max(1, round(sec / MARKER_S)))
    if s in ("5mb", "5mib", "5"):
        # ~5 MiB @ 48k ≈ 5*1024*1024*8/48000 ≈ 873 s → 88 blocks
        return ("5MB", 88)
    if s in ("100mb", "100mib", "100"):
        # ~100 MiB ≈ 17476 s → 1748 blocks (~4.8 h) — long; use 1748
        return ("100MB", 1748)
    if s in ("1gb", "1gib"):
        return ("1GB", 17480)
    raise SystemExit(f"unknown size spec: {spec}")


def build_one(out_dir: Path, spec: str, voice: str, dry_blocks: int | None) -> dict:
    label, n = size_to_blocks(spec)
    if dry_blocks is not None:
        n = dry_blocks
        label = f"{label}_dry{n}"
    work = Path(tempfile.mkdtemp(prefix=f"f1_{label}_"))
    engines: set[str] = set()
    try:
        files: list[Path] = []
        for i in range(n):
            sec = int(i * MARKER_S)
            wav = work / f"blk_{sec:05d}.wav"
            engines.add(make_block(sec, wav, work, voice))
            files.append(wav)
        lst = work / "list.txt"
        lst.write_text("".join(f"file '{p.name}'\n" for p in files), encoding="utf-8")
        mp3 = out_dir / f"F1-{label}.mp3"
        encode_mp3(lst, mp3, title=f"F1-{label}")
        meta = {
            "file": str(mp3),
            "label": label,
            "blocks": n,
            "duration_s": n * MARKER_S,
            "marker_s": MARKER_S,
            "ar": AR,
            "bitrate": BR,
            "engine": sorted(engines),
            "bytes": mp3.stat().st_size,
        }
        return meta
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--sizes", default="5mb", help="Komma: 30s,5mb,100mb,1gb")
    ap.add_argument("--voice", default="de")
    ap.add_argument(
        "--dry-blocks",
        type=int,
        default=None,
        help="nur N Blöcke (10 s) — schneller Smoke-Test",
    )
    args = ap.parse_args()
    if not have("ffmpeg"):
        print("ffmpeg fehlt", file=sys.stderr)
        return 2
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    report = []
    for spec in args.sizes.split(","):
        spec = spec.strip()
        if not spec:
            continue
        print(f"building {spec} …")
        meta = build_one(out, spec, args.voice, args.dry_blocks)
        report.append(meta)
        print(f"  → {meta['file']} ({meta['bytes']} B, {meta['duration_s']} s, engine={meta['engine']})")
    (out / "F1-INDEX.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    readme = out / "F1-STICK.md"
    eng = report[0]["engine"] if report else []
    readme.write_text(
        "\n".join(
            [
                "# F1 Stick",
                "",
                f"Engine: {eng}",
                "Marker alle 10 s (0, 10, 20, …).",
                "Messung: Video+Ton; `t_voice` = Antippen → erster Marker hörbar; welcher Marker?",
                "Hub USB-1.1 zwischen HU und Stick erzwingt Full-Speed (~1 MB/s).",
                "",
                "Dateien:",
                *[f"- `{Path(m['file']).name}` ({m['duration_s']} s, {m['bytes']} B)" for m in report],
                "",
            ]
        ),
        encoding="utf-8",
    )
    if "beep" in eng and not have("espeak-ng"):
        print(
            "Hinweis: kein espeak-ng — Beep-Fallback. Auf dem Pi mit espeak-ng neu bauen für Sprache.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

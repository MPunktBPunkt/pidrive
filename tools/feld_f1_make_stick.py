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


def encode_mp3(wav_list: Path, mp3: Path, title: str, br: str = BR) -> None:
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
            br,
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


def br_bps(br: str) -> int:
    s = br.strip().lower()
    return int(float(s[:-1]) * 1000) if s.endswith("k") else int(s)


def size_to_blocks(spec: str, br: str = BR) -> tuple[str, int]:
    """Return (label, n_blocks of 10 s); file size / bitrate decides the duration."""
    s = spec.strip().lower()
    if s.endswith("s") and s[:-1].isdigit():
        sec = int(s[:-1])
        return (f"{sec}s", max(1, round(sec / MARKER_S)))
    mib = {"5mb": 5, "5mib": 5, "5": 5, "100mb": 100, "100mib": 100, "100": 100, "1gb": 1000, "1gib": 1000}.get(s)
    if mib is None:
        raise SystemExit(f"unknown size spec: {spec}")
    # 48k: 5 MiB ≈ 874 s (87 blocks), 100 MiB ≈ 4,8 h (1748); 128k: 33 / 655 blocks
    sec = mib * 1024 * 1024 * 8 / br_bps(br)
    label = "1GB" if mib == 1000 else f"{mib}MB"
    return (label, max(1, round(sec / MARKER_S)))


def wav_bytes_needed(n_blocks: int) -> int:
    """Temp WAVs of one file: 16-bit mono at AR, plus one spoken raw per block (~same size)."""
    return int(n_blocks * MARKER_S * AR * 2 * 1.2)


def build_one(out_dir: Path, spec: str, voice: str, dry_blocks: int | None, br: str = BR,
              tmp_dir: str | None = None) -> dict:
    label, n = size_to_blocks(spec, br)
    if dry_blocks is not None:
        n = dry_blocks
        label = f"{label}_dry{n}"
    if br != BR:
        label = f"{label}_{br}"
    tmp_root = tmp_dir or tempfile.gettempdir()
    need = wav_bytes_needed(n)
    free = shutil.disk_usage(tmp_root).free
    if free < need:
        raise SystemExit(
            f"zu wenig Temp-Platz in {tmp_root}: frei {free / 1e6:.0f} MB, nötig ~{need / 1e6:.0f} MB "
            f"({n} Blöcke). --tmp-dir auf den Stick/SSD setzen oder --br 128k nehmen."
        )
    work = Path(tempfile.mkdtemp(prefix=f"f1_{label}_", dir=tmp_root))
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
        encode_mp3(lst, mp3, title=f"F1-{label}", br=br)
        meta = {
            "file": str(mp3),
            "label": label,
            "blocks": n,
            "duration_s": n * MARKER_S,
            "marker_s": MARKER_S,
            "ar": AR,
            "bitrate": br,
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
    ap.add_argument("--br", default=BR, help="MP3-Bitrate, z. B. 48k (Bridge-Format) oder 128k (100MB in 1,8 h statt 4,8 h)")
    ap.add_argument("--tmp-dir", default=None, help="Ordner für Temp-WAVs (Standard: System-Temp)")
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
        meta = build_one(out, spec, args.voice, args.dry_blocks, br=args.br, tmp_dir=args.tmp_dir)
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

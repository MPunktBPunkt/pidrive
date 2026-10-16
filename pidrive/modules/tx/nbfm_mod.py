#!/usr/bin/env python3
"""nbfm_mod.py — Schmalband-FM-Modulator: s16le mono (stdin) → IQ int16 (stdout).

Für rpitx `sendiq -t i16`. Hub Standard 2,5 kHz (PMR446, 12,5-kHz-Raster).
Mit numpy vektorisiert, sonst reines Python (Pi 4: ~48 kS/s machbar).
"""
from __future__ import annotations

import argparse
import math
import struct
import sys

try:
    import numpy as _np
except Exception:  # pragma: no cover - optional
    _np = None

CHUNK = 2400
AMP = 0.9 * 32767


def modulate_py(samples, phase: float, k: float):
    """samples: Folge von int16 → (iq_bytes, phase)."""
    out = bytearray()
    pack = struct.pack
    for s in samples:
        phase += k * (s / 32768.0)
        if phase > math.pi:
            phase -= 2 * math.pi
        elif phase < -math.pi:
            phase += 2 * math.pi
        out += pack("<hh", int(AMP * math.cos(phase)), int(AMP * math.sin(phase)))
    return bytes(out), phase


def modulate_np(buf: bytes, phase: float, k: float):
    x = _np.frombuffer(buf, dtype="<i2").astype(_np.float64) / 32768.0
    ph = phase + _np.cumsum(k * x)
    iq = _np.empty(2 * len(x), dtype="<i2")
    iq[0::2] = (AMP * _np.cos(ph)).astype("<i2")
    iq[1::2] = (AMP * _np.sin(ph)).astype("<i2")
    return iq.tobytes(), float(math.remainder(ph[-1], 2 * math.pi)) if len(x) else phase


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rate", type=int, default=48000)
    ap.add_argument("--dev", type=float, default=2500.0, help="Hub Hz")
    a = ap.parse_args(argv)
    k = 2 * math.pi * a.dev / a.rate
    phase = 0.0
    rd = sys.stdin.buffer
    wr = sys.stdout.buffer
    while True:
        buf = rd.read(CHUNK * 2)
        if not buf:
            break
        if len(buf) % 2:
            buf = buf[:-1]
        if _np is not None:
            iq, phase = modulate_np(buf, phase, k)
        else:
            n = len(buf) // 2
            iq, phase = modulate_py(struct.unpack(f"<{n}h", buf), phase, k)
        try:
            wr.write(iq)
            wr.flush()
        except BrokenPipeError:
            break
    return 0


if __name__ == "__main__":
    sys.exit(main())

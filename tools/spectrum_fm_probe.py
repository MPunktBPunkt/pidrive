#!/usr/bin/env python3
"""Probe UKW carriers via local WebUI API."""
import json
import time
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:8080"
TARGETS = [95.8, 103.0, 104.4]


def get(path, timeout=60):
    with urllib.request.urlopen(BASE + path, timeout=timeout) as r:
        return json.loads(r.read().decode())


def capture(**kw):
    q = urllib.parse.urlencode(kw)
    req = urllib.request.Request(BASE + "/api/spectrum/capture?" + q, method="POST")
    with urllib.request.urlopen(req, timeout=240) as r:
        return json.loads(r.read().decode())


def nearest(peaks, f, tol=0.15):
    best = None
    for p in peaks or []:
        df = abs(float(p.get("freq_mhz", 0)) - f)
        if df <= tol and (best is None or df < best[0]):
            best = (df, p)
    return best


def main():
    try:
        rt = get("/api/runtime")
        ppm = (rt.get("settings") or {}).get("ppm_correction", 49)
    except Exception as e:
        ppm = 49
        print("runtime err", e)
    print("ppm_setting", ppm)

    print("\n=== RANGE 95.5–105.0 MHz avg=4 samples=65536 ===")
    for g in [-1, 20, 40]:
        t0 = time.time()
        j = capture(
            mode="range",
            start_mhz=95.5,
            stop_mhz=105.0,
            ppm=ppm,
            gain=g,
            sample_count=65536,
            avg_frames=4,
        )
        dt = time.time() - t0
        peaks = j.get("peaks") or []
        print(
            f"\ngain={g} ok={j.get('ok')} dt={dt:.1f}s sr={j.get('sample_rate_hz')} "
            f"avg={j.get('avg_frames')} rbw={j.get('rbw_hz')} "
            f"windows={j.get('windows_ok')}/{j.get('windows_total')} "
            f"npeaks={len(peaks)} err={j.get('error')}"
        )
        for f in TARGETS:
            hit = nearest(peaks, f, 0.2)
            if hit:
                p = hit[1]
                print(
                    f"  {f}: FOUND {p.get('freq_mhz')} MHz  {p.get('db')} dB  "
                    f"df={hit[0]*1e3:.1f} kHz  interp={p.get('interpolated')}"
                )
            elif peaks:
                closest = min(peaks, key=lambda p: abs(float(p.get("freq_mhz", 0)) - f))
                print(
                    f"  {f}: MISS  closest={closest.get('freq_mhz')} "
                    f"({closest.get('db')} dB)"
                )
            else:
                print(f"  {f}: MISS  (no peaks)")
        top = sorted(peaks, key=lambda p: -float(p.get("db", -999)))[:8]
        print("  top:", [(round(p.get("freq_mhz", 0), 3), p.get("db")) for p in top])

    print("\n=== SNAPSHOTS center=target, avg=8, SR=1.024M ===")
    for f in TARGETS:
        for g in [-1, 40]:
            t0 = time.time()
            j = capture(
                mode="snapshot",
                center_mhz=f,
                ppm=ppm,
                gain=g,
                sample_count=65536,
                avg_frames=8,
                sample_rate_hz=1024000,
            )
            dt = time.time() - t0
            peaks = j.get("peaks") or []
            hit = nearest(peaks, f, 0.1)
            print(
                f"center={f} gain={g} ok={j.get('ok')} dt={dt:.1f}s "
                f"rbw={j.get('rbw_hz')} peaks={len(peaks)} err={j.get('error')}"
            )
            if hit:
                p = hit[1]
                print(
                    f"  -> {p.get('freq_mhz')} MHz {p.get('db')} dB "
                    f"df={hit[0]*1e6:.0f} Hz interp={p.get('interpolated')} "
                    f"delta_bin={p.get('delta_bin')}"
                )
            else:
                top = sorted(peaks, key=lambda p: -float(p.get("db", -999)))[:5]
                print(
                    "  miss top:",
                    [(round(p.get("freq_mhz", 0), 4), p.get("db")) for p in top],
                )

    print("\nDONE")


if __name__ == "__main__":
    main()

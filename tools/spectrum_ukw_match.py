#!/usr/bin/env python3
"""Schneller Abgleich bekannter UKW-Sender (Zooms) + optional Band."""
import json
import math
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:8080"
KNOWN = [
    (90.2, "RT1"),
    (90.7, "Bayern 1"),
    (95.8, "ref/früher"),
    (98.5, "Bayern 3"),
    (103.0, "SWR3"),
    (104.4, "Antenne Bayern"),
]


def capture(**kw):
    q = urllib.parse.urlencode(kw)
    req = urllib.request.Request(BASE + "/api/spectrum/capture?" + q, method="POST")
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode())


def energy_near(spec, start, bin_hz, f_c, half_khz=75):
    if not spec or not bin_hz:
        return None
    lo, hi = f_c - half_khz / 1000.0, f_c + half_khz / 1000.0
    acc = 0.0
    n = 0
    peak = -1e9
    peak_f = None
    for i, db in enumerate(spec):
        f = start + i * bin_hz / 1e6
        if lo <= f <= hi:
            acc += 10 ** (db / 10.0)
            n += 1
            if db > peak:
                peak, peak_f = db, f
    if not n:
        return None
    return {
        "peak_db": round(peak, 2),
        "peak_f": round(peak_f, 4),
        "mean_db": round(10 * math.log10(acc / n), 2),
    }


def main():
    print("=== Zooms ±0.35 MHz  gain=25  avg=4  SR=1.024M ===", flush=True)
    results = []
    for f, name in KNOWN:
        j = capture(
            mode="range",
            start_mhz=round(f - 0.35, 3),
            stop_mhz=round(f + 0.35, 3),
            ppm=49,
            gain=25,
            sample_count=65536,
            avg_frames=4,
            sample_rate_hz=1024000,
        )
        if not j.get("ok"):
            print(f"{f} {name}: FAIL {j.get('error')}", flush=True)
            results.append({"f": f, "name": name, "ok": False})
            continue
        peaks = sorted(j.get("peaks") or [], key=lambda p: -float(p["db"]))
        start = float(j.get("f0_mhz") or j.get("start_mhz"))
        bin_hz = float(j.get("bin_hz") or 0)
        e = energy_near(j.get("spectrum_db") or [], start, bin_hz, f, 75)
        # FM-Komplex: Peaks innerhalb ±100 kHz vom Soll
        core = [p for p in peaks if abs(p["freq_mhz"] - f) <= 0.1]
        # Nebenpeaks 100–200 kHz (Stereo/RDS-Flanken, Nachbarkanal)
        side = [p for p in peaks if 0.1 < abs(p["freq_mhz"] - f) <= 0.2]
        best = core[0] if core else (peaks[0] if peaks else None)
        df_hz = round((best["freq_mhz"] - f) * 1e6) if best else None
        row = {
            "f": f,
            "name": name,
            "ok": True,
            "energy": e,
            "n_peaks": len(peaks),
            "n_core": len(core),
            "n_side": len(side),
            "best_core": None
            if not core
            else {
                "freq": round(core[0]["freq_mhz"], 4),
                "db": core[0]["db"],
                "df_Hz": round((core[0]["freq_mhz"] - f) * 1e6),
            },
            "top": [(round(p["freq_mhz"], 4), p["db"]) for p in peaks[:6]],
        }
        results.append(row)
        print(
            f"{f} {name}: energy_peak={e and e['peak_db']}dB@{e and e['peak_f']} "
            f"core={row['n_core']} side={row['n_side']} best={row['best_core']} "
            f"top={row['top']}",
            flush=True,
        )

    # Schnelles Band avg=1 für Energie-Raster an Rasterfrequenzen
    print("\n=== Band schnell gain=25 avg=1 (Kanalenergie) ===", flush=True)
    j = capture(
        mode="range",
        start_mhz=87.5,
        stop_mhz=108.0,
        ppm=49,
        gain=25,
        sample_count=32768,
        avg_frames=1,
    )
    print(
        "band ok", j.get("ok"),
        "win", j.get("windows_ok"), "/", j.get("windows_total"),
        "err", j.get("error"),
        flush=True,
    )
    if j.get("ok"):
        spec = j.get("spectrum_db") or []
        start = float(j.get("f0_mhz") or 87.5)
        bin_hz = float(j.get("bin_hz") or 0)
        # 100 kHz Raster
        scores = []
        f = 87.5
        while f <= 108.001:
            e = energy_near(spec, start, bin_hz, round(f, 1), 50)
            if e:
                scores.append((round(f, 1), e["peak_db"], e["mean_db"]))
            f = round(f + 0.1, 1)
        scores.sort(key=lambda x: -x[1])
        print("top25 channel-grid:", scores[:25], flush=True)
        print("\nKNOWN on grid:", flush=True)
        for f, name in KNOWN:
            e = energy_near(spec, start, bin_hz, f, 75)
            print(f"  {f} {name}: {e}", flush=True)

    print("DONE", flush=True)
    with open("/tmp/ukw_match_results.json", "w") as f:
        json.dump(results, f, indent=2)


if __name__ == "__main__":
    main()

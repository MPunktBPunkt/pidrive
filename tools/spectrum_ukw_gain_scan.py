#!/usr/bin/env python3
"""UKW 87.5–108 MHz: Gain-Vergleich + Peak-Analyse."""
import json
import time
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:8080"
# Bekannte Allgäu-Referenzen aus früherer Session
KNOWN = [95.8, 103.0, 104.4]


def capture(**kw):
    q = urllib.parse.urlencode(kw)
    req = urllib.request.Request(BASE + "/api/spectrum/capture?" + q, method="POST")
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read().decode())


def nearest(peaks, f, tol=0.1):
    best = None
    for p in peaks or []:
        df = abs(float(p.get("freq_mhz", 0)) - f)
        if df <= tol and (best is None or df < best[0]):
            best = (df, p)
    return best


def analyze(peaks, noise_floor_est=None):
    peaks = sorted(peaks or [], key=lambda p: -float(p.get("db", -999)))
    if not peaks:
        return {}
    dbs = [float(p["db"]) for p in peaks]
    # Heuristik: starke Peaks vs. Schwarm
    top = dbs[0]
    # "klare" Sender: innerhalb 12 dB vom stärksten
    strong = [p for p in peaks if top - float(p["db"]) <= 12]
    mid = [p for p in peaks if 12 < top - float(p["db"]) <= 25]
    weak = [p for p in peaks if top - float(p["db"]) > 25]
    return {
        "n": len(peaks),
        "top_db": round(top, 2),
        "strong_n": len(strong),
        "mid_n": len(mid),
        "weak_n": len(weak),
        "strong": [(round(p["freq_mhz"], 3), p["db"]) for p in strong[:15]],
        "top10": [(round(p["freq_mhz"], 3), p["db"]) for p in peaks[:10]],
    }


def main():
    ppm = 49
    try:
        with urllib.request.urlopen(BASE + "/api/runtime", timeout=10) as r:
            rt = json.loads(r.read().decode())
            ppm = (rt.get("settings") or {}).get("ppm_correction", 49) or 49
    except Exception as e:
        print("runtime", e)
    print("ppm", ppm, flush=True)

    gains = [-1, 20, 30, 40, 48]
    results = {}

    print("\n=== RANGE 87.5–108.0  SR=auto  samples=65k  avg=4 ===", flush=True)
    for g in gains:
        t0 = time.time()
        j = capture(
            mode="range",
            start_mhz=87.5,
            stop_mhz=108.0,
            ppm=ppm,
            gain=g,
            sample_count=65536,
            avg_frames=4,
        )
        dt = time.time() - t0
        peaks = j.get("peaks") or []
        a = analyze(peaks)
        a.update(
            {
                "ok": j.get("ok"),
                "dt": round(dt, 1),
                "sr": j.get("sample_rate_hz"),
                "rbw": j.get("rbw_hz"),
                "avg": j.get("avg_frames"),
                "windows": f"{j.get('windows_ok')}/{j.get('windows_total')}",
                "err": j.get("error"),
            }
        )
        known_hits = {}
        for f in KNOWN:
            hit = nearest(peaks, f, 0.08)
            if hit:
                known_hits[f] = {
                    "freq": hit[1].get("freq_mhz"),
                    "db": hit[1].get("db"),
                    "df_hz": round(hit[0] * 1e6),
                }
            else:
                known_hits[f] = None
        a["known"] = known_hits
        results[g] = a
        print(f"\ngain={g} ok={a['ok']} dt={a['dt']}s win={a['windows']} npeaks={a['n']} "
              f"strong={a.get('strong_n')} mid={a.get('mid_n')} weak={a.get('weak_n')} "
              f"top_db={a.get('top_db')}", flush=True)
        print("  known:", known_hits, flush=True)
        print("  strong:", a.get("strong"), flush=True)
        print("  top10:", a.get("top10"), flush=True)

    # Enger Zoom um 103 bei overload vs moderate
    print("\n=== ZOOM 102.5–103.5 avg=8 SR=1.024M — Gain 20 vs 48 ===", flush=True)
    for g in [20, 48]:
        j = capture(
            mode="range",
            start_mhz=102.5,
            stop_mhz=103.5,
            ppm=ppm,
            gain=g,
            sample_count=65536,
            avg_frames=8,
            sample_rate_hz=1024000,
        )
        peaks = j.get("peaks") or []
        print(f"gain={g} n={len(peaks)} top10=",
              [(round(p["freq_mhz"], 4), p["db"]) for p in
               sorted(peaks, key=lambda x: -float(x["db"]))[:10]], flush=True)

    print("\nDONE", flush=True)
    with open("/tmp/ukw_gain_scan.json", "w") as f:
        json.dump(results, f, indent=2)


if __name__ == "__main__":
    main()

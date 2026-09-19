#!/usr/bin/env python3
"""
Schneller UKW-Detektor: 100-kHz-Raster + Kanalenergie (±75 kHz),
Cluster-Merge (~180 kHz), Abgleich mit bekannten Sendern.
"""
from __future__ import annotations

import json
import math
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:8080"

# Nutzer + BR Grünten/Schwaben (Allgäu) + Kandidaten
LABELS = {
    90.2: "RT1 (Nutzer)",
    90.7: "Bayern 1 Grünten",
    88.7: "Bayern 2 Grünten?",
    95.8: "Bayern 3 Grünten?",
    98.5: "Bayern 3 (Nutzer)",
    101.0: "BR Klassik Grünten?",
    103.0: "SWR3 (Nutzer)",
    104.4: "Antenne Bayern (Nutzer)",
    106.9: "BR24 / ex B5 Grünten?",
    107.6: "BR24 Hühnerberg?",
}


def capture(**kw):
    q = urllib.parse.urlencode(kw)
    req = urllib.request.Request(BASE + "/api/spectrum/capture?" + q, method="POST")
    with urllib.request.urlopen(req, timeout=400) as r:
        return json.loads(r.read().decode())


def channel_energy(spec, start_mhz, bin_hz, f_c, half_khz=75.0):
    if not spec or bin_hz <= 0:
        return None
    lo = f_c - half_khz / 1000.0
    hi = f_c + half_khz / 1000.0
    acc = 0.0
    n = 0
    peak = -1e9
    peak_f = None
    for i, db in enumerate(spec):
        f = start_mhz + i * bin_hz / 1e6
        if lo <= f <= hi:
            acc += 10.0 ** (db / 10.0)
            n += 1
            if db > peak:
                peak = db
                peak_f = f
    if n == 0:
        return None
    return {
        "mean_db": 10.0 * math.log10(acc / n),
        "peak_db": peak,
        "peak_f": peak_f,
        "bins": n,
    }


def merge_clusters(hits, merge_mhz=0.18):
    """hits: list of {f, mean_db, peak_db}; merge neighbors within merge_mhz."""
    if not hits:
        return []
    hits = sorted(hits, key=lambda h: h["f"])
    clusters = []
    cur = [hits[0]]
    for h in hits[1:]:
        if h["f"] - cur[-1]["f"] <= merge_mhz:
            cur.append(h)
        else:
            clusters.append(cur)
            cur = [h]
    clusters.append(cur)

    out = []
    for c in clusters:
        # Energieschwerpunkt (linear)
        wsum = 0.0
        fsum = 0.0
        best = c[0]
        for h in c:
            w = 10.0 ** (h["mean_db"] / 10.0)
            wsum += w
            fsum += h["f"] * w
            if h["mean_db"] > best["mean_db"]:
                best = h
        out.append(
            {
                "f_centroid": round(fsum / wsum, 3),
                "f_peak_chan": best["f"],
                "mean_db": round(best["mean_db"], 2),
                "peak_db": round(best["peak_db"], 2),
                "n_chans": len(c),
                "span_mhz": round(c[-1]["f"] - c[0]["f"], 3),
            }
        )
    out.sort(key=lambda x: -x["mean_db"])
    return out


def label_for(f, tol=0.05):
    for fk, name in LABELS.items():
        if abs(f - fk) <= tol:
            return name
    return None


def main():
    ppm = 49
    gain = 25
    print(f"=== Channel-energy scan 87.5–108  gain={gain} avg=2 samples=32k ===", flush=True)
    j = capture(
        mode="range",
        start_mhz=87.5,
        stop_mhz=108.0,
        ppm=ppm,
        gain=gain,
        sample_count=32768,
        avg_frames=2,
    )
    print(
        "ok", j.get("ok"),
        "win", j.get("windows_ok"), "/", j.get("windows_total"),
        "sr", j.get("sample_rate_hz"),
        "rbw", j.get("rbw_hz"),
        "err", j.get("error"),
        flush=True,
    )
    if not j.get("ok"):
        # Retry once after noting failure
        print("RETRY avg=1", flush=True)
        j = capture(
            mode="range",
            start_mhz=87.5,
            stop_mhz=108.0,
            ppm=ppm,
            gain=gain,
            sample_count=32768,
            avg_frames=1,
        )
        print(
            "ok", j.get("ok"),
            "win", j.get("windows_ok"), "/", j.get("windows_total"),
            "err", j.get("error"),
            flush=True,
        )
    if not j.get("ok"):
        raise SystemExit("band capture failed")

    spec = j.get("spectrum_db") or []
    start = float(j.get("f0_mhz") or j.get("start_mhz") or 87.5)
    bin_hz = float(j.get("bin_hz") or 0)

    # Noise floor: 20th percentile of spectrum
    srt = sorted(spec)
    floor = srt[max(0, len(srt) // 5)]
    thresh = floor + 10.0
    print(f"noise_20pct={floor:.1f} dB  thresh={thresh:.1f} dB (floor+10)", flush=True)

    # 100 kHz grid
    hits = []
    f = 87.5
    while f <= 108.001:
        e = channel_energy(spec, start, bin_hz, round(f, 1), half_khz=75.0)
        if e and e["mean_db"] >= thresh:
            hits.append(
                {
                    "f": round(f, 1),
                    "mean_db": e["mean_db"],
                    "peak_db": e["peak_db"],
                    "peak_f": e["peak_f"],
                }
            )
        f = round(f + 0.1, 1)

    clusters = merge_clusters(hits, merge_mhz=0.18)
    print(f"\ngrid_hits={len(hits)}  clusters={len(clusters)}", flush=True)
    print("\n=== DETEKTED CLUSTERS (stärkste zuerst) ===", flush=True)
    for i, c in enumerate(clusters[:40], 1):
        lab = label_for(c["f_centroid"]) or label_for(c["f_peak_chan"])
        tag = f"  ← {lab}" if lab else ""
        print(
            f"{i:2d}. {c['f_centroid']:6.1f} MHz  mean={c['mean_db']:5.1f} dB  "
            f"peak={c['peak_db']:5.1f}  chans={c['n_chans']}  span={c['span_mhz']}{tag}",
            flush=True,
        )

    print("\n=== EXAKT bekannte / verdächtige Frequenzen ===", flush=True)
    check = sorted(LABELS.keys())
    for f in check:
        e = channel_energy(spec, start, bin_hz, f, half_khz=75.0)
        above = e and e["mean_db"] >= thresh
        status = "JA" if above else "nein/schwach"
        print(
            f"  {f:5.1f} {LABELS[f]:28s}  "
            f"mean={e['mean_db'] if e else float('nan'):5.1f}  "
            f"peak={e['peak_db'] if e else float('nan'):5.1f}  [{status}]",
            flush=True,
        )

    # Unlabeled strong clusters → Kandidaten weitere Sender
    print("\n=== Unbekannte starke Cluster (keine Label-Match ±50 kHz) ===", flush=True)
    unk = []
    for c in clusters:
        if label_for(c["f_centroid"], 0.05) or label_for(c["f_peak_chan"], 0.05):
            continue
        if c["mean_db"] >= thresh + 2:
            unk.append(c)
    for c in unk[:20]:
        print(
            f"  {c['f_centroid']:6.1f} MHz  mean={c['mean_db']:5.1f} dB  "
            f"chans={c['n_chans']}",
            flush=True,
        )

    out = {
        "floor_db": floor,
        "thresh_db": thresh,
        "n_hits": len(hits),
        "clusters": clusters,
        "known_check": {
            str(f): channel_energy(spec, start, bin_hz, f, 75.0) for f in check
        },
        "unknown_strong": unk[:20],
    }
    with open("/tmp/ukw_channel_detect.json", "w") as fp:
        json.dump(out, fp, indent=2)
    print("\nDONE wrote /tmp/ukw_channel_detect.json", flush=True)


if __name__ == "__main__":
    main()

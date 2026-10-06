#!/usr/bin/env python3
"""Lab dry-run of F2/Q4b protocol on L3 (3 slots only) — not full 64-file matrix.

Sequence:
  remount → eager fav1 → eager fav2 → re-eager fav1 (expect 0 sim reads / cache)
  → remount → eager fav1 (expect re-read)
  Optional: eager fav0 (8 MiB) for Q4a sample on current geometry.

Uses nbt_hu_sim HuSim (same as G6). Field F2/Q4b still required on car.

  sg disk -c 'python3 tools/m3_lab_q4_cache_matrix.py --sg /dev/sg0 --out …/lab88-q4-prep'
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("nbt_hu_sim", ROOT / "nbt_hu_sim.py")
assert spec and spec.loader
m = importlib.util.module_from_spec(spec)
sys.modules["nbt_hu_sim"] = m
spec.loader.exec_module(m)


def main() -> int:
    ap = argparse.ArgumentParser(description="Lab Q4/F2 cache matrix dry-run (3 slots)")
    ap.add_argument("--esp", default="http://192.168.178.88")
    ap.add_argument("--esp-ip", default="192.168.178.88")
    ap.add_argument("--sg", default="/dev/sg0")
    ap.add_argument("--profile", default=str(ROOT / "profiles" / "nbt_evo_feld-s1-1700.json"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--with-fav0", action="store_true", help="also eager-read fav0 (8 MiB Q4a sample)")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    esp = args.esp.rstrip("/")
    report: dict = {"steps": [], "pass": False}

    pump = m.prep_lab(esp, args.esp_ip, None, remount=True)
    hu = m.HuSim(args.sg, m.load_profile(Path(args.profile)))
    try:
        hu.open()
        hu.refresh_slots(esp)

        def safe_rc() -> int | None:
            try:
                return int(m.snap(esp).get("readCount") or 0)
            except Exception as e:
                return None  # ESP HTTP often times out after 8 MiB eager

        def step(name: str, fn) -> None:
            t0 = time.monotonic()
            rc0 = safe_rc()
            n_ev = len(hu.events)
            err = None
            result = {}
            try:
                result = fn() or {}
            except Exception as e:
                err = str(e)
            rc1 = safe_rc()
            n_reads = sum(1 for e in hu.events[n_ev:] if e.get("op") == "read")
            d_rc = (rc1 - rc0) if rc0 is not None and rc1 is not None else None
            row = {
                "step": name,
                "sim_reads": n_reads,
                "d_readCount": d_rc,
                "dt_s": round(time.monotonic() - t0, 3),
                **result,
            }
            if err:
                row["err"] = err
            if rc0 is None or rc1 is None:
                row["snap_timeout"] = True
            report["steps"].append(row)
            print(json.dumps(row), flush=True)

        step("eager_fav1", lambda: {"covered": hu.eager_read("fav1")})
        step("eager_fav2", lambda: {"covered": hu.eager_read("fav2")})
        step(
            "re_fav1_cache",
            lambda: {"covered": hu.eager_read("fav1"), "expect_sim_reads_0": True},
        )
        # remount clear
        pump = m.prep_lab(esp, args.esp_ip, pump, remount=True)
        hu.open()
        hu.cache.clear()
        hu.events.clear()
        hu.refresh_slots(esp)
        step("post_remount_fav1", lambda: {"covered": hu.eager_read("fav1")})

        if args.with_fav0 and "fav0" in hu.slots:
            hu.cache.clear()
            step("eager_fav0_8MiB", lambda: {"covered": hu.eager_read("fav0"), "size": hu.slots["fav0"].size})

        cache_ok = any(
            s["step"] == "re_fav1_cache" and s["sim_reads"] == 0 for s in report["steps"]
        )
        reread_ok = any(
            s["step"] == "post_remount_fav1" and s["sim_reads"] >= 100 for s in report["steps"]
        )
        report["pass"] = bool(cache_ok and reread_ok)
        report["note"] = (
            "Lab 3-slot dry-run of G6/F2 protocol. Full Q4b needs N>>3 files (field/build)."
        )
    finally:
        hu.close()
        try:
            pump.close()
        except Exception:
            pass

    (out / "REPORT.json").write_text(json.dumps(report, indent=2))
    print(f"OUT {out} overall={'PASS' if report['pass'] else 'FAIL'}")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Lab Hörfenster-Leiter: Bridge-Prefill → REPLUG bei gewählter Bitrate (ohne FW-Flash).

Beispiel:
  python3 tools/lab_fenster_bitrate.py --bitrate 32k --rounds 3 --out docs/betrieb/artifacts-…/fenster
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

BITRATE = {
    "48k": 6000,
    "32k": 4000,
    "24k": 3000,
    "64k": 8000,
    "96k": 12000,
}
BRIDGE = Path("/home/martin/projects/esphub/esp32.pidrive/tools/pump_bridge.py")
SIM = Path(__file__).resolve().parent / "nbt_hu_sim.py"


def kill_bridge(host: str) -> None:
    subprocess.run(
        ["pkill", "-f", f"python3 {BRIDGE} --transport tcp --host {host}"],
        check=False,
        capture_output=True,
    )
    time.sleep(1.5)


def main() -> int:
    ap = argparse.ArgumentParser(description="Lab bitrate window: bridge prefill + REPLUG")
    ap.add_argument("--bitrate", default="32k", choices=sorted(BITRATE))
    ap.add_argument("--rounds", type=int, default=1)
    ap.add_argument("--esp", default="http://192.168.178.88")
    ap.add_argument("--host", default="192.168.178.88")
    ap.add_argument("--sg", default="/dev/sg0")
    ap.add_argument("--prefill-s", type=float, default=14.0)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    bps = BITRATE[args.bitrate]
    args.out.mkdir(parents=True, exist_ok=True)
    results = []

    for i in range(1, args.rounds + 1):
        rdir = args.out / f"r{i:02d}"
        rdir.mkdir(exist_ok=True)
        kill_bridge(args.host)
        blog = rdir / "bridge.log"
        br = subprocess.Popen(
            [
                sys.executable,
                str(BRIDGE),
                "--transport",
                "tcp",
                "--host",
                args.host,
                "--bitrate",
                args.bitrate,
                "--target-bps",
                str(bps),
                "--marker",
                "--marker-period",
                "1",
            ],
            stdout=blog.open("w"),
            stderr=subprocess.STDOUT,
        )
        (rdir / "bridge.pid").write_text(str(br.pid))
        time.sleep(args.prefill_s)
        br.terminate()
        try:
            br.wait(timeout=5)
        except subprocess.TimeoutExpired:
            br.kill()
        time.sleep(1.5)
        kill_bridge(args.host)

        sim = subprocess.run(
            [
                sys.executable,
                str(SIM),
                "--golden",
                "REPLUG",
                "--sg",
                args.sg,
                "--esp",
                args.esp,
                "--replug-cmd-kib",
                "4",
                "--head-pause-ms",
                "19",
                "--period-ms",
                "5.1",
                "--producer-burst",
                "1.0",
                "--replug-prefill-s",
                "12",
                "--replug-id3-bytes",
                "3300",
                "--replug-bps",
                str(bps),
                "--out",
                str(rdir / "replug"),
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        (rdir / "replug.log").write_text(sim.stdout + "\n" + sim.stderr)
        rep = {}
        rp = rdir / "replug" / "REPORT.json"
        if rp.exists():
            rep = (json.loads(rp.read_text()).get("results") or {}).get("REPLUG") or {}
        row = {
            "i": i,
            "pass": bool(rep.get("pass")),
            "live_bytes_file": rep.get("live_bytes_file"),
            "live_s_at_48k": rep.get("live_s_at_48k"),
            "live_s_at_bps": rep.get("live_s_at_bps"),
            "realtime_bps": rep.get("realtime_bps"),
            "identity_ok": rep.get("identity_ok"),
            "ring_full_pre": rep.get("ring_full_pre"),
            "sim_rc": sim.returncode,
        }
        results.append(row)
        print(json.dumps(row))

    summary = {
        "bitrate": args.bitrate,
        "bps": bps,
        "rounds": args.rounds,
        "pass_n": sum(1 for r in results if r["pass"]),
        "results": results,
        "pass": all(r["pass"] for r in results) and len(results) == args.rounds,
    }
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2))
    print("SUMMARY", json.dumps(summary))
    print("OUT", args.out)
    return 0 if summary["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

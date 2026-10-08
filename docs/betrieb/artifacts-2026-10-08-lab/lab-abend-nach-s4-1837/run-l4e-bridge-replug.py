#!/usr/bin/env python3
"""L4e: Dauer-Bridge + REPLUG×5 — weniger ring_full_pre-Fails; Uptime-Drops zählen."""
from __future__ import annotations

import json
import re
import subprocess
import time
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parent
ESP = "http://192.168.178.88"
BRIDGE = "/home/martin/projects/esphub/esp32.pidrive/tools/pump_bridge.py"
N = 5


def status() -> dict:
    d = json.load(urllib.request.urlopen(f"{ESP}/api/status", timeout=5))
    u = d.get("uptime") or ""
    m = re.match(r"(?:(\d+)h\s*)?(?:(\d+)min\s*)?(?:(\d+)s)?", u)
    sec = (
        int(m.group(1) or 0) * 3600
        + int(m.group(2) or 0) * 60
        + int(m.group(3) or 0)
        if m
        else None
    )
    return {
        "uptime": u,
        "sec": sec,
        "serial": (d.get("msc") or {}).get("usbSerial"),
        "peer": d.get("pumpTcpPeer") or "",
        "pump": d.get("pumpUp"),
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    # stop other bridges to this host
    subprocess.call(
        [
            "pkill",
            "-f",
            r"python3 .*/pump_bridge\.py --transport tcp --host 192\.168\.178\.88",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(2)
    blog = OUT / "bridge.log"
    bp = subprocess.Popen(
        [
            "python3",
            BRIDGE,
            "--transport",
            "tcp",
            "--host",
            "192.168.178.88",
            "--bitrate",
            "48k",
            "--target-bps",
            "6000",
            "--marker",
            "--marker-period",
            "1",
        ],
        stdout=blog.open("w"),
        stderr=subprocess.STDOUT,
    )
    (OUT / "bridge.pid").write_text(str(bp.pid) + "\n")
    time.sleep(10)
    pre = status()
    (OUT / "pre.json").write_text(json.dumps(pre, indent=2) + "\n")
    print("pre", pre, "bridge_pid", bp.pid, flush=True)
    if pre.get("peer") != "192.168.178.187":
        print("WARN unexpected peer", pre.get("peer"), flush=True)

    rows = []
    for i in range(1, N + 1):
        # wait ring fill a bit
        time.sleep(12)
        dest = OUT / f"r{i:02d}"
        log = OUT / f"r{i:02d}.log"
        # stop bridge briefly so sim can handshake, or keep? Earlier fail was dual client.
        # Strategy: kill bridge, sim owns pump for REPLUG, restart bridge after.
        bp.poll()
        if bp.returncode is None:
            bp.terminate()
            try:
                bp.wait(timeout=5)
            except subprocess.TimeoutExpired:
                bp.kill()
        time.sleep(2)
        cmd = [
            "sudo",
            "-A",
            "python3",
            "/home/martin/projects/pidrive/tools/nbt_hu_sim.py",
            "--golden",
            "REPLUG",
            "--sg",
            "/dev/sg0",
            "--esp",
            ESP,
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
            "--out",
            str(dest),
        ]
        with log.open("w") as f:
            rc = subprocess.call(cmd, stdout=f, stderr=subprocess.STDOUT)
        text = log.read_text(errors="replace")
        st = status()
        st.update(
            {
                "n": i,
                "rc": rc,
                "pass": "overall=PASS" in text,
                "fail": "overall=FAIL" in text,
            }
        )
        # extract live_s if present
        m = re.search(r'"live_s_at_48k":\s*([0-9.]+)', text)
        if m:
            st["live_s"] = float(m.group(1))
        rows.append(st)
        print(i, "PASS" if st["pass"] else "FAIL", "up", st["uptime"], "live_s", st.get("live_s"), flush=True)
        # restart bridge for next prefill
        bp = subprocess.Popen(
            [
                "python3",
                BRIDGE,
                "--transport",
                "tcp",
                "--host",
                "192.168.178.88",
                "--bitrate",
                "48k",
                "--target-bps",
                "6000",
                "--marker",
                "--marker-period",
                "1",
            ],
            stdout=blog.open("a"),
            stderr=subprocess.STDOUT,
        )
        time.sleep(8)

    drops = 0
    prev = None
    for r in rows:
        s = r.get("sec")
        if s is not None and prev is not None and s + 3 < prev:
            drops += 1
        if s is not None:
            prev = s
    summary = {
        "cycles": len(rows),
        "pass": sum(1 for r in rows if r["pass"]),
        "fail": sum(1 for r in rows if r["fail"]),
        "uptime_drops": drops,
        "live_s": [r.get("live_s") for r in rows if r.get("live_s") is not None],
        "first_up": rows[0]["uptime"] if rows else None,
        "last_up": rows[-1]["uptime"] if rows else None,
        "method": "prefill bridge 12s → stop → REPLUG (sim pump) → restart bridge ×5",
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (OUT / "status.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    print(json.dumps(summary, indent=2), flush=True)
    # leave bridge running
    return 0 if drops == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

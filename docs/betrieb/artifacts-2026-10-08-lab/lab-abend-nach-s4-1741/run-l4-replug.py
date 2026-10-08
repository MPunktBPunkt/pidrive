#!/usr/bin/env python3
"""L4 fallback: REPLUG stress; count ESP uptime drops (USB authorized is RO here)."""
from __future__ import annotations

import json
import re
import subprocess
import time
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parent
ESP = "http://192.168.178.88"
SG = "/dev/sg0"
N = 15


def status() -> dict:
    d = json.load(urllib.request.urlopen(f"{ESP}/api/status", timeout=5))
    u = d.get("uptime") or ""
    m = re.match(r"(?:(\d+)min\s*)?(?:(\d+)s)?", u)
    sec = int(m.group(1) or 0) * 60 + int(m.group(2) or 0) if m else None
    return {
        "uptime": u,
        "sec": sec,
        "serial": (d.get("msc") or {}).get("usbSerial"),
        "peer": d.get("pumpTcpPeer") or "",
        "otg": d.get("otgUp"),
    }


def main() -> int:
    # stop our pump bridges only (exact argv path)
    subprocess.call(
        ["pkill", "-f", r"python3 .*/pump_bridge\.py --transport tcp --host 192\.168\.178\.88"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(2)
    pre = status()
    (OUT / "l4-pre.json").write_text(json.dumps(pre, indent=2) + "\n")
    print("pre", pre, flush=True)

    rows: list[dict] = []
    fails: list[int] = []
    for i in range(1, N + 1):
        dest = OUT / f"l4b-r{i:02d}"
        dest.mkdir(exist_ok=True)
        log = OUT / f"l4b-r{i:02d}.log"
        cmd = [
            "sudo",
            "python3",
            "/home/martin/projects/pidrive/tools/nbt_hu_sim.py",
            "--golden",
            "REPLUG",
            "--sg",
            SG,
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
            "8",
            "--replug-id3-bytes",
            "3300",
            "--out",
            str(dest),
        ]
        with log.open("w") as f:
            rc = subprocess.call(cmd, stdout=f, stderr=subprocess.STDOUT)
        st = status()
        st.update({"n": i, "rc": rc})
        rows.append(st)
        if rc != 0:
            fails.append(i)
        print(i, "rc", rc, "up", st["uptime"], "ser", st["serial"], flush=True)
        time.sleep(1)

    drops = 0
    prev = None
    for r in rows:
        s = r.get("sec")
        if s is not None and prev is not None and s + 3 < prev:
            drops += 1
        if s is not None:
            prev = s

    passed = 0
    for p in sorted(OUT.glob("l4b-r*/REPORT.json")):
        blob = p.read_text(encoding="utf-8", errors="replace")
        if "PASS" in blob:
            passed += 1

    summary = {
        "cycles": len(rows),
        "rc_nonzero": fails,
        "uptime_drops": drops,
        "passed_reports_PASS_string": passed,
        "reports": len(list(OUT.glob("l4b-r*/REPORT.json"))),
        "first": rows[0] if rows else None,
        "last": rows[-1] if rows else None,
        "note": "sysfs USB authorized RO on this host; L4 via REPLUG×N (sim owns pump)",
    }
    (OUT / "l4-replug-status.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
    )
    (OUT / "l4-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2), flush=True)
    return 0 if not fails and drops == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

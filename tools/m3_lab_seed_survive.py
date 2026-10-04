#!/usr/bin/env python3
"""Lab: arm body_seed and prove it stays active across a settle window.

Reproduces the 1738 GO-gate failure class without a car:
  - Oracle A: SoftAP body_read still Q3B1*
  - Survive: active=True for --settle-s seconds (default 30)
  - Optional host body hit: dd past LBA 761 → bytesServed rises

Does not change Detect/Ring/PSRAM. Needs Lab ESP (+ optional /dev/sda).

Example:
  python3 tools/m3_lab_seed_survive.py --esp http://192.168.178.88
  sg disk -c 'python3 tools/m3_lab_seed_survive.py --esp http://192.168.178.88 --dev /dev/sda --hit'
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import time
import urllib.request
from pathlib import Path


def http_json(url: str, method: str = "GET", body: bytes | None = None, timeout: float = 12) -> dict:
    req = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={"Content-Type": "application/json"} if body is not None else {},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        return json.loads(raw.decode()) if raw else {}


def http_raw(url: str, timeout: float = 12) -> bytes:
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.read()


def parse_uptime_s(text: str | None) -> int | None:
    if not text:
        return None
    s = 0
    for n, unit in re.findall(r"(\d+)\s*(h|min|s)", text):
        n = int(n)
        s += n * (3600 if unit == "h" else 60 if unit == "min" else 1)
    return s


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--esp", default="http://192.168.178.88")
    ap.add_argument("--slot", type=int, default=0)
    ap.add_argument("--tag", default="B", choices=["A", "B"])
    ap.add_argument("--from-off", type=int, default=348160)
    ap.add_argument("--settle-s", type=int, default=30)
    ap.add_argument("--dev", default="")
    ap.add_argument("--hit", action="store_true", help="dd LBA 761+ and expect bytesServed rise")
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    esp = args.esp.rstrip("/")

    day = time.strftime("%Y-%m-%d")
    stamp = time.strftime("%H%M")
    out = Path(args.out) if args.out else Path(
        f"docs/betrieb/artifacts-{day}-lab/lab88-seed-survive-{stamp}"
    )
    out.mkdir(parents=True, exist_ok=True)
    report: dict = {"esp": esp, "ok": False, "steps": []}

    def step(name: str, ok: bool, detail: dict | str) -> None:
        report["steps"].append({"name": name, "ok": ok, "detail": detail})
        print(f"{'PASS' if ok else 'FAIL'} {name}: {detail}", flush=True)

    try:
        pre = http_json(f"{esp}/api/status")
    except Exception as e:
        step("reach", False, str(e))
        (out / "REPORT.json").write_text(json.dumps(report, indent=2))
        print(f"OUT={out}")
        return 2
    (out / "status-00-pre.json").write_text(json.dumps(pre, indent=2))
    step("reach", True, {"version": pre.get("version"), "uptime": pre.get("uptime")})

    http_json(f"{esp}/api/lab/stop", method="POST", body=b"{}")
    time.sleep(0.3)
    seed = http_json(
        f"{esp}/api/lab/body_seed",
        method="POST",
        body=json.dumps(
            {"slot": args.slot, "tag": args.tag, "fromOff": args.from_off}
        ).encode(),
    )
    (out / "seed.json").write_text(json.dumps(seed, indent=2))
    step("arm", bool(seed.get("active")), seed)

    raw = http_raw(
        f"{esp}/api/lab/body_read?slot={args.slot}&off={args.from_off}&n=8192"
    )
    (out / f"softap_{args.tag}_lba761.bin").write_bytes(raw)
    oracle_a = raw[:4] == b"Q3B1" and raw[4:5] == args.tag.encode() and len(raw) == 8192
    step(
        "oracleA",
        oracle_a,
        {"prefix": raw[:8].decode("latin1", "replace"), "sha16": hashlib.sha256(raw).hexdigest()[:16]},
    )

    st1 = http_json(f"{esp}/api/status")
    (out / "status-01-seeded.json").write_text(json.dumps(st1, indent=2))
    up1 = parse_uptime_s(st1.get("uptime"))
    bs1 = (st1.get("msc") or {}).get("bodySeed") or {}
    if not bs1.get("active"):
        step("gate_immediate", False, bs1)
        (out / "REPORT.json").write_text(json.dumps(report, indent=2))
        print(f"OUT={out}")
        return 1
    step("gate_immediate", True, {"uptime": st1.get("uptime"), "seedB": bs1.get("bytesServed")})

    t0 = time.time()
    died = None
    while time.time() - t0 < args.settle_s:
        time.sleep(2)
        st = http_json(f"{esp}/api/status")
        bs = (st.get("msc") or {}).get("bodySeed") or {}
        up = parse_uptime_s(st.get("uptime"))
        if not bs.get("active"):
            died = {"reason": "inactive", "status": {"uptime": st.get("uptime"), "bodySeed": bs}}
            break
        if up1 is not None and up is not None and up + 15 < up1:
            died = {"reason": "reboot", "uptime_was": up1, "uptime_now": up}
            break
    st2 = http_json(f"{esp}/api/status")
    (out / "status-02-after-settle.json").write_text(json.dumps(st2, indent=2))
    if died:
        step("survive", False, died)
        report["ok"] = False
        (out / "REPORT.json").write_text(json.dumps(report, indent=2))
        (out / "EAR.txt").write_text(
            f"lab seed survive FAIL {time.strftime('%Y-%m-%dT%H:%M:%S')}\n{json.dumps(died)}\n"
        )
        print(f"OUT={out}")
        return 1
    step(
        "survive",
        True,
        {"settle_s": args.settle_s, "uptime": st2.get("uptime"), "bodySeed": (st2.get("msc") or {}).get("bodySeed")},
    )

    if args.hit:
        if not args.dev:
            step("hit", False, "need --dev for host dd")
        else:
            b0 = int(((st2.get("msc") or {}).get("bodySeed") or {}).get("bytesServed") or 0)
            subprocess.check_call(
                [
                    "dd",
                    f"if={args.dev}",
                    "bs=512",
                    "skip=761",
                    "count=64",
                    "iflag=direct",
                    "status=none",
                    "of=/dev/null",
                ],
                stderr=subprocess.DEVNULL,
            )
            time.sleep(0.5)
            st3 = http_json(f"{esp}/api/status")
            (out / "status-03-after-hit.json").write_text(json.dumps(st3, indent=2))
            b1 = int(((st3.get("msc") or {}).get("bodySeed") or {}).get("bytesServed") or 0)
            step("hit_bytesServed", b1 > b0, {"before": b0, "after": b1, "delta": b1 - b0})

    report["ok"] = all(s["ok"] for s in report["steps"])
    (out / "REPORT.json").write_text(json.dumps(report, indent=2))
    (out / "EAR.txt").write_text(
        f"lab seed survive {'PASS' if report['ok'] else 'FAIL'} {time.strftime('%Y-%m-%dT%H:%M:%S')}\n"
        f"settle_s={args.settle_s} hit={args.hit}\nOUT={out}\n"
    )
    print(f"OUT={out} ok={report['ok']}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

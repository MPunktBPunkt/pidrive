#!/usr/bin/env python3
"""Lab: trigger mid-file cold body reads and verify cold_body_burst diag (log only).

Does NOT change Detect policy. Confirms FW emits cold_body_burst with eval=not_from_head
when host reads past headLbaSlop with >=32 KiB volume.

Example:
  sg disk -c 'python3 tools/m3_lab_detect_cold_body.py --esp http://192.168.178.88 --dev /dev/sda'
"""
from __future__ import annotations

import argparse
import json
import subprocess
import time
import urllib.request
from pathlib import Path


def http_json(url: str, method: str = "GET", body: bytes | None = None) -> dict:
    req = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={"Content-Type": "application/json"} if body is not None else {},
    )
    with urllib.request.urlopen(req, timeout=12) as r:
        raw = r.read()
        return json.loads(raw.decode()) if raw else {}


def dd(dev: str, lba: int, sectors: int) -> int:
    subprocess.check_call(
        [
            "dd",
            f"if={dev}",
            "bs=512",
            f"skip={lba}",
            f"count={sectors}",
            "iflag=direct",
            "status=none",
            "of=/dev/null",
        ],
        stderr=subprocess.DEVNULL,
    )
    return sectors * 512


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--esp", default="http://192.168.178.88")
    ap.add_argument("--dev", default="/dev/sda")
    ap.add_argument("--slot", type=int, default=0)
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    esp = args.esp.rstrip("/")

    stamp = time.strftime("%H%M")
    day = time.strftime("%Y-%m-%d")
    out = Path(args.out) if args.out else Path(
        f"docs/betrieb/artifacts-{day}-lab/lab88-detect-cold-{stamp}"
    )
    out.mkdir(parents=True, exist_ok=True)

    http_json(f"{esp}/api/lab/stop", method="POST", body=b"{}")
    time.sleep(0.3)

    st0 = http_json(f"{esp}/api/status")
    (out / "status-00.json").write_text(json.dumps(st0, indent=2))
    slot = st0["msc"]["slotMap"][args.slot]
    lba0 = int(slot["lba0"])
    print(f"fw={st0['version']} serial={st0['msc'].get('usbSerial')} lba0={lba0}")
    ev0 = http_json(f"{esp}/api/events")
    next0 = int(ev0.get("nextSeq") or 0)
    c0 = int(st0["msc"].get("coldBodyBurstCount") or 0)

    # 1) Cold body first — must emit cold_body_burst / not_from_head, no play.guess
    print("== cold body burst sim from LBA 761 ==")
    start = lba0 + (348160 // 512)  # 761 when lba0=81
    total = 0
    for i in range(0, 96, 8):  # 12 × 8 sectors = 48 KiB
        total += dd(args.dev, start + i, 8)
        time.sleep(0.01)
    print(f"  transferred≈{total} B")
    time.sleep(1.0)

    st1 = http_json(f"{esp}/api/status")
    (out / "status-01-after-cold.json").write_text(json.dumps(st1, indent=2))
    c1 = int(st1["msc"].get("coldBodyBurstCount") or 0)
    ev1 = http_json(f"{esp}/api/events")
    (out / "events-after-cold.json").write_text(json.dumps(ev1, indent=2))

    bursts = [
        e
        for e in ev1.get("events") or []
        if e.get("code") == "cold_body_burst" and int(e.get("seq") or 0) >= next0
    ]
    rejects = [
        e
        for e in ev1.get("events") or []
        if e.get("code") == "play.reject" and int(e.get("seq") or 0) >= next0
    ]
    guesses_after_cold = [
        e
        for e in ev1.get("events") or []
        if e.get("code") == "play.guess" and int(e.get("seq") or 0) >= next0
    ]

    has_not_from_head = any(
        ("ev=not_from_head" in (b.get("detail") or ""))
        or ("not_from_head" in (b.get("detail") or ""))
        for b in bursts
    )
    no_guess_from_cold = len(guesses_after_cold) == 0

    # 2) Warm-head contrast (may fire play.guess — documents Detect bias)
    print("== warm head contrast ==")
    next1 = int(ev1.get("nextSeq") or next0)
    dd(args.dev, lba0, 16)
    time.sleep(0.3)
    # accumulate enough for seq_short→ok path
    for _ in range(4):
        dd(args.dev, lba0, 16)
        time.sleep(0.05)
    time.sleep(0.8)
    ev2 = http_json(f"{esp}/api/events")
    (out / "events-after-warm.json").write_text(json.dumps(ev2, indent=2))
    guesses_warm = [
        e
        for e in ev2.get("events") or []
        if e.get("code") == "play.guess" and int(e.get("seq") or 0) >= next1
    ]

    verdict = "FAIL"
    if c1 > c0 and bursts and has_not_from_head and no_guess_from_cold:
        verdict = "PASS"
    elif c1 > c0 and bursts:
        verdict = "PASS_WEAK"

    report = {
        "verdict": verdict,
        "fw": st0.get("version"),
        "serial": st0["msc"].get("usbSerial"),
        "coldBodyBurstCount": [c0, c1],
        "burst_events": bursts,
        "play_reject_sample": rejects[:5],
        "play_guess_after_cold": guesses_after_cold,
        "play_guess_after_warm_contrast": guesses_warm,
        "policy_unchanged_on_cold": no_guess_from_cold,
        "warm_head_can_fire_detect": len(guesses_warm) > 0,
        "note": "log-only; Detect policy not changed; cold sim is host-dd not HU",
    }
    (out / "report.json").write_text(json.dumps(report, indent=2))
    (out / "NOTES.md").write_text(
        "\n".join(
            [
                f"# Detect cold_body_burst Lab — `{out.name}`",
                "",
                f"**Verdict:** `{verdict}`",
                f"**FW:** `{report['fw']}`",
                f"**coldBodyBurstCount:** {c0} → {c1}",
                f"**cold_body_burst events:** {len(bursts)}",
                f"**play.guess after cold:** {len(guesses_after_cold)} (must be 0)",
                f"**play.guess after warm contrast:** {len(guesses_warm)} (may be >0 — Detect bias)",
                "",
                "## Expectation",
                "- cold_body_burst fires with `ev=not_from_head` / `w=0`",
                "- no play.guess from mid-file cold burst (policy unchanged)",
                "- warm head may still fire Detect — documents the field bug",
                "",
            ]
        )
    )
    print(json.dumps(report, indent=2)[:2000])
    print(f"artefacts: {out}")
    return 0 if verdict.startswith("PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())

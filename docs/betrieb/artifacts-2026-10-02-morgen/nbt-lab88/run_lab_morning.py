#!/usr/bin/env python3
"""Lab morning follow-up: armed prefetch_then_warm + paced fav0/fav1."""
from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ESP = "http://192.168.178.88"
HARNESS = Path("/tmp/nbt_harness")


def get() -> dict:
    return json.load(urllib.request.urlopen(ESP + "/api/status", timeout=5))


def post(path: str, body: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        ESP + path,
        data=data,
        headers={"Content-Type": "application/json"} if data else {},
        method="POST",
    )
    return json.load(urllib.request.urlopen(req, timeout=10))


def wait_uid(uid: str, timeout: float = 25.0) -> dict:
    t0 = time.time()
    while time.time() - t0 < timeout:
        d = get()
        s = d.get("stream") or {}
        print(
            f"  wait {uid}: play={d.get('playingUid')} stream={s.get('uid')} "
            f"active={s.get('active')} size={s.get('size')} id3={s.get('id3Len')}",
            flush=True,
        )
        if s.get("active") and s.get("uid") == uid and int(s.get("size") or 0) > 0:
            return d
        time.sleep(0.5)
    raise SystemExit(f"timeout waiting for stream {uid}")


def main() -> None:
    sys.path.insert(0, str(HARNESS))
    from nbt_report import analyze, to_markdown

    print("=== stop ===", flush=True)
    print(post("/api/lab/stop"), flush=True)
    time.sleep(2)

    print("=== lab/play fav2 + prefetch rerun ===", flush=True)
    print(post("/api/lab/play", {"uid": "fav2"}), flush=True)
    wait_uid("fav2")
    out = HARNESS / "reports" / "prefetch_then_warm__rerun__20261002.json"
    subprocess.check_call(
        [
            sys.executable,
            str(HARNESS / "nbt_replay.py"),
            "--trace",
            str(HARNESS / "traces" / "feld_prefetch_then_warm_gentle.replay.json"),
            "--esp",
            ESP,
            "--sg",
            "/dev/sg0",
            "--mode",
            "sg",
            "--settle",
            "5",
            "--out",
            str(out),
        ]
    )
    raw = json.loads(out.read_text())
    rep = analyze(raw)
    Path(str(out).replace(".json", ".summary.json")).write_text(json.dumps(rep, indent=2))
    Path(str(out).replace(".json", ".md")).write_text(to_markdown(rep))
    print(
        "PREFETCH_RERUN",
        rep.get("overall"),
        "stream",
        rep.get("stream_bytes_delta"),
        "under",
        rep.get("underrun_delta"),
        "live",
        rep.get("live_ratio"),
        "pre",
        rep.get("pre_warm_delta"),
        flush=True,
    )
    for v in rep.get("verdicts", []):
        print(" ", v.get("result"), v.get("id"), "-", v.get("detail"), flush=True)

    for uid in ("fav0", "fav1"):
        print(f"===== paced {uid} =====", flush=True)
        print(post("/api/lab/stop"), flush=True)
        time.sleep(1)
        print(post("/api/lab/play", {"uid": uid}), flush=True)
        wait_uid(uid)
        log = Path(f"/tmp/paced-{uid}.txt")
        with log.open("w") as f:
            p = subprocess.run(
                [
                    sys.executable,
                    str(HARNESS / "lab_paced_consume.py"),
                    "--esp",
                    ESP,
                    "--dev",
                    "/dev/sda",
                    "--mode",
                    "paced",
                    "--seconds",
                    "10",
                    "--warmup",
                    "0",
                ],
                stdout=f,
                stderr=subprocess.STDOUT,
                text=True,
            )
        print(log.read_text(), flush=True)
        print("exit", p.returncode, flush=True)


if __name__ == "__main__":
    main()

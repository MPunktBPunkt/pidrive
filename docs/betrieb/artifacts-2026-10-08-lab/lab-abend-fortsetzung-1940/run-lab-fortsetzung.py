#!/usr/bin/env python3
"""Lab-Fortsetzung nach s4: Q10-Sniff, authorized-Probe, Klasse-A Remount×N, Head vs Mid reject."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ESP = os.environ.get("ESP", "http://192.168.178.88")
OUT = Path(__file__).resolve().parent
REPO = Path("/home/martin/projects/pidrive")
SG = "/dev/sg0"
USB_AUTH = Path("/sys/bus/usb/devices/2-3.2/authorized")
BRIDGE = Path("/home/martin/projects/esphub/esp32.pidrive/tools/pump_bridge.py")


def http_json(url: str, method: str = "GET", body: bytes | None = None, timeout: float = 8):
    req = urllib.request.Request(url, data=body, method=method)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        return json.loads(raw) if raw else {}


def status(retries: int = 8, delay: float = 2.0):
    last = None
    for i in range(retries):
        try:
            return http_json(f"{ESP.rstrip('/')}/api/status", timeout=6)
        except Exception as e:
            last = e
            time.sleep(delay)
    raise RuntimeError(f"status failed after {retries}: {last}")


def uptime_key(st: dict) -> tuple:
    m = st.get("msc") or {}
    return (st.get("uptime"), m.get("usbSerial"), m.get("remountGen"), st.get("otgUp"))


def kill_bridge():
    subprocess.run(
        ["pkill", "-f", f"python3 {BRIDGE} --transport tcp --host 192.168.178.88"],
        check=False,
        capture_output=True,
    )
    time.sleep(1.5)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    summary: dict = {"esp": ESP, "blocks": {}}

    # --- L4f: authorized / VBUS ---
    auth = {
        "path": str(USB_AUTH),
        "exists": USB_AUTH.exists(),
        "value": USB_AUTH.read_text().strip() if USB_AUTH.exists() else None,
        "writable": False,
        "write_error": None,
    }
    if USB_AUTH.exists():
        try:
            with open(USB_AUTH, "r+") as f:
                cur = f.read().strip()
                f.seek(0)
                f.write(cur)
            auth["writable"] = True
        except OSError as e:
            auth["write_error"] = f"{type(e).__name__}: {e}"
            # sudo -A often hangs without askpass in this CT — do not block; RO is expected.
            auth["note"] = "PVE/CT: sysfs authorized not writable without host-side uhubctl"
    summary["blocks"]["L4f_authorized"] = auth
    (OUT / "l4f-authorized.json").write_text(json.dumps(auth, indent=2))
    print("L4f authorized", auth)

    # --- Q10 sniff on prior fenster + tonight ---
    reads = list(REPO.glob(
        "docs/betrieb/artifacts-2026-10-08-lab/lab-fenster-*/**/reads.jsonl"
    )) + list(REPO.glob(
        "docs/betrieb/artifacts-2026-10-08-lab/lab-abend-nach-s4-1837/*/reads.jsonl"
    ))
    reads = sorted(set(reads))[:12]
    q10_out = OUT / "q10-sniff.json"
    cmd = [
        sys.executable,
        str(REPO / "tools/lab_q10_read_sniff.py"),
        *[str(p) for p in reads],
        "--esp",
        ESP,
        "--out",
        str(q10_out),
    ]
    r = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True)
    print(r.stdout)
    if r.returncode != 0:
        print(r.stderr, file=sys.stderr)
    summary["blocks"]["Q10"] = {
        "rc": r.returncode,
        "n_files": len(reads),
        "out": str(q10_out),
    }
    if q10_out.exists():
        summary["blocks"]["Q10"]["summary"] = json.loads(q10_out.read_text()).get("summary")

    # --- Klasse-A: stop stream → API remount ×8, uptime must not drop ---
    kill_bridge()
    try:
        http_json(f"{ESP.rstrip('/')}/api/lab/stop", method="POST", body=b"{}", timeout=8)
    except Exception as e:
        print("lab/stop", e)
    time.sleep(1)
    pre = status()
    (OUT / "status-pre.json").write_text(json.dumps(pre, indent=2))
    pre_up = pre.get("uptime")
    drops = 0
    remount_ok = 0
    rows = []
    (OUT / "class-a-remount.jsonl").write_text("")
    for i in range(1, 6):
        before = status()
        b_ser = (before.get("msc") or {}).get("usbSerial")
        b_gen = int((before.get("msc") or {}).get("remountGen") or 0)
        try:
            http_json(f"{ESP.rstrip('/')}/api/lab/remount", method="POST", body=b"{}", timeout=10)
        except Exception as e:
            rows.append({"i": i, "remount_err": f"{type(e).__name__}: {e}"})
            time.sleep(3)
            continue
        time.sleep(3.5)
        after = status()
        a_ser = (after.get("msc") or {}).get("usbSerial")
        a_gen = int((after.get("msc") or {}).get("remountGen") or 0)
        advanced = a_gen > b_gen or a_ser != b_ser
        if advanced:
            remount_ok += 1
        reboot = False
        bu, au = str(before.get("uptime") or ""), str(after.get("uptime") or "")
        if ("h" in bu or "min" in bu) and au.endswith("s") and "min" not in au and "h" not in au:
            reboot = True
            drops += 1
        row = {
            "i": i,
            "before": uptime_key(before),
            "after": uptime_key(after),
            "remount_advanced": advanced,
            "reboot": reboot,
            "ser": a_ser,
        }
        rows.append(row)
        print("remount", row)
        (OUT / "class-a-remount.jsonl").open("a").write(json.dumps(row) + "\n")
    summary["blocks"]["class_a_remount"] = {
        "n": len(rows),
        "drops": drops,
        "remount_advanced": remount_ok,
        "pass": drops == 0 and remount_ok >= 4,
        "pre_uptime": pre_up,
        "post_uptime": status().get("uptime"),
    }

    # --- Head-from-0 vs Mid-file reject (after remount, with short bridge prefill) ---
    kill_bridge()
    br_log = OUT / "bridge-prefill.log"
    br = subprocess.Popen(
        [
            sys.executable,
            str(BRIDGE),
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
        stdout=br_log.open("w"),
        stderr=subprocess.STDOUT,
    )
    time.sleep(12)
    br.terminate()
    try:
        br.wait(timeout=5)
    except subprocess.TimeoutExpired:
        br.kill()
    time.sleep(1.5)

    # mid-file: read fav2 from offset ~64KiB via overlay or SG — use sim GW-like: sg read mid
    # Capture events before/after mid read and after head-from-0 REPLUG-lite
    rej_pre = int((status().get("msc") or {}).get("playRejectCount") or 0)
    # Mid read via lab overlay if available (doesn't need sg dual-client)
    mid_detail = {}
    try:
        # LBA for fav2 body mid ≈ 17489 + 128 sectors (~64KiB)
        http_json(
            f"{ESP.rstrip('/')}/api/lab/overlay_read?off=65536&n=8192",
            timeout=8,
        )
        mid_detail["overlay"] = "ok"
    except Exception as e:
        mid_detail["overlay"] = f"{type(e).__name__}: {e}"
    time.sleep(1)
    ev_mid = http_json(f"{ESP.rstrip('/')}/api/events?n=40")
    (OUT / "events-after-mid.json").write_text(json.dumps(ev_mid, indent=2))
    rej_mid = int((status().get("msc") or {}).get("playRejectCount") or 0)
    codes_mid = [
        e.get("detail")
        for e in (ev_mid.get("events") or [])
        if e.get("code") == "play.reject"
    ][-5:]

    # Head-from-0 REPLUG (sim owns pump)
    kill_bridge()
    rdir = OUT / "replug-48k-head"
    rdir.mkdir(exist_ok=True)
    # martin ∈ disk → /dev/sg0 ohne sudo (sudo -A hängt hier oft ohne Askpass)
    sim = subprocess.run(
        [
            sys.executable,
            str(REPO / "tools/nbt_hu_sim.py"),
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
            "12",
            "--replug-id3-bytes",
            "3300",
            "--replug-bps",
            "6000",
            "--out",
            str(rdir),
        ],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=120,
    )
    (OUT / "replug-48k-head.log").write_text(sim.stdout + "\n" + sim.stderr)
    print(sim.stdout[-800:] if sim.stdout else sim.stderr[-400:])
    report = {}
    if (rdir / "REPORT.json").exists():
        report = json.loads((rdir / "REPORT.json").read_text())
    replug = (report.get("results") or {}).get("REPLUG") or {}
    summary["blocks"]["reject_matrix"] = {
        "rej_pre": rej_pre,
        "rej_after_mid": rej_mid,
        "mid_delta": rej_mid - rej_pre,
        "mid_last_rejects": codes_mid,
        "mid": mid_detail,
        "replug_pass": replug.get("pass"),
        "live_s_at_48k": replug.get("live_s_at_48k"),
        "live_s_at_bps": replug.get("live_s_at_bps"),
        "live_bytes_file": replug.get("live_bytes_file"),
        "identity_ok": replug.get("identity_ok"),
        "ring_full_pre": replug.get("ring_full_pre"),
    }

    # Q10 on fresh REPLUG
    fresh_reads = rdir / "reads.jsonl"
    if fresh_reads.exists():
        subprocess.run(
            [
                sys.executable,
                str(REPO / "tools/lab_q10_read_sniff.py"),
                str(fresh_reads),
                "--esp",
                ESP,
                "--out",
                str(OUT / "q10-fresh-replug.json"),
            ],
            check=False,
        )

    summary["overall"] = {
        "authorized_still_ro": not auth.get("writable"),
        "class_a_remount_pass": summary["blocks"]["class_a_remount"]["pass"],
        "q10_4kib": (summary["blocks"].get("Q10") or {}).get("summary", {}).get("all_q10_4kib"),
        "replug_pass": replug.get("pass"),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary["overall"], indent=2))
    print("OUT", OUT)
    return 0 if summary["blocks"]["class_a_remount"]["pass"] and replug.get("pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())

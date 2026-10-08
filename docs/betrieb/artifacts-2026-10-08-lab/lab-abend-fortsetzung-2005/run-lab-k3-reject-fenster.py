#!/usr/bin/env python3
"""Lab: K3 Name-Override+Remount, SG Mid vs Head Reject, 32k×3 Fenster."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ESP = os.environ.get("ESP", "http://192.168.178.88")
HOST = "192.168.178.88"
OUT = Path(__file__).resolve().parent
REPO = Path("/home/martin/projects/pidrive")
BRIDGE = Path("/home/martin/projects/esphub/esp32.pidrive/tools/pump_bridge.py")
OVERRIDE = Path("/tmp/pidrive-name-overrides-lab2005.json")
SG = "/dev/sg0"
NEW_NAME = "Radio BOB LAB 1008"


def http_json(url: str, method: str = "GET", body: bytes | None = None, timeout: float = 8):
    req = urllib.request.Request(url, data=body, method=method)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        return json.loads(raw) if raw else {}


def status(retries: int = 10) -> dict:
    last = None
    for _ in range(retries):
        try:
            return http_json(f"{ESP.rstrip('/')}/api/status", timeout=6)
        except Exception as e:
            last = e
            time.sleep(2)
    raise RuntimeError(f"status: {last}")


def lab_stop() -> None:
    try:
        http_json(f"{ESP.rstrip('/')}/api/lab/stop", method="POST", body=b"{}", timeout=8)
    except Exception as e:
        print("lab/stop", e)
    time.sleep(1)


def remount() -> dict:
    http_json(f"{ESP.rstrip('/')}/api/lab/remount", method="POST", body=b"{}", timeout=10)
    time.sleep(3)
    return status()


def kill_bridge() -> None:
    subprocess.run(
        ["pkill", "-f", f"python3 {BRIDGE} --transport tcp --host {HOST}"],
        check=False,
        capture_output=True,
    )
    time.sleep(1.5)


def slot_name(st: dict, uid: str) -> str | None:
    for s in st.get("slotMap") or (st.get("msc") or {}).get("slotMap") or []:
        if s.get("uid") == uid:
            return s.get("name")
    # fallback: playing / menu items not always present — scan status text fields
    return None


def fav_names(st: dict) -> dict:
    out = {}
    for s in st.get("slotMap") or (st.get("msc") or {}).get("slotMap") or []:
        if s.get("uid"):
            out[s["uid"]] = s.get("name")
    return out


def start_bridge(extra: list[str], log: Path) -> subprocess.Popen:
    kill_bridge()
    cmd = [
        sys.executable,
        str(BRIDGE),
        "--transport",
        "tcp",
        "--host",
        HOST,
        "--bitrate",
        "48k",
        "--target-bps",
        "6000",
        "--marker",
        "--marker-period",
        "1",
        *extra,
    ]
    return subprocess.Popen(cmd, stdout=log.open("w"), stderr=subprocess.STDOUT)


def wait_name(uid: str, want: str, timeout_s: float = 25.0) -> tuple[bool, str | None, dict]:
    t0 = time.monotonic()
    last = None
    st = {}
    while time.monotonic() - t0 < timeout_s:
        st = status()
        last = slot_name(st, uid) or fav_names(st).get(uid)
        if last == want:
            return True, last, st
        # also accept substring match if menu truncated
        if last and want in last:
            return True, last, st
        time.sleep(1.5)
    return False, last, st


def reject_details(n: int = 60) -> list[str]:
    try:
        ev = http_json(f"{ESP.rstrip('/')}/api/events?n={n}")
    except Exception:
        return []
    return [
        e.get("detail") or ""
        for e in (ev.get("events") or [])
        if e.get("code") == "play.reject"
    ]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    summary: dict = {"blocks": {}}

    # ---------- K3: name override + remount (msc-lock publish) ----------
    lab_stop()
    kill_bridge()
    OVERRIDE.write_text(json.dumps({"fav2": NEW_NAME}, ensure_ascii=False, indent=2) + "\n")
    br = start_bridge(
        ["--msc-lock", "--name-override-file", str(OVERRIDE)],
        OUT / "k3-bridge-override.log",
    )
    time.sleep(6)
    # remount = media re-present (Feld: OTG ab/an)
    lab_stop()
    st1 = remount()
    ok1, name1, st1b = wait_name("fav2", NEW_NAME)
    (OUT / "k3-status-renamed.json").write_text(json.dumps(st1b or st1, indent=2))
    # clear override: frozen msc-lock rejects in-session menu_set → bridge restart + remount
    kill_bridge()
    try:
        br.terminate()
        br.wait(timeout=3)
    except Exception:
        pass
    OVERRIDE.write_text("{}\n")
    lab_stop()
    br2 = start_bridge(
        ["--msc-lock", "--name-override-file", str(OVERRIDE)],
        OUT / "k3-bridge-restore.log",
    )
    time.sleep(5)
    lab_stop()
    remount()
    ok2, name2, st2 = wait_name("fav2", "Radio BOB!", timeout_s=25)
    (OUT / "k3-status-restored.json").write_text(json.dumps(st2, indent=2))
    kill_bridge()
    try:
        br2.terminate()
        br2.wait(timeout=3)
    except Exception:
        pass
    summary["blocks"]["K3"] = {
        "override_file": str(OVERRIDE),
        "want": NEW_NAME,
        "name_after_override": name1,
        "override_ok": ok1,
        "name_after_clear": name2,
        "restore_ok": bool(ok2),
        "note": "restore needs bridge restart+remount; empty file alone blocked by msc-lock freeze",
        "uptime": status().get("uptime"),
        "serial": (status().get("msc") or {}).get("usbSerial"),
        "pass": bool(ok1 and ok2),
    }
    print("K3", summary["blocks"]["K3"])

    # ---------- Mid-file SG vs Head REPLUG (reject matrix) ----------
    lab_stop()
    kill_bridge()
    remount()
    rej0 = int((status().get("msc") or {}).get("playRejectCount") or 0)
    mid_script = OUT / "_mid_read.py"
    mid_script.write_text(
        f"""
import json, sys
sys.path.insert(0, "{REPO / 'tools'}")
from pathlib import Path
from nbt_hu_sim import HuSim, load_profile, prep_lab, snap_retry
esp = "{ESP}"
out = Path("{OUT / 'mid-sg'}")
out.mkdir(exist_ok=True)
profile = load_profile(Path("{REPO / 'tools/profiles/nbt_evo_2026-10-06.json'}"))
hu = HuSim("{SG}", profile)
pump = None
try:
    pump = prep_lab(esp, "{HOST}", None, remount=False)
    hu.open()
    hu.refresh_slots(esp)
    # mid-file fav2: 64 KiB into body (past ID3/head)
    n = 0
    for off in range(65536, 65536 + 32 * 4096, 4096):
        n += len(hu.read_n("fav2", off, 4096))
    post = snap_retry(esp)
    (out / "status.json").write_text(json.dumps(post, indent=2))
    print(json.dumps({{"bytes": n, "rej": (post.get("msc") or {{}}).get("playRejectCount")}}))
finally:
    hu.close()
    if pump:
        try: pump.close()
        except Exception: pass
"""
    )
    mid = subprocess.run(
        [sys.executable, str(mid_script)],
        capture_output=True,
        text=True,
        timeout=90,
    )
    (OUT / "mid-sg.log").write_text(mid.stdout + "\n" + mid.stderr)
    time.sleep(1)
    rej1 = int((status().get("msc") or {}).get("playRejectCount") or 0)
    dets = reject_details(80)
    mid_hits = [d for d in dets if "not_from_head" in d or "plug_window" in d]
    (OUT / "events-after-mid.json").write_text(
        json.dumps(http_json(f"{ESP.rstrip('/')}/api/events?n=80"), indent=2)
    )

    # Head path: bridge prefill + REPLUG
    kill_bridge()
    br = start_bridge([], OUT / "head-bridge.log")
    time.sleep(12)
    kill_bridge()
    try:
        br.terminate()
        br.wait(timeout=3)
    except Exception:
        pass
    head_out = OUT / "head-replug"
    head = subprocess.run(
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
            str(head_out),
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    (OUT / "head-replug.log").write_text(head.stdout + "\n" + head.stderr)
    replug = {}
    if (head_out / "REPORT.json").exists():
        replug = (json.loads((head_out / "REPORT.json").read_text()).get("results") or {}).get(
            "REPLUG"
        ) or {}
    summary["blocks"]["reject_matrix"] = {
        "rej_pre": rej0,
        "rej_after_mid": rej1,
        "mid_delta": rej1 - rej0,
        "mid_reject_samples": mid_hits[-6:],
        "mid_saw_not_from_head": any("not_from_head" in d for d in mid_hits),
        "mid_sg_rc": mid.returncode,
        "mid_sg_out": (mid.stdout or "")[-200:],
        "head_replug_pass": bool(replug.get("pass")),
        "live_s_at_bps": replug.get("live_s_at_bps"),
        "live_bytes_file": replug.get("live_bytes_file"),
        "pass": bool(replug.get("pass"))
        and (rej1 > rej0 or any("not_from_head" in d for d in mid_hits)),
    }
    print("reject_matrix", summary["blocks"]["reject_matrix"])

    # ---------- 32k ×3 fenster ----------
    fen_out = OUT / "fenster-32k-x3"
    fen = subprocess.run(
        [
            sys.executable,
            str(REPO / "tools/lab_fenster_bitrate.py"),
            "--bitrate",
            "32k",
            "--rounds",
            "3",
            "--esp",
            ESP,
            "--out",
            str(fen_out),
        ],
        capture_output=True,
        text=True,
        timeout=400,
    )
    (OUT / "fenster-32k-x3.log").write_text(fen.stdout + "\n" + fen.stderr)
    print(fen.stdout[-1200:] if fen.stdout else fen.stderr[-400:])
    fen_sum = {}
    if (fen_out / "summary.json").exists():
        fen_sum = json.loads((fen_out / "summary.json").read_text())
    summary["blocks"]["fenster_32k_x3"] = {
        "pass": fen_sum.get("pass"),
        "pass_n": fen_sum.get("pass_n"),
        "results": fen_sum.get("results"),
        "rc": fen.returncode,
    }

    summary["overall"] = {
        "k3_override": summary["blocks"]["K3"]["pass"],
        "reject_matrix": summary["blocks"]["reject_matrix"]["pass"],
        "fenster_32k_x3": bool(fen_sum.get("pass")),
        "uptime": status().get("uptime"),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2))
    print("OVERALL", json.dumps(summary["overall"], indent=2))
    print("OUT", OUT)
    ok = all(summary["overall"].values()) if isinstance(summary["overall"]["uptime"], str) else False
    # uptime is str — compute pass without it
    passed = (
        summary["overall"]["k3_override"]
        and summary["overall"]["reject_matrix"]
        and summary["overall"]["fenster_32k_x3"]
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

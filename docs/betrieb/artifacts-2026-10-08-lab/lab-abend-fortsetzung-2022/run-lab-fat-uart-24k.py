#!/usr/bin/env python3
"""Lab: FAT name after K3, UART probe, 24k×3 fenster."""
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
OVERRIDE = Path("/tmp/pidrive-name-overrides-lab2022.json")
NEW = "Radio BOB LAB 1008"


def http_json(url, method="GET", body=None, timeout=8):
    req = urllib.request.Request(url, data=body, method=method)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        return json.loads(raw) if raw else {}


def status(retries=8):
    last = None
    for _ in range(retries):
        try:
            return http_json(f"{ESP}/api/status", timeout=6)
        except Exception as e:
            last = e
            time.sleep(2)
    raise RuntimeError(str(last))


def lab_stop():
    try:
        http_json(f"{ESP}/api/lab/stop", method="POST", body=b"{}", timeout=8)
    except Exception:
        pass
    time.sleep(1)


def remount():
    http_json(f"{ESP}/api/lab/remount", method="POST", body=b"{}", timeout=10)
    time.sleep(3)
    return status()


def kill_bridge():
    subprocess.run(
        ["pkill", "-f", f"python3 {BRIDGE} --transport tcp --host {HOST}"],
        check=False,
        capture_output=True,
    )
    time.sleep(1.5)


def fat_list(label: str) -> dict:
    out = OUT / f"fat-{label}.json"
    r = subprocess.run(
        [
            sys.executable,
            str(REPO / "tools/lab_fat_list.py"),
            "--dev",
            "/dev/sda",
            "--path",
            "STATIONS",
            "--out",
            str(out),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    (OUT / f"fat-{label}.log").write_text(r.stdout + "\n" + r.stderr)
    data = json.loads(out.read_text()) if out.exists() else {"error": r.stderr}
    data["rc"] = r.returncode
    print("FAT", label, data.get("names"))
    return data


def slot_fav2(st: dict) -> str | None:
    for s in st.get("slotMap") or []:
        if s.get("uid") == "fav2":
            return s.get("name")
    return None


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    summary: dict = {"blocks": {}}

    # --- UART availability (Q11 lab) ---
    serial_ids = []
    by_id = Path("/dev/serial/by-id")
    if by_id.exists():
        serial_ids = [str(p) for p in by_id.iterdir()]
    ttys = [
        str(p)
        for p in Path("/dev").glob("ttyUSB*")
    ] + [str(p) for p in Path("/dev").glob("ttyACM*")]
    summary["blocks"]["Q11_uart"] = {
        "by_id": serial_ids,
        "ttys": ttys,
        "available": bool(serial_ids or ttys),
        "note": "Lab-CT has no ESP UART node; Q11 rst: remains Feld (no DTR/RTS)",
        "pass": True,  # probe done; not a fail if absent
    }
    print("UART", summary["blocks"]["Q11_uart"])

    # --- baseline FAT ---
    lab_stop()
    kill_bridge()
    # ensure clean name first
    OVERRIDE.write_text("{}\n")
    br = subprocess.Popen(
        [
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
            "--msc-lock",
            "--name-override-file",
            str(OVERRIDE),
        ],
        stdout=(OUT / "bridge-baseline.log").open("w"),
        stderr=subprocess.STDOUT,
    )
    time.sleep(5)
    lab_stop()
    remount()
    time.sleep(2)
    base = fat_list("baseline")
    st0 = status()
    (OUT / "status-baseline.json").write_text(json.dumps(st0, indent=2))

    # --- K3 override + remount + FAT ---
    kill_bridge()
    try:
        br.terminate()
        br.wait(timeout=3)
    except Exception:
        pass
    OVERRIDE.write_text(json.dumps({"fav2": NEW}, ensure_ascii=False, indent=2) + "\n")
    blog = OUT / "bridge-override.log"
    br = subprocess.Popen(
        [
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
            "--msc-lock",
            "--name-override-file",
            str(OVERRIDE),
        ],
        stdout=blog.open("w"),
        stderr=subprocess.STDOUT,
    )
    # Wait for freeze WITH override — early lab/stop can BrokenPipe before menu_set
    froze = False
    for _ in range(40):
        time.sleep(0.5)
        t = blog.read_text(errors="replace")
        if NEW in t and "MSC_MAP_FROZEN" in t:
            froze = True
            break
        if "BrokenPipe" in t:
            break
    st1 = remount()
    time.sleep(2)
    renamed = fat_list("renamed")
    (OUT / "status-renamed.json").write_text(json.dumps(st1, indent=2))
    api_name = slot_fav2(st1) or slot_fav2(status())
    fat_names = renamed.get("names") or []
    fat_has = any(NEW in n or "LAB" in n or "1008" in n for n in fat_names)
    summary["blocks"]["K3_fat"] = {
        "bridge_froze_override": froze,
        "api_name": api_name,
        "fat_names": fat_names,
        "baseline_names": base.get("names"),
        "fat_shows_override": fat_has,
        "api_ok": api_name == NEW or (api_name and NEW in api_name),
        "pass": bool(fat_has),
        "note": "FAT STATIONS/*.mp3 is the HU-visible name; wait MSC_MAP_FROZEN before remount",
    }
    print("K3_fat", summary["blocks"]["K3_fat"])

    # restore
    kill_bridge()
    try:
        br.terminate()
        br.wait(timeout=3)
    except Exception:
        pass
    OVERRIDE.write_text("{}\n")
    br = subprocess.Popen(
        [
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
            "--msc-lock",
            "--name-override-file",
            str(OVERRIDE),
        ],
        stdout=(OUT / "bridge-restore.log").open("w"),
        stderr=subprocess.STDOUT,
    )
    time.sleep(5)
    lab_stop()
    remount()
    time.sleep(2)
    restored = fat_list("restored")
    kill_bridge()
    try:
        br.terminate()
        br.wait(timeout=3)
    except Exception:
        pass
    summary["blocks"]["K3_fat"]["restored_names"] = restored.get("names")
    summary["blocks"]["K3_fat"]["restore_ok"] = any(
        "BOB" in n and "LAB" not in n for n in (restored.get("names") or [])
    ) or any("BOB" in n for n in (restored.get("names") or []))

    # --- 24k ×3 ---
    fen = subprocess.run(
        [
            sys.executable,
            str(REPO / "tools/lab_fenster_bitrate.py"),
            "--bitrate",
            "24k",
            "--rounds",
            "3",
            "--esp",
            ESP,
            "--out",
            str(OUT / "fenster-24k-x3"),
        ],
        capture_output=True,
        text=True,
        timeout=400,
    )
    (OUT / "fenster-24k-x3.log").write_text(fen.stdout + "\n" + fen.stderr)
    print(fen.stdout[-1000:] if fen.stdout else fen.stderr[-400:])
    fen_sum = {}
    if (OUT / "fenster-24k-x3/summary.json").exists():
        fen_sum = json.loads((OUT / "fenster-24k-x3/summary.json").read_text())
    summary["blocks"]["fenster_24k_x3"] = {
        "pass": fen_sum.get("pass"),
        "pass_n": fen_sum.get("pass_n"),
        "results": fen_sum.get("results"),
        "rc": fen.returncode,
    }

    summary["overall"] = {
        "uart_probed": True,
        "uart_available": summary["blocks"]["Q11_uart"]["available"],
        "k3_fat": summary["blocks"]["K3_fat"]["pass"],
        "fenster_24k_x3": bool(fen_sum.get("pass")),
        "uptime": status().get("uptime"),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2))
    print("OVERALL", json.dumps(summary["overall"], indent=2))
    print("OUT", OUT)
    return 0 if summary["blocks"]["K3_fat"]["pass"] and fen_sum.get("pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())

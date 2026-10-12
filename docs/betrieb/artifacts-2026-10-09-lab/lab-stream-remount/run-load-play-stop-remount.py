#!/usr/bin/env python3
"""Load arm: bridge peer up → lab/play (stream) → lab/stop → remount ×N.

FW skips remount while stream_->active() (msc.remount_skip). Closest lab
analogue to 'OTG under load': remount immediately after live stream with
pump TCP still connected.
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ESP = os.environ.get("ESP", "http://192.168.178.88").rstrip("/")
ESP_HOST = os.environ.get("ESP_HOST", "192.168.178.88")
OUT = Path(__file__).resolve().parent
BRIDGE = Path("/home/martin/projects/esphub/esp32.pidrive/tools/pump_bridge.py")
MY_IP = os.environ.get("MY_IP", "192.168.178.187")


def http_json(url: str, method: str = "GET", body: bytes | None = None, timeout: float = 20):
    req = urllib.request.Request(url, data=body, method=method)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        return json.loads(raw) if raw else {}


def status(retries: int = 10, delay: float = 1.5) -> dict:
    last = None
    for _ in range(retries):
        try:
            return http_json(f"{ESP}/api/status", timeout=6)
        except Exception as e:
            last = e
            time.sleep(delay)
    raise RuntimeError(f"status failed: {last}")


def snap(st: dict | None = None) -> dict:
    st = st or status()
    m = st.get("msc") or {}
    s = m.get("stream") or {}
    return {
        "t": time.strftime("%H:%M:%S"),
        "uptime": st.get("uptime"),
        "serial": m.get("usbSerial"),
        "remountGen": m.get("remountGen"),
        "peer": st.get("pumpTcpPeer") or "",
        "freeHeap": st.get("freeHeap"),
        "stream_active": s.get("active"),
        "absEnd": s.get("absEnd"),
        "underruns": s.get("underruns"),
        "ring": s.get("size"),
        "phase": m.get("phase"),
    }


def parse_uptime_seconds(u: str) -> float | None:
    if not u:
        return None
    total = 0.0
    found = False
    num = ""
    unit = ""
    i = 0
    u = str(u).strip()
    while i < len(u):
        c = u[i]
        if c.isdigit() or c == ".":
            num += c
            i += 1
            continue
        if c.isalpha():
            unit += c
            i += 1
            while i < len(u) and u[i].isalpha():
                unit += u[i]
                i += 1
            if num:
                v = float(num)
                if unit.startswith("h"):
                    total += v * 3600
                elif unit.startswith("min"):
                    total += v * 60
                elif unit.startswith("s"):
                    total += v
                found = True
                num = ""
                unit = ""
            continue
        i += 1
    return total if found else None


def is_soft_reboot(before: dict, after: dict) -> bool:
    bu = parse_uptime_seconds(str(before.get("uptime") or ""))
    au = parse_uptime_seconds(str(after.get("uptime") or ""))
    if bu is not None and au is not None and bu >= 180 and au < 90:
        return True
    b, a = str(before.get("uptime") or ""), str(after.get("uptime") or "")
    if ("h" in b or "min" in b) and a.endswith("s") and "min" not in a and "h" not in a:
        return True
    return False


def kill_bridge() -> None:
    try:
        out = subprocess.check_output(["pgrep", "-af", "pump_bridge.py"], text=True)
    except subprocess.CalledProcessError:
        out = ""
    for line in out.splitlines():
        if ESP_HOST not in line or "pgrep" in line:
            continue
        try:
            os.kill(int(line.split(None, 1)[0]), signal.SIGTERM)
        except (ValueError, ProcessLookupError):
            pass
    time.sleep(2)


def start_bridge(bitrate: str, bps: int, log: Path) -> subprocess.Popen:
    kill_bridge()
    fh = open(log, "w", encoding="utf-8")
    proc = subprocess.Popen(
        [
            sys.executable,
            str(BRIDGE),
            "--transport",
            "tcp",
            "--host",
            ESP_HOST,
            "--bitrate",
            bitrate,
            "--target-bps",
            str(bps),
            "--marker",
            "--marker-period",
            "1",
        ],
        stdout=fh,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    deadline = time.time() + 45
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"bridge died: {log}")
        peer = status().get("pumpTcpPeer") or ""
        if peer == MY_IP:
            return proc
        time.sleep(1)
    raise RuntimeError("no peer")


def cycle(arm: str, n: int, bitrate: str, bps: int) -> dict:
    proc = start_bridge(bitrate, bps, OUT / f"bridge-{arm}.log")
    rows = []
    drops = 0
    remount_ok = 0
    stream_ok = 0
    heap_min = None
    jsonl = OUT / f"{arm}.jsonl"
    jsonl.write_text("")
    try:
        for i in range(1, n + 1):
            before = snap()
            play = http_json(
                f"{ESP}/api/lab/play",
                method="POST",
                body=b'{"uid":"fav2"}',
                timeout=12,
            )
            time.sleep(4)
            mid = snap()
            if mid.get("stream_active") and int(mid.get("absEnd") or 0) > 0:
                stream_ok += 1
            stop = http_json(f"{ESP}/api/lab/stop", method="POST", body=b"{}", timeout=12)
            time.sleep(1.5)
            pre_rm = snap()
            remount_err = None
            try:
                http_json(f"{ESP}/api/lab/remount", method="POST", body=b"{}", timeout=20)
            except Exception as e:
                remount_err = f"{type(e).__name__}: {e}"
            time.sleep(3.5)
            after = snap()
            advanced = int(after.get("remountGen") or 0) > int(before.get("remountGen") or 0) or (
                after.get("serial") and after.get("serial") != before.get("serial")
            )
            if advanced:
                remount_ok += 1
            reboot = is_soft_reboot(before, after)
            if reboot:
                drops += 1
            fh = after.get("freeHeap")
            if isinstance(fh, int):
                heap_min = fh if heap_min is None else min(heap_min, fh)
            row = {
                "i": i,
                "play": play,
                "stop": stop,
                "before": before,
                "mid_stream": mid,
                "pre_remount": pre_rm,
                "after": after,
                "remount_advanced": advanced,
                "reboot": reboot,
                "remount_err": remount_err,
            }
            rows.append(row)
            with jsonl.open("a") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            print(
                f"{arm} #{i}: reboot={reboot} adv={advanced} "
                f"stream_abs={mid.get('absEnd')} "
                f"up {before.get('uptime')}→{after.get('uptime')} "
                f"ser {before.get('serial')}→{after.get('serial')} "
                f"peer={after.get('peer')!r}"
            )
    finally:
        if proc.poll() is None:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                proc.wait(timeout=5)
            except Exception:
                pass
        kill_bridge()
    return {
        "arm": arm,
        "n": n,
        "bitrate": bitrate,
        "target_bps": bps,
        "remount_ok": remount_ok,
        "stream_ok": stream_ok,
        "soft_resets": drops,
        "freeHeap_min": heap_min,
        "pass": drops == 0 and remount_ok >= max(1, (n * 7) // 10) and stream_ok >= max(1, (n * 7) // 10),
        "rows": rows,
    }


def main() -> int:
    summary = {"esp": ESP, "host": MY_IP, "method": "play→stop→remount peer-up"}
    print("== load48k play-stop-remount x10 ==")
    a48 = cycle("load48k-psr", 10, "48k", 6000)
    (OUT / "load48k-psr-summary.json").write_text(
        json.dumps(a48, indent=2, ensure_ascii=False) + "\n"
    )
    summary["load48k-psr"] = {k: v for k, v in a48.items() if k != "rows"}

    print("== load32k play-stop-remount x5 ==")
    a32 = cycle("load32k-psr", 5, "32k", 4000)
    (OUT / "load32k-psr-summary.json").write_text(
        json.dumps(a32, indent=2, ensure_ascii=False) + "\n"
    )
    summary["load32k-psr"] = {k: v for k, v in a32.items() if k != "rows"}

    summary["soft_resets_total"] = summary["load48k-psr"]["soft_resets"] + summary[
        "load32k-psr"
    ]["soft_resets"]
    summary["all_pass"] = summary["load48k-psr"]["pass"] and summary["load32k-psr"]["pass"]
    summary["final"] = snap()
    (OUT / "psr-summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if summary["all_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

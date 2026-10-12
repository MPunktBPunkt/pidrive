#!/usr/bin/env python3
"""Lab: API remount under idle vs live pump stream — soft-reset rate.

Does NOT stop the stream before remount (unlike prior Klasse-A series).
Physical VBUS / UART brownout is out of scope on this host.
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
BRIDGE = Path(
    os.environ.get(
        "BRIDGE",
        "/home/martin/projects/esphub/esp32.pidrive/tools/pump_bridge.py",
    )
)
MY_IP = os.environ.get("MY_IP", "192.168.178.187")


def http_json(url: str, method: str = "GET", body: bytes | None = None, timeout: float = 10):
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
        "plugged": m.get("plugged"),
        "otgUp": st.get("otgUp"),
        "peer": st.get("pumpTcpPeer") or "",
        "pumpTcpUp": st.get("pumpTcpUp"),
        "freeHeap": st.get("freeHeap"),
        "stream_active": s.get("active"),
        "absEnd": s.get("absEnd"),
        "hostAbs": s.get("hostAbsCursor"),
        "underruns": s.get("underruns"),
        "ring": s.get("size"),
    }


def parse_uptime_seconds(u: str) -> float | None:
    """Rough seconds from ESP uptime strings like '20h 56min', '3min 12s', '16s'."""
    if not u:
        return None
    u = str(u).strip()
    total = 0.0
    found = False
    num = ""
    unit = ""
    i = 0
    while i < len(u):
        c = u[i]
        if c.isdigit() or c == ".":
            num += c
            i += 1
            continue
        if c.isalpha():
            unit += c
            i += 1
            # peek rest of unit
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
                else:
                    return None
                found = True
                num = ""
                unit = ""
            continue
        i += 1
    return total if found else None


def is_soft_reboot(before: dict, after: dict) -> bool:
    """Detect reboot: uptime collapses, or serial jumps backwards / large drop in seconds."""
    bu = parse_uptime_seconds(str(before.get("uptime") or ""))
    au = parse_uptime_seconds(str(after.get("uptime") or ""))
    if bu is not None and au is not None:
        # after remount, uptime should keep growing (or stay ~same within sleep)
        if au + 30 < bu * 0.5 and au < 120:
            return True
        if bu >= 180 and au < 90:
            return True
    # string heuristic from prior runners
    b, a = str(before.get("uptime") or ""), str(after.get("uptime") or "")
    if ("h" in b or "min" in b) and a.endswith("s") and "min" not in a and "h" not in a:
        return True
    return False


def kill_bridge() -> None:
    """Kill only pump_bridge PIDs for this ESP (avoid pkill -f matching our cmdline)."""
    try:
        out = subprocess.check_output(["pgrep", "-af", "pump_bridge.py"], text=True)
    except subprocess.CalledProcessError:
        out = ""
    for line in out.splitlines():
        if ESP_HOST not in line:
            continue
        if "pgrep" in line or "run-stream-remount" in line:
            continue
        try:
            pid = int(line.split(None, 1)[0])
        except ValueError:
            continue
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    time.sleep(2)
    # second pass SIGKILL
    try:
        out = subprocess.check_output(["pgrep", "-af", "pump_bridge.py"], text=True)
    except subprocess.CalledProcessError:
        out = ""
    for line in out.splitlines():
        if ESP_HOST not in line or "pgrep" in line:
            continue
        try:
            pid = int(line.split(None, 1)[0])
            os.kill(pid, signal.SIGKILL)
        except (ValueError, ProcessLookupError):
            pass
    time.sleep(1)


def lab_play(uid: str = "fav2") -> dict:
    return http_json(
        f"{ESP}/api/lab/play",
        method="POST",
        body=json.dumps({"uid": uid}).encode(),
        timeout=12,
    )


def start_bridge(bitrate: str, target_bps: int, log_path: Path) -> subprocess.Popen:
    kill_bridge()
    log = open(log_path, "w", encoding="utf-8")
    cmd = [
        sys.executable,
        str(BRIDGE),
        "--transport",
        "tcp",
        "--host",
        ESP_HOST,
        "--bitrate",
        bitrate,
        "--target-bps",
        str(target_bps),
        "--marker",
        "--marker-period",
        "1",
    ]
    proc = subprocess.Popen(
        cmd,
        stdout=log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    # wait for peer
    deadline = time.time() + 45
    peer_ok = False
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"bridge died early; see {log_path}")
        st = status()
        peer = st.get("pumpTcpPeer") or ""
        if peer == MY_IP or peer.endswith(MY_IP):
            peer_ok = True
            break
        time.sleep(1)
    if not peer_ok:
        raise RuntimeError(f"bridge peer not {MY_IP} within 45s; last={snap()}")
    # activate MSC stream (mirrors field play) so absEnd advances under load
    try:
        print("lab/play", lab_play("fav2"))
    except Exception as e:
        print("lab/play warn", e)
    deadline = time.time() + 20
    last = snap()
    a0 = int(last.get("absEnd") or 0)
    while time.time() < deadline:
        time.sleep(2)
        last = snap()
        a1 = int(last.get("absEnd") or 0)
        if last.get("stream_active") or a1 > a0 + 2000:
            print("stream ready", last)
            return proc
    print("WARN: stream not clearly active; continuing", last)
    return proc


def remount_cycle(n: int, arm: str, require_peer: bool | None) -> dict:
    rows = []
    drops = 0
    remount_ok = 0
    heap_min = None
    jsonl = OUT / f"{arm}.jsonl"
    jsonl.write_text("")
    for i in range(1, n + 1):
        before = snap()
        if require_peer is True and not before.get("peer"):
            rows.append({"i": i, "error": "peer_missing_before", "before": before})
            break
        if require_peer is False and before.get("peer"):
            # foreign peer — abort idle arm
            rows.append({"i": i, "error": "peer_present_on_idle", "before": before})
            break
        remount_err = None
        try:
            http_json(f"{ESP}/api/lab/remount", method="POST", body=b"{}", timeout=20)
        except Exception as e:
            remount_err = f"{type(e).__name__}: {e}"
            # Remount often still applies; HTTP can time out under MSC burst.
            time.sleep(2)
        time.sleep(3.5)
        after = snap()
        # if stream was required, re-arm play after remount (field: tip again)
        if require_peer is True:
            try:
                lab_play("fav2")
                time.sleep(1.5)
                after = snap()
            except Exception:
                pass
        b_gen = int(before.get("remountGen") or 0)
        a_gen = int(after.get("remountGen") or 0)
        advanced = a_gen > b_gen or (
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
            "before": before,
            "after": after,
            "remount_advanced": advanced,
            "reboot": reboot,
            "remount_err": remount_err,
            "stream_active_after": after.get("stream_active"),
            "absEnd_after": after.get("absEnd"),
        }
        rows.append(row)
        with jsonl.open("a") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(
            f"{arm} #{i}: reboot={reboot} adv={advanced} "
            f"up {before.get('uptime')}→{after.get('uptime')} "
            f"ser {before.get('serial')}→{after.get('serial')} "
            f"peer={after.get('peer')!r} absEnd={after.get('absEnd')} "
            f"active={after.get('stream_active')} err={remount_err}"
        )
    return {
        "arm": arm,
        "n": n,
        "remount_ok": remount_ok,
        "soft_resets": drops,
        "freeHeap_min": heap_min,
        # Soft-reset is the gate; HTTP timeouts with advanced serial still count as remount OK.
        "pass": drops == 0 and remount_ok >= max(1, (n * 7) // 10),
        "rows": rows,
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    summary: dict = {
        "esp": ESP,
        "host": MY_IP,
        "fw_freeze": "0.4.46-dev",
        "note": "API remount only; authorized/VBUS RO; no UART",
        "arms": {},
    }

    print("== baseline ==")
    kill_bridge()
    try:
        http_json(f"{ESP}/api/lab/stop", method="POST", body=b"{}", timeout=8)
    except Exception as e:
        print("lab/stop (ok if none)", e)
    time.sleep(2)
    base = snap()
    (OUT / "baseline.json").write_text(json.dumps(base, indent=2, ensure_ascii=False) + "\n")
    print(base)
    summary["baseline"] = base

    skip_idle = os.environ.get("SKIP_IDLE", "") in ("1", "true", "yes")
    only = os.environ.get("ONLY_ARMS", "idle,load48k,load32k")
    want = {x.strip() for x in only.split(",") if x.strip()}

    # --- Idle arm ---
    if "idle" in want and not skip_idle:
        print("== idle remount x10 ==")
        for _ in range(15):
            st = snap()
            if not st.get("peer"):
                break
            kill_bridge()
            time.sleep(2)
        idle = remount_cycle(10, "idle", require_peer=False)
        summary["arms"]["idle"] = {k: v for k, v in idle.items() if k != "rows"}
        (OUT / "idle-summary.json").write_text(
            json.dumps(idle, indent=2, ensure_ascii=False) + "\n"
        )
    elif (OUT / "idle-summary.json").exists():
        prev = json.loads((OUT / "idle-summary.json").read_text())
        summary["arms"]["idle"] = {k: v for k, v in prev.items() if k != "rows"}
        summary["arms"]["idle"]["reused"] = True

    # --- Load 48k ---
    if "load48k" in want:
        print("== load 48k remount x10 (stream ON) ==")
        proc48 = None
        try:
            proc48 = start_bridge("48k", 6000, OUT / "bridge-48k-stream.log")
            time.sleep(3)
            load48 = remount_cycle(10, "load48k", require_peer=True)
        finally:
            if proc48 and proc48.poll() is None:
                try:
                    os.killpg(os.getpgid(proc48.pid), signal.SIGTERM)
                    proc48.wait(timeout=5)
                except Exception:
                    try:
                        os.killpg(os.getpgid(proc48.pid), signal.SIGKILL)
                    except Exception:
                        pass
            kill_bridge()
        summary["arms"]["load48k"] = {k: v for k, v in load48.items() if k != "rows"}
        (OUT / "load48k-summary.json").write_text(
            json.dumps(load48, indent=2, ensure_ascii=False) + "\n"
        )

    # --- Load 32k ---
    if "load32k" in want:
        print("== load 32k remount x5 (stream ON) ==")
        proc32 = None
        try:
            proc32 = start_bridge("32k", 4000, OUT / "bridge-32k-stream.log")
            time.sleep(3)
            load32 = remount_cycle(5, "load32k", require_peer=True)
        finally:
            if proc32 and proc32.poll() is None:
                try:
                    os.killpg(os.getpgid(proc32.pid), signal.SIGTERM)
                    proc32.wait(timeout=5)
                except Exception:
                    try:
                        os.killpg(os.getpgid(proc32.pid), signal.SIGKILL)
                    except Exception:
                        pass
            kill_bridge()
        summary["arms"]["load32k"] = {k: v for k, v in load32.items() if k != "rows"}
        (OUT / "load32k-summary.json").write_text(
            json.dumps(load32, indent=2, ensure_ascii=False) + "\n"
        )

    summary["final"] = snap()
    arm_keys = [a for a in ("idle", "load48k", "load32k") if a in summary["arms"]]
    summary["all_pass"] = bool(arm_keys) and all(
        summary["arms"][a].get("pass") for a in arm_keys
    )
    summary["soft_resets_total"] = sum(
        summary["arms"][a].get("soft_resets", 0) for a in arm_keys
    )
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    print("== summary ==")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if summary["all_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

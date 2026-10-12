#!/usr/bin/env python3
"""Lab spike: station Play/Stop submenu — arm → prefill → head-read Live (no OTG).

  python3 docs/betrieb/artifacts-2026-10-11-lab/lab-station-arm-play/run.py

Requires: ESP .88 OTG on host (/dev/sda), no foreign pump peer, bridge with
--station-submenu fav2 (patched pump_bridge.py).
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
DEV = os.environ.get("MSC_DEV", "/dev/sda")
UID = os.environ.get("ARM_UID", "fav2")
BITRATE = os.environ.get("BITRATE", "32k")
TARGET_BPS = int(os.environ.get("TARGET_BPS", "4000"))
PREFILL_S = float(os.environ.get("PREFILL_S", "14"))
LIVE_KIB = int(os.environ.get("LIVE_KIB", "64"))


def http_json(url: str, method: str = "GET", body: bytes | None = None, timeout: float = 12):
    req = urllib.request.Request(url, data=body, method=method)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        return json.loads(raw) if raw else {}


def status(retries: int = 8, delay: float = 0.8) -> dict:
    last = None
    for _ in range(retries):
        try:
            return http_json(f"{ESP}/api/status", timeout=5)
        except Exception as e:
            last = e
            time.sleep(delay)
    raise RuntimeError(f"status failed: {last}")


def snap(label: str = "") -> dict:
    st = status()
    m = st.get("msc") or {}
    s = m.get("stream") or {}
    slots = {str(x.get("uid")): x for x in (m.get("slotMap") or []) if isinstance(x, dict)}
    return {
        "t": time.strftime("%H:%M:%S"),
        "label": label,
        "uptime": st.get("uptime"),
        "serial": m.get("usbSerial"),
        "peer": st.get("pumpTcpPeer") or "",
        "playingUid": st.get("playingUid") or "",
        "stream_active": bool(s.get("active")),
        "absEnd": int(s.get("absEnd") or 0),
        "ring": int(s.get("size") or 0),
        "underruns": int(s.get("underruns") or 0),
        "id3Len": int(s.get("id3Len") or 0),
        "slotMap": [
            {
                "uid": x.get("uid"),
                "name": x.get("name"),
                "lba0": x.get("lba0"),
                "bytes": x.get("bytes"),
                "kind": x.get("kind"),
            }
            for x in (m.get("slotMap") or [])
        ],
        "slots": slots,
    }


def dd_bytes(dev: str, lba: int, nbytes: int) -> bytes:
    """Read nbytes from MSC starting at LBA (512-byte sectors)."""
    sectors = max(1, (nbytes + 511) // 512)
    cmd = [
        "dd",
        f"if={dev}",
        "bs=512",
        f"skip={lba}",
        f"count={sectors}",
        "status=none",
        "iflag=direct",
    ]
    try:
        return subprocess.check_output(cmd)
    except subprocess.CalledProcessError:
        # fallback without O_DIRECT
        cmd = [
            "dd",
            f"if={dev}",
            "bs=512",
            f"skip={lba}",
            f"count={sectors}",
            "status=none",
        ]
        return subprocess.check_output(cmd)


def count_nonzero(data: bytes) -> int:
    return sum(1 for b in data if b != 0)


def main() -> int:
    series: list[dict] = []
    bridge_log = OUT / "bridge.log"
    dump_path = OUT / "live-head.bin"

    peer = (status().get("pumpTcpPeer") or "").strip()
    my_ips = subprocess.check_output(["hostname", "-I"], text=True).split()
    if peer and peer not in my_ips:
        print(f"ABBRUCH: ESP-Peer {peer} ≠ dieser Host {my_ips}", file=sys.stderr)
        return 2

    pidfile = Path("/tmp/lab-station-arm-play-bridge.pid")
    if pidfile.exists():
        try:
            old = int(pidfile.read_text().strip())
            os.kill(old, signal.SIGTERM)
            time.sleep(0.5)
        except (ValueError, OSError):
            pass

    # Lab: no msc-lock so Play/Live/Stop map can replace a frozen classic 3-station seal.
    # Field: seal once with --station-submenu (OTG already in).
    try:
        http_json(f"{ESP}/api/lab/remount", method="POST", body=b"{}", timeout=8)
        print("remount ok", flush=True)
        time.sleep(2)
    except Exception as e:
        print(f"remount skip: {e}", flush=True)

    cmd = [
        sys.executable,
        "-u",
        str(BRIDGE),
        "--transport",
        "tcp",
        "--host",
        ESP_HOST,
        "--bitrate",
        BITRATE,
        "--target-bps",
        str(TARGET_BPS),
        "--marker",
        "--marker-period",
        "1",
        "--no-msc-lock",
        "--station-submenu",
        UID,
    ]
    print("== bridge ==", " ".join(cmd), flush=True)
    blog = bridge_log.open("w", encoding="utf-8")
    proc = subprocess.Popen(cmd, stdout=blog, stderr=subprocess.STDOUT)
    pidfile.write_text(str(proc.pid), encoding="utf-8")
    try:
        # wait menu freeze / slotMap
        arm_lba = None
        live_lba = None
        stop_lba = None
        for i in range(40):
            time.sleep(0.5)
            s = snap(f"wait_menu_{i}")
            series.append(s)
            slots = s.get("slots") or {}
            arm = slots.get(f"pump:arm:{UID}") or {}
            live = slots.get(UID) or {}
            stop = slots.get("pump:stop") or {}
            if arm.get("lba0") is not None and live.get("lba0") is not None:
                arm_lba = int(arm["lba0"])
                live_lba = int(live["lba0"])
                if stop.get("lba0") is not None:
                    stop_lba = int(stop["lba0"])
                print(
                    f"menu ok names={[x.get('name') for x in s['slotMap']]} "
                    f"arm_lba={arm_lba} live_lba={live_lba}",
                    flush=True,
                )
                break
        else:
            print("ABBRUCH: Play/Live slots nicht in slotMap", file=sys.stderr)
            (OUT / "series.json").write_text(json.dumps(series, indent=2), encoding="utf-8")
            return 3

        serial0 = series[-1]["serial"]
        up0 = series[-1]["uptime"]

        # Lab: SoftAP lab/play emits the same play_uid the HU would after tipping Play.
        # (Host MSC tip fights indexSettled/plug_window right after remount — separate probe.)
        print(f"== lab/play arm uid=pump:arm:{UID} ==", flush=True)
        try:
            arm_resp = http_json(
                f"{ESP}/api/lab/play",
                method="POST",
                body=json.dumps({"uid": f"pump:arm:{UID}"}).encode(),
                timeout=8,
            )
            print("arm_resp", arm_resp, flush=True)
        except Exception as e:
            print(f"ABBRUCH lab/play: {e}", file=sys.stderr)
            return 6
        time.sleep(1.2)
        series.append(snap("after_arm_play"))

        print(f"== prefill wait {PREFILL_S}s ==", flush=True)
        t_end = time.time() + PREFILL_S
        while time.time() < t_end:
            time.sleep(1.0)
            s = snap("prefill")
            series.append(s)
            print(
                f"  active={s['stream_active']} absEnd={s['absEnd']} ring={s['ring']} "
                f"uid={s['playingUid']!r}",
                flush=True,
            )
            if s["stream_active"] and s["absEnd"] >= max(40_000, s["ring"] or 40_000):
                break

        pre = snap("pre_live_read")
        series.append(pre)
        if not pre["stream_active"] or pre["absEnd"] < 8_000:
            print("FAIL: Stream nach Arm/Prefill nicht bereit", flush=True)
            (OUT / "series.json").write_text(json.dumps(series, indent=2), encoding="utf-8")
            return 4

        print(f"== tip Live head-read {LIVE_KIB} KiB lba={live_lba} ==", flush=True)
        live = dd_bytes(DEV, live_lba, LIVE_KIB * 1024)
        dump_path.write_bytes(live)
        post = snap("after_live_read")
        series.append(post)

        # crude live detection: ID3/APIC or non-trivial entropy vs silence pad
        nz = count_nonzero(live)
        # silence frames still have sync words — look for ID3 or high nonzero ratio
        has_id3 = live[:3] == b"ID3"
        live_like = has_id3 or nz > len(live) * 0.02

        print(f"== tip Stop lba={stop_lba} ==", flush=True)
        if stop_lba is not None:
            for _ in range(2):
                dd_bytes(DEV, stop_lba, 4096)
                time.sleep(0.05)
            time.sleep(0.8)
        series.append(snap("after_stop"))

        blog.flush()
        arm_lines = []
        keep_lines = []
        starts = 0
        try:
            text = bridge_log.read_text(encoding="utf-8", errors="replace")
            for line in text.splitlines():
                if "ARM " in line or "arm skip" in line:
                    arm_lines.append(line)
                if "live tip keep" in line:
                    keep_lines.append(line)
                if "audio_start sent" in line:
                    starts += 1
        except OSError:
            pass

        serial1 = series[-1]["serial"]
        summary = {
            "esp": ESP,
            "uid": UID,
            "bitrate": BITRATE,
            "target_bps": TARGET_BPS,
            "serial0": serial0,
            "serial1": serial1,
            "uptime0": up0,
            "uptime1": series[-1]["uptime"],
            "soft_reset": serial0 != serial1,
            "prefill_absEnd": pre["absEnd"],
            "prefill_ring": pre["ring"],
            "stream_active_pre": pre["stream_active"],
            "dump_bytes": len(live),
            "dump_nonzero": nz,
            "dump_has_id3": has_id3,
            "live_like": live_like,
            "bridge_arm_lines": arm_lines[-5:],
            "bridge_keep_lines": keep_lines[-5:],
            "audio_start_count": starts,
            "slot_names": [x.get("name") for x in pre.get("slotMap") or []],
            "verdict": (
                "PASS"
                if (
                    pre["stream_active"]
                    and live_like
                    and serial0 == serial1
                    and starts >= 1
                )
                else "FAIL"
            ),
        }
        (OUT / "series.json").write_text(json.dumps(series, indent=2), encoding="utf-8")
        (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(json.dumps(summary, indent=2), flush=True)
        return 0 if summary["verdict"] == "PASS" else 5
    finally:
        proc.send_signal(signal.SIGINT)
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()
        blog.close()
        try:
            pidfile.unlink(missing_ok=True)
        except OSError:
            pass


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Lab: simulate HU-like sequential body burst across the live window.

1) Pump-feed fav0 MP3 (seed off)
2) Sequential dd in ~32KiB steps from absBase → absEnd (HU cold-body style)
3) Extra hit near LBA 761 (fileOff≈348160) — typically outside a late window
4) Log hostAbsCursor / liveBytes / underruns after each step

Example:
  sg disk -c 'python3 tools/m3_lab_av_burst_sim.py --dev /dev/sda'
"""
from __future__ import annotations

import argparse
import json
import socket
import struct
import subprocess
import time
import urllib.request
from pathlib import Path

FRAME_MAX = 512


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


def dd(dev: str, lba: int, sectors: int) -> None:
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


def wait_dev(dev: str, timeout: float = 20.0) -> None:
    t0 = time.time()
    while time.time() - t0 < timeout:
        if Path(dev).exists():
            try:
                dd(dev, 0, 1)
                return
            except subprocess.CalledProcessError:
                pass
        time.sleep(0.5)
    raise SystemExit(f"dev not ready: {dev}")


class PumpTcp:
    def __init__(self, host: str, port: int = 9090):
        self.s = socket.create_connection((host, port), timeout=8)
        self.s.settimeout(0.35)

    def close(self) -> None:
        try:
            self.s.close()
        except OSError:
            pass

    def send_json(self, obj: dict) -> None:
        self.s.sendall((json.dumps(obj, separators=(",", ":")) + "\n").encode())

    def send_bin(self, kind: int, payload: bytes, gap_s: float = 0.002) -> None:
        off = 0
        while off < len(payload):
            chunk = payload[off : off + FRAME_MAX]
            hdr = bytes((0x01, kind, len(chunk) & 0xFF, (len(chunk) >> 8) & 0xFF))
            self.s.sendall(hdr + chunk)
            off += len(chunk)
            time.sleep(gap_s)

    def drain(self, seconds: float = 1.0) -> None:
        t_end = time.time() + seconds
        while time.time() < t_end:
            try:
                if not self.s.recv(4096):
                    break
            except socket.timeout:
                continue


def id3(title: str) -> bytes:
    enc = b"\x00" + title.encode("latin-1", errors="replace")[:30]
    frame = b"TIT2" + struct.pack(">I", len(enc)) + b"\x00\x00" + enc
    size = len(frame)
    header = b"ID3\x03\x00\x00" + bytes(
        [(size >> 21) & 0x7F, (size >> 14) & 0x7F, (size >> 7) & 0x7F, size & 0x7F]
    )
    return header + frame


def snap(esp: str) -> dict:
    st = http_json(f"{esp}/api/status")
    m = st["msc"]
    s = m.get("stream") or {}
    sb = int(m.get("streamBytes") or 0)
    ud = int(s.get("underruns") or 0)
    return {
        "active": s.get("active"),
        "absBase": int(s.get("absBase") or 0),
        "absEnd": int(s.get("absEnd") or 0),
        "size": s.get("size"),
        "hostAbs": int(s.get("hostAbsCursor") or 0),
        "streamBytes": sb,
        "underruns": ud,
        "live": sb - ud,
        "host_in_window": False,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--esp", default="http://192.168.178.88")
    ap.add_argument("--esp-ip", default="192.168.178.88")
    ap.add_argument("--dev", default="/dev/sda")
    ap.add_argument("--mp3", default="docs/betrieb/artifacts-2026-10-03-m3/mp3/L1.mp3")
    ap.add_argument("--uid", default="fav0")
    ap.add_argument("--feed-kb", type=int, default=220)
    ap.add_argument("--step-kib", type=int, default=32)
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    esp = args.esp.rstrip("/")
    mp3 = Path(args.mp3)
    stamp = time.strftime("%H%M")
    day = time.strftime("%Y-%m-%d")
    out = Path(args.out) if args.out else Path(
        f"docs/betrieb/artifacts-{day}-lab/lab88-av-burst-{stamp}"
    )
    out.mkdir(parents=True, exist_ok=True)

    http_json(f"{esp}/api/lab/body_seed", method="POST", body=b'{"slot":0,"tag":"off"}')
    http_json(f"{esp}/api/lab/stop", method="POST", body=b"{}")
    time.sleep(0.25)

    pump = PumpTcp(args.esp_ip)
    steps: list[dict] = []
    try:
        pump.send_json({"t": "hello", "ver": 1})
        pump.drain(1.2)
        pump.send_json({"t": "audio_stop"})
        time.sleep(0.1)
        pump.send_json(
            {
                "t": "menu_set",
                "rev": int(time.time()) % 100000,
                "page": 0,
                "items": [
                    {"uid": "fav0", "name": "AV Rock", "kind": "station"},
                    {"uid": "fav1", "name": "AV Bayern", "kind": "station"},
                    {"uid": "fav2", "name": "AV BOB", "kind": "station"},
                    {"uid": "pump:page_next", "name": "Menue", "kind": "action"},
                ],
            }
        )
        pump.drain(1.8)
        time.sleep(1.0)
        wait_dev(args.dev)
        st = http_json(f"{esp}/api/status")
        (out / "status-00-menu.json").write_text(json.dumps(st, indent=2))
        lba0 = int(next(s for s in st["msc"]["slotMap"] if s["uid"] == args.uid)["lba0"])

        pump.send_json(
            {
                "t": "audio_start",
                "uid": args.uid,
                "codec": "mp3",
                "br": "48k",
                "cSrc": "burst",
                "cPath": "burst",
                "cTry": "burst",
            }
        )
        pump.drain(0.7)
        pump.send_bin(0x56, id3("AV-Burst"), gap_s=0.05)
        time.sleep(0.2)
        blob = mp3.read_bytes()
        feed_n = min(len(blob), args.feed_kb * 1024)
        print(f"feed {feed_n}", flush=True)
        pump.send_bin(0x55, blob[:feed_n], gap_s=0.002)
        time.sleep(0.7)

        s0 = snap(esp)
        (out / "status-01-armed.json").write_text(json.dumps(http_json(f"{esp}/api/status"), indent=2))
        base, end = s0["absBase"], s0["absEnd"]
        print(f"window {base}..{end}", flush=True)
        if end <= base + 8192:
            raise SystemExit("window too small")

        step = args.step_kib * 1024
        off = (base // 512) * 512
        i = 0
        while off + step <= end:
            lba = lba0 + off // 512
            dd(args.dev, lba, step // 512)
            time.sleep(0.05)
            s = snap(esp)
            s["host_in_window"] = base <= s["hostAbs"] < end
            row = {"i": i, "kind": "in_window", "file_off": off, "lba": lba, **s}
            steps.append(row)
            print(
                f"IN[{i}] off={off} lba={lba} hostAbs={s['hostAbs']} "
                f"live={s['live']} und={s['underruns']} inWin={s['host_in_window']}",
                flush=True,
            )
            off += step
            i += 1

        # classic HU prefill zone ~ LBA 761 → fileOff 348160
        prefill_off = 348160
        prefill_lba = lba0 + prefill_off // 512
        before = snap(esp)
        dd(args.dev, prefill_lba, 64)
        time.sleep(0.05)
        after = snap(esp)
        after["host_in_window"] = base <= after["hostAbs"] < end
        steps.append(
            {
                "i": i,
                "kind": "prefill_lba761",
                "file_off": prefill_off,
                "lba": prefill_lba,
                "before": before,
                **after,
                "underrun_delta": after["underruns"] - before["underruns"],
                "live_delta": after["live"] - before["live"],
            }
        )
        print(
            f"PREFILL761 lba={prefill_lba} undΔ={after['underruns']-before['underruns']} "
            f"liveΔ={after['live']-before['live']} hostAbs={after['hostAbs']}",
            flush=True,
        )

        pump.send_json({"t": "audio_stop"})
    finally:
        pump.close()

    try:
        (out / "status-02-final.json").write_text(json.dumps(http_json(f"{esp}/api/status"), indent=2))
    except Exception as e:
        (out / "status-02-final.err.txt").write_text(str(e))

    in_steps = [s for s in steps if s.get("kind") == "in_window"]
    pref = next((s for s in steps if s.get("kind") == "prefill_lba761"), None)
    host_moved = False
    if len(in_steps) >= 2:
        host_moved = in_steps[-1]["hostAbs"] > in_steps[0]["hostAbs"]
    elif len(in_steps) == 1:
        # single chunk still advances cursor into/through window
        host_moved = in_steps[0]["hostAbs"] >= in_steps[0]["file_off"]
    live_up = False
    if len(in_steps) >= 2:
        live_up = in_steps[-1]["live"] > in_steps[0]["live"]
    elif len(in_steps) == 1:
        live_up = in_steps[0]["live"] > 0 and in_steps[0]["underruns"] == 0
    pref_und = bool(pref and pref.get("underrun_delta", 0) > 0)
    ok = bool(in_steps) and host_moved and live_up and pref_und
    report = {
        "ok": ok,
        "window": [base, end] if steps else None,
        "in_steps": len(in_steps),
        "host_moved": host_moved,
        "live_up_across_burst": live_up,
        "prefill761_underrun": pref_und,
        "prefill": (
            {k: pref.get(k) for k in ("lba", "file_off", "underrun_delta", "live_delta", "hostAbs")}
            if pref
            else None
        ),
        "first_last": {
            "first": in_steps[0] if in_steps else None,
            "last": in_steps[-1] if in_steps else None,
        },
        "steps": steps,
    }
    (out / "REPORT.json").write_text(json.dumps(report, indent=2))
    (out / "EAR.txt").write_text(
        f"lab AV burst-sim {'PASS' if ok else 'FAIL'} {time.strftime('%Y-%m-%dT%H:%M:%S')}\n"
        f"host_moved={host_moved} live_up={live_up} prefill761_und={pref_und}\nOUT={out}\n"
    )
    print(f"OUT={out} ok={ok}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

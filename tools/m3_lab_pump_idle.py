#!/usr/bin/env python3
"""Lab: idle pump throughput baseline (no host MSC reads).

Claude/Mistral consensus after eb91d4e: measure true pump path rate via
absEnd growth and pumped_bytes over a fixed window — no burst_s confusion.

Example:
  python3 tools/m3_lab_pump_idle.py --duration-s 10 --frame-max 512 --gap-s 0.0002
  python3 tools/m3_lab_pump_idle.py --duration-s 10 --frame-max 2048 --gap-s 0
"""
from __future__ import annotations

import argparse
import json
import socket
import struct
import time
import urllib.request
from pathlib import Path

KIND_AUDIO = 0x55
KIND_ID3 = 0x56


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


class PumpTcp:
    def __init__(self, host: str, port: int = 9090, frame_max: int = 512, batch_frames: int = 1):
        self.s = socket.create_connection((host, port), timeout=8)
        self.s.settimeout(2.0)
        try:
            self.s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except OSError:
            pass
        self.frame_max = max(1, min(frame_max, 65535))
        self.batch_frames = max(1, batch_frames)

    def close(self) -> None:
        try:
            self.s.close()
        except OSError:
            pass

    def send_json(self, obj: dict) -> None:
        self.s.sendall((json.dumps(obj, separators=(",", ":")) + "\n").encode())

    def drain(self, seconds: float = 0.5) -> None:
        t_end = time.time() + seconds
        while time.time() < t_end:
            try:
                chunk = self.s.recv(65536)
                if not chunk:
                    break
            except (socket.timeout, ConnectionResetError, BrokenPipeError, OSError):
                continue

    def send_bin(self, kind: int, payload: bytes, gap_s: float = 0.0) -> int:
        """Return audio payload bytes sent. Optionally batch N frames per sendall."""
        sent = 0
        off = 0
        pending: list[bytes] = []
        frames_in_batch = 0
        while off < len(payload):
            chunk = payload[off : off + self.frame_max]
            hdr = bytes((0x01, kind, len(chunk) & 0xFF, (len(chunk) >> 8) & 0xFF))
            pending.append(hdr + chunk)
            frames_in_batch += 1
            sent += len(chunk)
            off += len(chunk)
            if frames_in_batch >= self.batch_frames or off >= len(payload):
                self.s.sendall(b"".join(pending))
                pending = []
                frames_in_batch = 0
                if gap_s > 0:
                    time.sleep(gap_s)
        return sent


def id3(title: str) -> bytes:
    enc = b"\x00" + title.encode("latin-1", errors="replace")[:30]
    frame = b"TIT2" + struct.pack(">I", len(enc)) + b"\x00\x00" + enc
    size = len(frame)
    return b"ID3\x03\x00\x00" + bytes(
        [(size >> 21) & 0x7F, (size >> 14) & 0x7F, (size >> 7) & 0x7F, size & 0x7F]
    ) + frame


def stream_snap(esp: str) -> dict:
    st = http_json(f"{esp}/api/status", timeout=8)
    m = st.get("msc") or {}
    s = m.get("stream") or st.get("stream") or {}
    return {
        "ts": time.time(),
        "absBase": int(s.get("absBase") or 0),
        "absEnd": int(s.get("absEnd") or 0),
        "size": int(s.get("size") or 0),
        "active": bool(s.get("active")),
        "underruns": int(s.get("underruns") or 0),
        "streamBytes": int(m.get("streamBytes") or 0),
    }


def soft_rst(esp: str) -> None:
    try:
        http_json(f"{esp}/api/restart", method="POST", body=b"{}", timeout=3)
    except Exception:
        pass
    for _ in range(40):
        try:
            if http_json(f"{esp}/api/status").get("ok"):
                break
        except Exception:
            pass
        time.sleep(1)
    time.sleep(2)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--esp", default="http://192.168.178.88")
    ap.add_argument("--esp-ip", default="192.168.178.88")
    ap.add_argument("--uid", default="fav1")
    ap.add_argument("--mp3", default="docs/betrieb/artifacts-2026-10-03-m3/mp3/L1.mp3")
    ap.add_argument("--out", default="")
    ap.add_argument("--duration-s", type=float, default=10.0)
    ap.add_argument("--chunk", type=int, default=4096, help="Audio bytes per send_bin call")
    ap.add_argument("--frame-max", type=int, default=512, help="Pump TCP frame payload max")
    ap.add_argument("--gap-s", type=float, default=0.0002, help="Sleep between frame batches (0=none)")
    ap.add_argument("--batch-frames", type=int, default=1, help="Frames per sendall()")
    ap.add_argument("--soft-rst", action="store_true")
    ap.add_argument("--label", default="")
    args = ap.parse_args()

    esp = args.esp.rstrip("/")
    stamp = time.strftime("%H%M%S")
    day = time.strftime("%Y-%m-%d")
    out = Path(args.out) if args.out else Path(
        f"docs/betrieb/artifacts-{day}-lab/lab88-pump-idle-{stamp}"
    )
    out.mkdir(parents=True, exist_ok=True)
    mp3 = Path(args.mp3).read_bytes()

    if args.soft_rst:
        print("== soft-rst ==", flush=True)
        soft_rst(esp)

    try:
        http_json(f"{esp}/api/lab/stop", method="POST", body=b"{}")
    except Exception:
        pass

    pump = PumpTcp(args.esp_ip, frame_max=args.frame_max, batch_frames=args.batch_frames)
    try:
        pump.send_json({"t": "hello", "ver": 1})
        pump.drain(0.6)
        try:
            pump.send_json({"t": "audio_stop"})
        except (BrokenPipeError, OSError):
            pump.close()
            pump = PumpTcp(args.esp_ip, frame_max=args.frame_max, batch_frames=args.batch_frames)
            pump.send_json({"t": "hello", "ver": 1})
            pump.drain(0.6)
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
                ],
            }
        )
        pump.drain(1.0)
        pump.send_json(
            {
                "t": "audio_start",
                "uid": args.uid,
                "codec": "mp3",
                "br": "48k",
                "cSrc": "lab",
                "cPath": "idle",
                "cTry": "idle",
            }
        )
        pump.drain(0.3)
        pump.send_bin(KIND_ID3, id3("IdlePump"), gap_s=0.02)
        time.sleep(0.2)

        s0 = stream_snap(esp)
        print(
            f"== idle pump {args.duration_s}s chunk={args.chunk} frame={args.frame_max} "
            f"gap={args.gap_s} batch={args.batch_frames} ==",
            flush=True,
        )
        print(f"  start absEnd={s0['absEnd']} size={s0['size']}", flush=True)

        pumped = 0
        off = 0
        t0 = time.time()
        t_end = t0 + args.duration_s
        loops = 0
        while time.time() < t_end:
            n = min(args.chunk, len(mp3) - off)
            if n <= 0:
                off = 0
                n = min(args.chunk, len(mp3))
            pumped += pump.send_bin(KIND_AUDIO, mp3[off : off + n], gap_s=args.gap_s)
            off = (off + n) % max(1, len(mp3))
            loops += 1
        wall = time.time() - t0
        time.sleep(0.15)
        s1 = stream_snap(esp)
    finally:
        try:
            pump.send_json({"t": "audio_stop"})
        except Exception:
            pass
        pump.close()

    abs_delta = max(0, s1["absEnd"] - s0["absEnd"])
    report = {
        "label": args.label
        or f"idle chunk={args.chunk} frame={args.frame_max} gap={args.gap_s} batch={args.batch_frames}",
        "config": {
            "duration_s": args.duration_s,
            "chunk": args.chunk,
            "frame_max": args.frame_max,
            "gap_s": args.gap_s,
            "batch_frames": args.batch_frames,
        },
        "wall_s": wall,
        "loops": loops,
        "pumped_bytes": pumped,
        "pumped_bps": pumped / wall if wall else 0,
        "absEnd0": s0["absEnd"],
        "absEnd1": s1["absEnd"],
        "abs_delta": abs_delta,
        "abs_bps": abs_delta / wall if wall else 0,
        "size0": s0["size"],
        "size1": s1["size"],
        "start": s0,
        "end": s1,
    }
    (out / "REPORT.json").write_text(json.dumps(report, indent=2))
    md = [
        "# Lab Pump Idle",
        "",
        f"**Label:** `{report['label']}`",
        f"- wall={wall:.2f}s pumped={pumped} ({report['pumped_bps']:.0f} B/s)",
        f"- absEnd Δ={abs_delta} ({report['abs_bps']:.0f} B/s)",
        f"- frame_max={args.frame_max} gap={args.gap_s} chunk={args.chunk} batch={args.batch_frames}",
        "",
    ]
    (out / "GESAMTBERICHT-PUMP-IDLE.md").write_text("\n".join(md))
    print(f"OUT={out}", flush=True)
    print(
        json.dumps(
            {
                "pumped_bps": round(report["pumped_bps"]),
                "abs_bps": round(report["abs_bps"]),
                "pumped": pumped,
                "abs_delta": abs_delta,
                "wall_s": round(wall, 3),
                "size1": s1["size"],
            },
            indent=2,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Lab AV follow-up: MPEG inside live window vs silence/underrun outside.

Negative control for the cursor/window hypothesis:
  - inside absBase..absEnd → MPEG sync / non-silence, liveBytes rise
  - below absBase and/or above absEnd → silence-like and/or underruns rise

Also: multi-point samples + optional ffmpeg decode smoke on inside blob.

Example:
  sg disk -c 'python3 tools/m3_lab_av_window_bounds.py --dev /dev/sda'
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


def dd_bytes(dev: str, lba: int, sectors: int) -> bytes:
    return subprocess.check_output(
        [
            "dd",
            f"if={dev}",
            "bs=512",
            f"skip={lba}",
            f"count={sectors}",
            "iflag=direct",
            "status=none",
        ],
        stderr=subprocess.DEVNULL,
    )


def wait_dev(dev: str, timeout: float = 20.0) -> None:
    t0 = time.time()
    while time.time() - t0 < timeout:
        if Path(dev).exists():
            try:
                dd_bytes(dev, 0, 1)
                return
            except subprocess.CalledProcessError:
                pass
        time.sleep(0.5)
    raise SystemExit(f"dev not ready: {dev}")


def mpeg_syncs(blob: bytes, limit: int = 12) -> list[int]:
    hits = []
    for i in range(max(0, len(blob) - 1)):
        if blob[i] == 0xFF and (blob[i + 1] & 0xE0) == 0xE0:
            hits.append(i)
            if len(hits) >= limit:
                break
    return hits


def silence_ratio(blob: bytes) -> float:
    n = min(len(blob), 4096)
    if n == 0:
        return 0.0
    return sum(1 for b in blob[:n] if b == 0xFF) / n


class PumpTcp:
    def __init__(self, host: str, port: int = 9090):
        self.s = socket.create_connection((host, port), timeout=8)
        self.s.settimeout(0.35)
        self.buf = b""

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
                chunk = self.s.recv(4096)
            except socket.timeout:
                continue
            if not chunk:
                break
            self.buf += chunk


def id3(title: str) -> bytes:
    enc = b"\x00" + title.encode("latin-1", errors="replace")[:30]
    frame = b"TIT2" + struct.pack(">I", len(enc)) + b"\x00\x00" + enc
    size = len(frame)
    header = b"ID3\x03\x00\x00" + bytes(
        [(size >> 21) & 0x7F, (size >> 14) & 0x7F, (size >> 7) & 0x7F, size & 0x7F]
    )
    return header + frame


def live_bytes(m: dict, s: dict) -> int:
    return int(m.get("streamBytes") or 0) - int(s.get("underruns") or 0)


def sample(dev: str, lba0: int, file_off: int, sectors: int, label: str, out: Path) -> dict:
    lba = lba0 + file_off // 512
    blob = dd_bytes(dev, lba, sectors)
    path = out / f"sample-{label}-off{file_off}.bin"
    path.write_bytes(blob)
    syncs = mpeg_syncs(blob)
    return {
        "label": label,
        "file_off": file_off,
        "lba": lba,
        "syncs": syncs,
        "sync_n": len(syncs),
        "id3": blob[:3] == b"ID3",
        "ff_ratio": round(silence_ratio(blob), 3),
        "prefix_hex": blob[:16].hex(),
        "path": str(path.name),
    }


def ffmpeg_smoke(blob_path: Path, out: Path) -> dict:
    wav = out / "decode-smoke.wav"
    log = out / "decode-smoke.log"
    try:
        r = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-nostats",
                "-y",
                "-i",
                str(blob_path),
                "-t",
                "1",
                "-f",
                "wav",
                str(wav),
            ],
            capture_output=True,
            text=True,
            timeout=20,
        )
        log.write_text((r.stderr or "")[-4000:])
        ok = r.returncode == 0 and wav.exists() and wav.stat().st_size > 44
        return {"ok": ok, "rc": r.returncode, "wav_bytes": wav.stat().st_size if wav.exists() else 0}
    except FileNotFoundError:
        return {"ok": False, "rc": -1, "error": "ffmpeg missing"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "rc": -2, "error": "ffmpeg timeout"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--esp", default="http://192.168.178.88")
    ap.add_argument("--esp-ip", default="192.168.178.88")
    ap.add_argument("--dev", default="/dev/sda")
    ap.add_argument("--mp3", default="docs/betrieb/artifacts-2026-10-03-m3/mp3/L1.mp3")
    ap.add_argument("--uid", default="fav0")
    ap.add_argument("--feed-kb", type=int, default=200)
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    esp = args.esp.rstrip("/")
    mp3_path = Path(args.mp3)
    if not mp3_path.is_file():
        raise SystemExit(f"missing mp3: {mp3_path}")

    stamp = time.strftime("%H%M")
    day = time.strftime("%Y-%m-%d")
    out = Path(args.out) if args.out else Path(
        f"docs/betrieb/artifacts-{day}-lab/lab88-av-window-{stamp}"
    )
    out.mkdir(parents=True, exist_ok=True)
    report: dict = {"ok": False, "inside": [], "outside": [], "metrics": {}}

    http_json(f"{esp}/api/lab/body_seed", method="POST", body=b'{"slot":0,"tag":"off"}')
    http_json(f"{esp}/api/lab/stop", method="POST", body=b"{}")
    time.sleep(0.3)

    pump = PumpTcp(args.esp_ip)
    try:
        pump.send_json({"t": "hello", "ver": 1})
        pump.drain(1.5)
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
        pump.drain(2.0)
        time.sleep(1.0)
        wait_dev(args.dev)

        st = http_json(f"{esp}/api/status")
        (out / "status-00-menu.json").write_text(json.dumps(st, indent=2))
        slot = next(s for s in st["msc"]["slotMap"] if s.get("uid") == args.uid)
        lba0 = int(slot["lba0"])

        pump.send_json(
            {
                "t": "audio_start",
                "uid": args.uid,
                "codec": "mp3",
                "br": "48k",
                "cSrc": "av-win",
                "cPath": "av-win",
                "cTry": "av-win",
            }
        )
        pump.drain(0.8)
        pump.send_bin(0x56, id3("AV-Window"), gap_s=0.05)
        time.sleep(0.2)
        feed_n = min(len(mp3_path.read_bytes()), args.feed_kb * 1024)
        print(f"feed {feed_n} B", flush=True)
        pump.send_bin(0x55, mp3_path.read_bytes()[:feed_n], gap_s=0.002)
        time.sleep(0.8)

        st1 = http_json(f"{esp}/api/status")
        (out / "status-01-armed.json").write_text(json.dumps(st1, indent=2))
        s = st1["msc"].get("stream") or {}
        abs_base = int(s.get("absBase") or 0)
        abs_end = int(s.get("absEnd") or 0)
        print(f"window {abs_base}..{abs_end} size={s.get('size')} active={s.get('active')}", flush=True)
        if abs_end <= abs_base + 16384:
            raise SystemExit("live window too small")

        # metrics before outside hammer
        m0 = st1["msc"]
        s0 = m0.get("stream") or {}
        before = {
            "streamBytes": m0.get("streamBytes"),
            "underruns": s0.get("underruns"),
            "live": live_bytes(m0, s0),
        }

        # inside: three points
        span = abs_end - abs_base
        inside_offs = [
            abs_base + (span * 1) // 5,
            abs_base + (span * 2) // 5,
            abs_base + (span * 3) // 5,
        ]
        inside_offs = [(o // 512) * 512 for o in inside_offs]
        for i, off in enumerate(inside_offs):
            row = sample(args.dev, lba0, off, 24, f"in{i}", out)
            report["inside"].append(row)
            print("IN ", row, flush=True)

        st_in = http_json(f"{esp}/api/status")
        after_in = {
            "streamBytes": st_in["msc"].get("streamBytes"),
            "underruns": (st_in["msc"].get("stream") or {}).get("underruns"),
            "live": live_bytes(st_in["msc"], st_in["msc"].get("stream") or {}),
        }

        # outside: below base and above end (clamped into slot)
        slot_bytes = (int(slot["lba1"]) - lba0 + 1) * 512
        below = max(0, abs_base - 64 * 1024)
        below = (below // 512) * 512
        above = min(slot_bytes - 16 * 512, abs_end + 64 * 1024)
        above = (above // 512) * 512
        for label, off in (("below", below), ("above", above)):
            if off >= abs_base and off < abs_end:
                print(f"skip {label} still inside", flush=True)
                continue
            row = sample(args.dev, lba0, off, 24, label, out)
            report["outside"].append(row)
            print("OUT", row, flush=True)

        st_out = http_json(f"{esp}/api/status")
        (out / "status-02-after-samples.json").write_text(json.dumps(st_out, indent=2))
        after_out = {
            "streamBytes": st_out["msc"].get("streamBytes"),
            "underruns": (st_out["msc"].get("stream") or {}).get("underruns"),
            "live": live_bytes(st_out["msc"], st_out["msc"].get("stream") or {}),
        }
        report["metrics"] = {
            "abs": [abs_base, abs_end],
            "before": before,
            "after_inside": after_in,
            "after_outside": after_out,
            "underrun_delta_outside": int(after_out["underruns"] or 0) - int(after_in["underruns"] or 0),
            "live_delta_inside": int(after_in["live"] or 0) - int(before["live"] or 0),
        }

        # decoder smoke on best inside sample
        best = max(report["inside"], key=lambda r: r["sync_n"])
        decode = ffmpeg_smoke(out / best["path"], out)
        report["decode_smoke"] = {"sample": best["path"], **decode}
        print("DECODE", report["decode_smoke"], flush=True)

        pump.send_json({"t": "audio_stop"})
    finally:
        pump.close()

    inside_ok = all(r["sync_n"] >= 1 or r["id3"] for r in report["inside"]) and len(report["inside"]) >= 2
    # outside: expect fewer syncs OR high FF silence ratio OR underrun growth
    outside_ok = False
    if report["outside"]:
        weak = [
            r
            for r in report["outside"]
            if r["sync_n"] == 0 or r["ff_ratio"] >= 0.8 or (not r["id3"] and r["sync_n"] < 2)
        ]
        und_up = report["metrics"].get("underrun_delta_outside", 0) > 0
        outside_ok = bool(weak) or und_up
    report["ok"] = inside_ok and outside_ok
    report["verdict"] = {
        "inside_mpeg_like": inside_ok,
        "outside_contrast": outside_ok,
        "note": "Supports window hypothesis in lab; not HU field proof.",
    }
    (out / "REPORT.json").write_text(json.dumps(report, indent=2))
    (out / "EAR.txt").write_text(
        f"lab AV window-bounds {'PASS' if report['ok'] else 'FAIL'} {time.strftime('%Y-%m-%dT%H:%M:%S')}\n"
        f"inside_ok={inside_ok} outside_ok={outside_ok} decode={report.get('decode_smoke')}\n"
        f"metrics={report['metrics']}\nOUT={out}\n"
    )
    print(f"OUT={out} ok={report['ok']} inside={inside_ok} outside={outside_ok}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

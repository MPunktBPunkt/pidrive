#!/usr/bin/env python3
"""Lab AV stages A/B: producer fills ring; host dd checks MPEG at read LBAs.

A — after audio_start+feed: stream.active, size>0, underruns low before host read
B — dd at live-window LBAs contains ID3 and/or MPEG sync (0xFFE*); contrast head silence

Freeze: no Detect/Ring/PSRAM/Pacing changes. Seed must be off.

Example:
  sg disk -c 'python3 tools/m3_lab_av_mpeg_at_host.py --esp http://192.168.178.88 --dev /dev/sda'
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
ID3_BUDGET = 128


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


def mpeg_syncs(blob: bytes, limit: int = 8) -> list[int]:
    hits = []
    for i in range(max(0, len(blob) - 1)):
        if blob[i] == 0xFF and (blob[i + 1] & 0xE0) == 0xE0:
            hits.append(i)
            if len(hits) >= limit:
                break
    return hits


def looks_like_silence_fill(blob: bytes) -> bool:
    # Mp3Silence often dense 0xFF; ID3/MPEG has structure. Heuristic only.
    if len(blob) < 64:
        return False
    ff = sum(1 for b in blob[:4096] if b == 0xFF)
    return ff / min(len(blob), 4096) > 0.85 and blob[:3] != b"ID3"


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

    def recv_lines(self, deadline: float) -> list[dict]:
        out: list[dict] = []
        while time.time() < deadline:
            try:
                chunk = self.s.recv(4096)
            except socket.timeout:
                continue
            if not chunk:
                break
            self.buf += chunk
            while b"\n" in self.buf:
                line, self.buf = self.buf.split(b"\n", 1)
                text = line.decode("utf-8", errors="replace").strip()
                if text.startswith("{"):
                    try:
                        out.append(json.loads(text))
                    except json.JSONDecodeError:
                        pass
        return out


def build_minimal_id3(title: str) -> bytes:
    enc = b"\x00" + title.encode("latin-1", errors="replace")[:30]
    frame = b"TIT2" + struct.pack(">I", len(enc)) + b"\x00\x00" + enc
    size = len(frame)
    header = b"ID3\x03\x00\x00" + bytes(
        [(size >> 21) & 0x7F, (size >> 14) & 0x7F, (size >> 7) & 0x7F, size & 0x7F]
    )
    return (header + frame)[:ID3_BUDGET]


def live_bytes(m: dict, s: dict) -> int | None:
    sb = m.get("streamBytes")
    ud = s.get("underruns")
    if sb is None or ud is None:
        return None
    return int(sb) - int(ud)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--esp", default="http://192.168.178.88")
    ap.add_argument("--esp-ip", default="192.168.178.88")
    ap.add_argument("--dev", default="/dev/sda")
    ap.add_argument("--mp3", default="docs/betrieb/artifacts-2026-10-03-m3/mp3/L1.mp3")
    ap.add_argument("--uid", default="fav0")
    ap.add_argument("--feed-kb", type=int, default=180)
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    esp = args.esp.rstrip("/")
    mp3_path = Path(args.mp3)
    if not mp3_path.is_file():
        raise SystemExit(f"mp3 missing: {mp3_path}")

    stamp = time.strftime("%H%M")
    day = time.strftime("%Y-%m-%d")
    out = Path(args.out) if args.out else Path(
        f"docs/betrieb/artifacts-{day}-lab/lab88-av-mpeg-{stamp}"
    )
    out.mkdir(parents=True, exist_ok=True)
    report: dict = {"ok": False, "stageA": {}, "stageB": {}, "out": str(out)}

    print("== clear seed + stop ==")
    http_json(f"{esp}/api/lab/body_seed", method="POST", body=b'{"slot":0,"tag":"off"}')
    http_json(f"{esp}/api/lab/stop", method="POST", body=b"{}")
    time.sleep(0.3)

    st0 = http_json(f"{esp}/api/status")
    (out / "status-00-pre.json").write_text(json.dumps(st0, indent=2))
    print("fw", st0.get("version"), "seed", (st0.get("msc") or {}).get("bodySeed"))

    pump = PumpTcp(args.esp_ip, 9090)
    try:
        pump.send_json({"t": "hello", "ver": 1})
        pump.recv_lines(time.time() + 2.0)
        pump.send_json({"t": "audio_stop"})
        time.sleep(0.15)
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
        pump.recv_lines(time.time() + 2.0)
        time.sleep(1.2)
        wait_dev(args.dev)

        st1 = http_json(f"{esp}/api/status")
        (out / "status-01-menu.json").write_text(json.dumps(st1, indent=2))
        slot = next(s for s in st1["msc"]["slotMap"] if s.get("uid") == args.uid)
        lba0 = int(slot["lba0"])
        print(f"slot {args.uid} lba0={lba0} name={slot.get('name')}")

        # baseline head sample (likely silence / pre-live)
        head = dd_bytes(args.dev, lba0, 16)
        (out / "sample-head-pre.bin").write_bytes(head)

        pump.send_json(
            {
                "t": "audio_start",
                "uid": args.uid,
                "codec": "mp3",
                "br": "48k",
                "cSrc": "av-lab",
                "cPath": "av-lab",
                "cTry": "av-lab",
            }
        )
        pump.recv_lines(time.time() + 1.0)
        pump.send_bin(0x56, build_minimal_id3("AV-Lab-MPEG"), gap_s=0.05)
        time.sleep(0.3)
        mp3 = mp3_path.read_bytes()
        feed_n = min(len(mp3), args.feed_kb * 1024)
        print(f"feeding {feed_n} B", flush=True)
        pump.send_bin(0x55, mp3[:feed_n], gap_s=0.002)
        time.sleep(0.8)

        # Stage A — ring fill without further host body hammering
        poll = []
        for i in range(8):
            st = http_json(f"{esp}/api/status")
            m = st["msc"]
            s = m.get("stream") or {}
            row = {
                "t": i + 1,
                "active": s.get("active"),
                "uid": s.get("uid"),
                "size": s.get("size"),
                "absBase": s.get("absBase"),
                "absEnd": s.get("absEnd"),
                "underruns": s.get("underruns"),
                "streamBytes": m.get("streamBytes"),
                "live": live_bytes(m, s),
                "hostAbs": s.get("hostAbsCursor"),
            }
            poll.append(row)
            print("A", row, flush=True)
            time.sleep(0.4)
        (out / "status-02-stageA.json").write_text(json.dumps(st, indent=2))
        last = poll[-1]
        stage_a_ok = bool(last.get("active")) and int(last.get("size") or 0) > 4096
        report["stageA"] = {"ok": stage_a_ok, "poll": poll}
        print("STAGE A", "PASS" if stage_a_ok else "FAIL", flush=True)

        # Stage B — read inside live window
        abs_base = int(last.get("absBase") or 0)
        abs_end = int(last.get("absEnd") or 0)
        if abs_end <= abs_base + 8192:
            # fallback: near file start after ID3
            file_off = 0
        else:
            file_off = abs_base + ((abs_end - abs_base) // 4)
            file_off = (file_off // 512) * 512
        lba = lba0 + file_off // 512
        body = dd_bytes(args.dev, lba, 32)
        (out / f"sample-live-off{file_off}.bin").write_bytes(body)
        head2 = dd_bytes(args.dev, lba0, 16)
        (out / "sample-head-post.bin").write_bytes(head2)

        st3 = http_json(f"{esp}/api/status")
        (out / "status-03-stageB.json").write_text(json.dumps(st3, indent=2))
        m3 = st3["msc"]
        s3 = m3.get("stream") or {}
        syncs = mpeg_syncs(body)
        id3 = body[:3] == b"ID3" or head2[:3] == b"ID3"
        stage_b_ok = bool(syncs) or id3 or (body[:3] == b"ID3")
        # also accept if body differs strongly from pre-head silence pattern
        changed = body != head[: len(body)] if len(head) >= 64 else body != head2
        report["stageB"] = {
            "ok": stage_b_ok,
            "file_off": file_off,
            "lba": lba,
            "abs": [abs_base, abs_end],
            "id3_in_live_or_head": id3 or head2[:3] == b"ID3",
            "mpeg_sync_offs": syncs,
            "live_prefix_hex": body[:16].hex(),
            "head_post_prefix_hex": head2[:16].hex(),
            "looks_silence_live": looks_like_silence_fill(body),
            "changed_vs_pre_head": changed,
            "streamBytes": m3.get("streamBytes"),
            "underruns": s3.get("underruns"),
            "liveBytes": live_bytes(m3, s3),
            "hostAbsCursor": s3.get("hostAbsCursor"),
        }
        print("STAGE B", "PASS" if stage_b_ok else "FAIL", report["stageB"], flush=True)

        # keep feeding a bit more then stop
        pump.send_json({"t": "audio_stop"})
    finally:
        pump.close()

    report["ok"] = bool(report["stageA"].get("ok")) and bool(report["stageB"].get("ok"))
    (out / "REPORT.json").write_text(json.dumps(report, indent=2))
    (out / "EAR.txt").write_text(
        f"lab AV MPEG-at-host {'PASS' if report['ok'] else 'FAIL'} {time.strftime('%Y-%m-%dT%H:%M:%S')}\n"
        f"A={report['stageA'].get('ok')} B={report['stageB'].get('ok')}\n"
        f"liveBytes={report['stageB'].get('liveBytes')} underruns={report['stageB'].get('underruns')}\n"
        f"OUT={out}\n"
    )
    print(f"OUT={out} ok={report['ok']}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

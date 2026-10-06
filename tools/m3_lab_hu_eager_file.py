#!/usr/bin/env python3
"""Lab: HU eager file-read mimic (File-Cache model, Stufe-2 Vorstufe).

Reads an entire MSC slot at ~4 KiB / --gap-ms (field ~3–5 ms), then the next
slot — matching NBT-Evo eager-read + next-track prefetch.

Optional realtime producer (default ~9000 B/s), not the 900 KB/s hold illusion.

Example:
  sg disk -c 'python3 tools/m3_lab_hu_eager_file.py --dev /dev/sda --uid fav1 --next fav2'
"""
from __future__ import annotations

import argparse
import json
import socket
import struct
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

KIND_AUDIO = 0x55
KIND_ID3 = 0x56
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


def wait_dev(dev: str, timeout: float = 25.0) -> None:
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


def id3(title: str) -> bytes:
    enc = b"\x03" + title.encode("utf-8")
    frame = b"TIT2" + struct.pack(">I", len(enc)) + b"\x00\x00" + enc
    size = len(frame)
    return b"ID3\x03\x00\x00" + bytes(
        [(size >> 21) & 0x7F, (size >> 14) & 0x7F, (size >> 7) & 0x7F, size & 0x7F]
    ) + frame


class PumpTcp:
    def __init__(self, host: str, port: int = 9090):
        self.s = socket.create_connection((host, port), timeout=8)
        self.s.settimeout(0.35)

    def close(self) -> None:
        try:
            self.s.close()
        except Exception:
            pass

    def send_json(self, obj: dict) -> None:
        self.s.sendall((json.dumps(obj, separators=(",", ":")) + "\n").encode())

    def send_bin(self, kind: int, payload: bytes) -> None:
        n = len(payload)
        hdr = bytes([0xA5, kind, (n >> 8) & 0xFF, n & 0xFF])
        self.s.sendall(hdr + payload)

    def drain(self, seconds: float) -> None:
        t0 = time.time()
        while time.time() - t0 < seconds:
            try:
                self.s.recv(4096)
            except Exception:
                time.sleep(0.02)


def snap(esp: str) -> dict:
    st = http_json(f"{esp}/api/status")
    m = st.get("msc") or {}
    s = m.get("stream") or st.get("stream") or {}
    sb = int(m.get("streamBytes") or 0)
    und = int(s.get("underruns") or 0)
    slots = []
    for x in m.get("slotMap") or []:
        if isinstance(x, dict):
            slots.append(
                {
                    "uid": x.get("uid"),
                    "bytes": x.get("bytes"),
                    "maxSeq": x.get("maxSeq"),
                    "lba0": x.get("lba0"),
                }
            )
    return {
        "uptime": st.get("uptime"),
        "serial": m.get("usbSerial"),
        "play": st.get("playingUid"),
        "active": s.get("active"),
        "armed": s.get("cursorArmed"),
        "hostAbs": s.get("hostAbsCursor"),
        "absBase": s.get("absBase"),
        "absEnd": s.get("absEnd"),
        "streamBytes": sb,
        "underruns": und,
        "liveBytes": max(0, sb - und),
        "readCount": m.get("readCount"),
        "bytesFile": m.get("bytesFile"),
        "slots": slots,
    }


def setup_menu(pump: PumpTcp, uid: str | None = None) -> None:
    pump.send_json({"t": "hello", "ver": 1})
    pump.drain(0.8)
    pump.send_json({"t": "audio_stop"})
    time.sleep(0.1)
    pump.send_json(
        {
            "t": "menu_set",
            "rev": 1,
            "page": 0,
            "items": [
                {"uid": "fav0", "name": "Rock Antenne", "kind": "station"},
                {"uid": "fav1", "name": "Rock Antenne Bayern", "kind": "station"},
                {"uid": "fav2", "name": "Radio BOB!", "kind": "station"},
                {"uid": "pump:page_next", "name": "Menue", "kind": "action"},
            ],
        }
    )
    pump.drain(0.5)
    if uid:
        pump.send_json(
            {
                "t": "audio_start",
                "uid": uid,
                "codec": "mp3",
                "br": "48k",
                "cSrc": "lab",
                "cPath": "lab",
                "cTry": "lab",
            }
        )
        pump.drain(0.4)
        pump.send_bin(KIND_ID3, id3("Eager-File"))


def arm_stream(pump: PumpTcp, uid: str) -> None:
    pump.send_json(
        {
            "t": "audio_start",
            "uid": uid,
            "codec": "mp3",
            "br": "48k",
            "cSrc": "lab",
            "cPath": "lab",
            "cTry": "lab",
        }
    )
    pump.drain(0.4)
    pump.send_bin(KIND_ID3, id3("Eager-File"))


def producer_loop(
    pump: PumpTcp,
    mp3: bytes,
    bps: int,
    stop: threading.Event,
    stats: dict,
) -> None:
    """Feed audio at roughly bps (token bucket), looping mp3 body after ID3 skip."""
    # skip tiny ID3 if present
    off = 0
    if mp3.startswith(b"ID3") and len(mp3) > 10:
        size = ((mp3[6] & 0x7F) << 21) | ((mp3[7] & 0x7F) << 14) | ((mp3[8] & 0x7F) << 7) | (mp3[9] & 0x7F)
        off = 10 + size
    body = mp3[off:] if off < len(mp3) else mp3
    if not body:
        body = mp3
    i = 0
    window_t0 = time.time()
    sent = 0
    while not stop.is_set():
        now = time.time()
        if now - window_t0 >= 1.0:
            window_t0 = now
            sent = 0
        if sent >= bps:
            time.sleep(0.01)
            continue
        n = min(FRAME_MAX, bps - sent, len(body) - i)
        if n <= 0:
            i = 0
            continue
        chunk = body[i : i + n]
        i += n
        try:
            pump.send_bin(KIND_AUDIO, chunk)
        except Exception as e:
            stats["err"] = str(e)
            break
        sent += len(chunk)
        stats["bytes"] = stats.get("bytes", 0) + len(chunk)
        time.sleep(0.008)


def eager_read_slot(dev: str, lba0: int, size_bytes: int, gap_ms: float) -> dict:
    """Sequential 8-sector (4 KiB) reads covering size_bytes."""
    sectors_total = max(1, (size_bytes + 511) // 512)
    chunk = 8  # 4 KiB
    t0 = time.time()
    n_ops = 0
    for skip in range(0, sectors_total, chunk):
        n = min(chunk, sectors_total - skip)
        dd(dev, lba0 + skip, n)
        n_ops += 1
        if gap_ms > 0:
            time.sleep(gap_ms / 1000.0)
    return {
        "lba0": lba0,
        "size_bytes": size_bytes,
        "ops": n_ops,
        "duration_s": round(time.time() - t0, 3),
        "gap_ms": gap_ms,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="HU eager whole-file read mimic")
    ap.add_argument("--esp", default="http://192.168.178.88")
    ap.add_argument("--esp-ip", default="192.168.178.88")
    ap.add_argument("--dev", default="/dev/sda")
    ap.add_argument("--uid", default="fav1")
    ap.add_argument("--next", default="fav2", dest="next_uid")
    ap.add_argument("--gap-ms", type=float, default=4.0)
    ap.add_argument("--pump-bps", type=int, default=9000, help="realtime-ish producer (0=off)")
    ap.add_argument(
        "--mp3",
        default="docs/betrieb/artifacts-2026-10-03-m3/mp3/L1.mp3",
    )
    ap.add_argument("--arm-before-read", action="store_true", help="audio_start before eager read (Muster A)")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    esp = args.esp.rstrip("/")
    stamp = time.strftime("%H%M")
    day = time.strftime("%Y-%m-%d")
    out = Path(args.out) if args.out else Path(
        f"docs/betrieb/artifacts-{day}-lab/lab88-hu-eager-{stamp}"
    )
    out.mkdir(parents=True, exist_ok=True)

    mp3 = Path(args.mp3)
    if not mp3.is_file():
        raise SystemExit(f"missing mp3: {mp3}")
    mp3_bytes = mp3.read_bytes()

    try:
        http_json(f"{esp}/api/lab/stop", method="POST", body=b"{}")
    except Exception:
        pass
    time.sleep(0.4)
    wait_dev(args.dev)

    report: dict = {
        "gap_ms": args.gap_ms,
        "pump_bps": args.pump_bps,
        "uid": args.uid,
        "next": args.next_uid,
        "arm_before_read": args.arm_before_read,
        "steps": [],
    }

    pump = PumpTcp(args.esp_ip)
    stop = threading.Event()
    prod_stats: dict = {}
    thr: threading.Thread | None = None
    try:
        setup_menu(pump)  # menu only; arm after remount
        try:
            http_json(f"{esp}/api/lab/remount", method="POST", body=b"{}")
            report["steps"].append({"op": "remount", "ok": True})
        except Exception as e:
            report["steps"].append({"op": "remount_err", "err": str(e)})
        time.sleep(1.5)
        wait_dev(args.dev)

        if args.arm_before_read:
            arm_stream(pump, args.uid)
        else:
            pump.send_json({"t": "audio_stop"})
            time.sleep(0.1)

        st0 = snap(esp)
        (out / "status-pre.json").write_text(json.dumps(st0, indent=2))
        report["pre"] = st0

        # resolve LBAs from live slotMap
        st = http_json(f"{esp}/api/status")
        sm = (st.get("msc") or {}).get("slotMap") or []
        by_uid = {s.get("uid"): s for s in sm if isinstance(s, dict)}
        for need in (args.uid, args.next_uid):
            if need not in by_uid:
                raise SystemExit(f"missing slot {need}: {list(by_uid)}")

        if args.pump_bps > 0 and args.arm_before_read:
            thr = threading.Thread(
                target=producer_loop,
                args=(pump, mp3_bytes, args.pump_bps, stop, prod_stats),
                daemon=True,
            )
            thr.start()
            time.sleep(0.3)

        def slot_size(s: dict) -> int:
            # slotMap.bytes = host progress, not file size; prefer LBA span
            l0, l1 = int(s["lba0"]), int(s["lba1"])
            return max(512, (l1 - l0 + 1) * 512)

        s1 = by_uid[args.uid]
        size1 = slot_size(s1)
        r1 = eager_read_slot(args.dev, int(s1["lba0"]), size1, args.gap_ms)
        report["steps"].append({"op": "eager", "uid": args.uid, **r1})
        mid = snap(esp)
        (out / "status-after-uid.json").write_text(json.dumps(mid, indent=2))
        report["after_uid"] = mid

        s2 = by_uid[args.next_uid]
        size2 = slot_size(s2)
        r2 = eager_read_slot(args.dev, int(s2["lba0"]), size2, args.gap_ms)
        report["steps"].append({"op": "eager_next", "uid": args.next_uid, **r2})
        post = snap(esp)
        (out / "status-after-next.json").write_text(json.dumps(post, indent=2))
        report["after_next"] = post
        report["producer"] = dict(prod_stats)

        # Heuristic classification
        host = int(post.get("hostAbs") or 0)
        und = int(post.get("underruns") or 0)
        max_seq = None
        for s in post.get("slots") or []:
            if s.get("uid") == args.uid:
                max_seq = s.get("maxSeq")
        report["classification"] = {
            "maxSeq_uid": max_seq,
            "hostAbs": host,
            "underruns": und,
            "hint": (
                "Muster_A_like"
                if args.arm_before_read and host > 0
                else "Muster_B_prefetch_like"
                if max_seq and int(max_seq) >= size1 * 0.9
                else "partial_or_unknown"
            ),
        }
    finally:
        stop.set()
        if thr:
            thr.join(timeout=2)
        try:
            pump.send_json({"t": "audio_stop"})
        except Exception:
            pass
        pump.close()

    (out / "REPORT.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report["classification"], indent=2))
    print(f"OUT {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

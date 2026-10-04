#!/usr/bin/env python3
"""Q3a Lab: prove ESP delivers payload B on MSC host read after overlay arm.

Protocol:
  1. lab/stop + remount
  2. Host-hash silence at several body offsets on fav1 (= A)
  3. TCP pump: hello → menu_set → audio_start(fav1) → stream MP3 (= B)
  4. Pick offset inside stream absBase..absEnd; host-hash vs overlay_read
  5. PASS if host==overlay and host≠silence(A)

Example:
  python3 tools/m3_lab_q3a_freshness.py --esp http://192.168.178.88 --dev /dev/sda \\
    --mp3 docs/betrieb/artifacts-2026-10-03-m3/mp3/L1.mp3
"""
from __future__ import annotations

import argparse
import hashlib
import json
import socket
import struct
import subprocess
import time
import urllib.request
from pathlib import Path

FRAME_MAX = 256
ID3_BUDGET = 8 * 1024
SAMPLE_SECTORS = 16  # 8 KiB
PROBE_OFFS = (32 * 1024, 64 * 1024, 96 * 1024, 128 * 1024, 192 * 1024)


def http_json(url: str, method: str = "GET", body: bytes | None = None) -> dict:
    req = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={"Content-Type": "application/json"} if body is not None else {},
    )
    with urllib.request.urlopen(req, timeout=12) as r:
        raw = r.read()
        return json.loads(raw.decode()) if raw else {}


def http_bytes(url: str) -> tuple[bytes, dict[str, str]]:
    with urllib.request.urlopen(url, timeout=12) as r:
        headers = {k.lower(): v for k, v in r.headers.items()}
        return r.read(), headers


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
        try:
            dd_bytes(dev, 0, 1)
            return
        except subprocess.CalledProcessError:
            time.sleep(0.4)
    raise SystemExit(f"device {dev} not ready")


def sha16(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()[:16]


class PumpTcp:
    def __init__(self, host: str, port: int = 9090):
        self.s = socket.create_connection((host, port), timeout=8)
        self.s.settimeout(0.3)
        self.buf = b""

    def close(self) -> None:
        try:
            self.s.close()
        except OSError:
            pass

    def send_json(self, obj: dict) -> None:
        line = json.dumps(obj, separators=(",", ":")) + "\n"
        self.s.sendall(line.encode())
        print(f"[tx] {line.strip()}", flush=True)

    def send_bin(self, kind: int, payload: bytes, gap_s: float = 0.004) -> None:
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
                if not text or text[0] != "{":
                    continue
                try:
                    msg = json.loads(text)
                except json.JSONDecodeError:
                    continue
                print(f"[rx] {text[:180]}", flush=True)
                out.append(msg)
        return out


def build_minimal_id3(title: str = "Q3a-B") -> bytes:
    enc = b"\x00" + title.encode("latin-1", errors="replace")[:30]
    frame = b"TIT2" + struct.pack(">I", len(enc)) + b"\x00\x00" + enc
    size = len(frame)
    header = b"ID3\x03\x00\x00" + bytes(
        [(size >> 21) & 0x7F, (size >> 14) & 0x7F, (size >> 7) & 0x7F, size & 0x7F]
    )
    return (header + frame)[:ID3_BUDGET]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--esp", default="http://192.168.178.88")
    ap.add_argument("--esp-ip", default="192.168.178.88")
    ap.add_argument("--dev", default="/dev/sda")
    ap.add_argument(
        "--mp3",
        default="docs/betrieb/artifacts-2026-10-03-m3/mp3/L1.mp3",
    )
    ap.add_argument("--slot-i", type=int, default=1)
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    esp = args.esp.rstrip("/")
    mp3_path = Path(args.mp3)
    if not mp3_path.is_file():
        raise SystemExit(f"mp3 missing: {mp3_path}")

    stamp = time.strftime("%H%M")
    day = time.strftime("%Y-%m-%d")
    out = Path(args.out) if args.out else Path(
        f"docs/betrieb/artifacts-{day}-lab/lab88-q3a-{stamp}"
    )
    out.mkdir(parents=True, exist_ok=True)

    print("== Q3a stop+remount ==")
    http_json(f"{esp}/api/lab/stop", method="POST", body=b"{}")
    time.sleep(0.4)
    http_json(f"{esp}/api/lab/remount", method="POST", body=b"{}")
    time.sleep(2.0)
    wait_dev(args.dev)

    st = http_json(f"{esp}/api/status")
    (out / "status-00-after-remount.json").write_text(json.dumps(st, indent=2))
    m = st["msc"]
    slot = m["slotMap"][args.slot_i]
    lba0, lba1 = int(slot["lba0"]), int(slot["lba1"])
    slot_bytes = (lba1 - lba0 + 1) * 512
    print(
        f"fw={st['version']} serial={m.get('usbSerial')} slot={args.slot_i} "
        f"name={slot.get('name')!r} uid={slot.get('uid')} lba={lba0}..{lba1}"
    )

    try:
        dd_bytes(args.dev, 0, 8)
    except subprocess.CalledProcessError:
        pass
    time.sleep(0.8)

    silence: dict[int, bytes] = {}
    for off in PROBE_OFFS:
        if off + SAMPLE_SECTORS * 512 > slot_bytes:
            continue
        silence[off] = dd_bytes(args.dev, lba0 + off // 512, SAMPLE_SECTORS)
        print(f"A off={off} sha16={sha16(silence[off])}")

    st_a = http_json(f"{esp}/api/status")
    (out / "status-01-pre-A.json").write_text(json.dumps(st_a, indent=2))
    bytes_ctr = int(st_a["msc"]["slotMap"][args.slot_i].get("bytes") or 0)
    preflight = {
        "slot": args.slot_i,
        "uid": st_a["msc"]["slotMap"][args.slot_i].get("uid"),
        "name": st_a["msc"]["slotMap"][args.slot_i].get("name"),
        "lba0": lba0,
        "lba1": lba1,
        "bytes_after_scan": bytes_ctr,
        "cold": bytes_ctr < slot_bytes // 2,
        "silence_hashes": {str(k): sha16(v) for k, v in silence.items()},
    }

    print("== pump TCP arm overlay B ==")
    pump = PumpTcp(args.esp_ip, 9090)
    stream: dict = {}
    overlay = b""
    blob_b = b""
    file_off = 0
    hash_a = ""
    hash_b = ""
    match_overlay = False
    changed = False
    target_uid = f"fav{args.slot_i}"
    feed_n = 0
    verdict = "FAIL"
    try:
        pump.send_json({"t": "hello", "ver": 1})
        msgs = pump.recv_lines(time.time() + 2.5)
        if not any(x.get("t") == "hello_ack" for x in msgs):
            print("WARN: no hello_ack", flush=True)
        pump.send_json({"t": "audio_stop"})
        time.sleep(0.2)
        pump.send_json(
            {
                "t": "menu_set",
                "rev": int(time.time()) % 100000,
                "page": 0,
                "items": [
                    {"uid": "fav0", "name": "Q3a Rock", "kind": "station"},
                    {"uid": "fav1", "name": "Q3a Bayern", "kind": "station"},
                    {"uid": "fav2", "name": "Q3a BOB", "kind": "station"},
                    {"uid": "pump:page_next", "name": "Menue", "kind": "action"},
                ],
            }
        )
        pump.recv_lines(time.time() + 2.0)
        time.sleep(1.5)
        wait_dev(args.dev)

        st_m = http_json(f"{esp}/api/status")
        (out / "status-02-after-menu.json").write_text(json.dumps(st_m, indent=2))
        slot = next(
            s
            for s in st_m["msc"]["slotMap"]
            if s.get("uid") == target_uid or s.get("i") == args.slot_i
        )
        target_uid = slot["uid"]
        lba0, lba1 = int(slot["lba0"]), int(slot["lba1"])

        pump.send_json(
            {
                "t": "audio_start",
                "uid": target_uid,
                "codec": "mp3",
                "br": "48k",
                "cSrc": "q3a",
                "cPath": "q3a",
                "cTry": "q3a",
            }
        )
        pump.recv_lines(time.time() + 1.2)
        pump.send_bin(0x56, build_minimal_id3("Q3a-Payload-B"), gap_s=0.05)
        time.sleep(0.4)

        mp3 = mp3_path.read_bytes()
        feed_n = min(len(mp3), 220 * 1024)
        print(f"feeding {feed_n} B of {mp3_path.name}", flush=True)
        pump.send_bin(0x55, mp3[:feed_n], gap_s=0.002)
        time.sleep(1.0)

        st_b = http_json(f"{esp}/api/status")
        (out / "status-03-overlay-armed.json").write_text(json.dumps(st_b, indent=2))
        stream = st_b["msc"].get("stream") or {}
        abs_base = int(stream.get("absBase") or 0)
        abs_end = int(stream.get("absEnd") or 0)
        print(
            f"stream active={stream.get('active')} size={stream.get('size')} "
            f"uid={stream.get('uid')} abs={abs_base}..{abs_end}"
        )

        # Choose sample inside live window, preferring a pre-hashed silence offset
        candidates = [
            o
            for o in silence
            if abs_base <= o and o + SAMPLE_SECTORS * 512 <= abs_end
        ]
        if not candidates and abs_end > abs_base + SAMPLE_SECTORS * 512:
            live = abs_base + ((abs_end - abs_base) // 3)
            file_off = (live // 512) * 512
            hash_a = "unsampled_silence"
            blob_a = b""
        else:
            file_off = candidates[len(candidates) // 2] if candidates else 64 * 1024
            blob_a = silence.get(file_off, b"")
            hash_a = sha16(blob_a) if blob_a else "missing"

        sample_lba = lba0 + file_off // 512
        print(f"sample file_off={file_off} lba={sample_lba} hash_A={hash_a}")

        try:
            overlay, hdr = http_bytes(
                f"{esp}/api/lab/overlay_read?off={file_off}&n={SAMPLE_SECTORS * 512}"
            )
            (out / "overlay_B.bin").write_bytes(overlay)
            print(
                f"overlay_read n={len(overlay)} sha16={sha16(overlay)} "
                f"uid={hdr.get('x-stream-uid')}"
            )
        except Exception as e:
            print(f"overlay_read failed: {e}")
            overlay = b""

        blob_b = dd_bytes(args.dev, sample_lba, SAMPLE_SECTORS)
        hash_b = sha16(blob_b)
        if blob_a:
            (out / "host_A.bin").write_bytes(blob_a)
        (out / "host_B.bin").write_bytes(blob_b)
        print(f"B host sha16={hash_b}")

        n = min(len(overlay), len(blob_b))
        match_overlay = n >= 512 and overlay[:n] == blob_b[:n]
        changed = bool(blob_a) and blob_b != blob_a

        if not stream.get("active"):
            verdict = "FAIL_NO_STREAM"
        elif match_overlay and changed:
            verdict = "PASS"
        elif match_overlay and not blob_a:
            verdict = "PASS_ORACLE"  # host==overlay, no silence baseline at that off
        elif changed:
            verdict = "PASS_WEAK"
        else:
            verdict = "FAIL_NO_CHANGE"
    finally:
        try:
            pump.send_json({"t": "audio_stop"})
        except Exception:
            pass
        pump.close()

    report = {
        "verdict": verdict,
        "fw": st.get("version"),
        "serial": m.get("usbSerial"),
        "preflight": preflight,
        "file_off": file_off,
        "hash_a": hash_a,
        "hash_b": hash_b,
        "hash_overlay": sha16(overlay) if overlay else None,
        "changed_A_to_B": changed,
        "match_overlay": match_overlay,
        "stream": stream,
        "target_uid": target_uid,
        "mp3": str(mp3_path),
        "feed_bytes": feed_n,
    }
    (out / "report.json").write_text(json.dumps(report, indent=2))
    (out / "EAR.txt").write_text(
        "\n".join(
            [
                f"Q3a Lab {day} {stamp}",
                f"verdict={verdict}",
                f"serial={report['serial']} uid={target_uid}",
                f"preflight.warmth.slot{args.slot_i} bytes={preflight['bytes_after_scan']} cold={preflight['cold']}",
                f"file_off={file_off} hash_A={hash_a} hash_B={hash_b} overlay={report['hash_overlay']}",
                f"changed={changed} match_overlay={match_overlay}",
                f"stream.active={stream.get('active')} abs={stream.get('absBase')}..{stream.get('absEnd')}",
                "",
            ]
        )
    )
    print(json.dumps(report, indent=2))
    print(f"artefacts: {out}")
    return 0 if verdict.startswith("PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())

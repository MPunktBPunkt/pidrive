#!/usr/bin/env python3
"""Paced MSC consume for a chosen uid (uses slotMap LBA)."""
from __future__ import annotations

import json
import subprocess
import time
import urllib.request


ESP = "http://192.168.178.88"
DEV = "/dev/sda"


def get() -> dict:
    return json.load(urllib.request.urlopen(ESP + "/api/status", timeout=5))


def post(path: str, body: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        ESP + path,
        data=data,
        headers={"Content-Type": "application/json"} if data else {},
        method="POST",
    )
    return json.load(urllib.request.urlopen(req, timeout=10))


def stream_of(st: dict) -> dict:
    s = st.get("stream")
    if isinstance(s, dict) and s:
        return s
    return (st.get("msc") or {}).get("stream") or {}


def dd_chunk(lba: int, sectors: int = 8) -> None:
    for _ in range(5):
        try:
            subprocess.check_call(
                [
                    "dd",
                    f"if={DEV}",
                    "bs=512",
                    f"skip={lba}",
                    f"count={sectors}",
                    "iflag=direct",
                    "status=none",
                    "of=/dev/null",
                ],
                stderr=subprocess.DEVNULL,
            )
            return
        except subprocess.CalledProcessError:
            time.sleep(0.3)
    raise SystemExit(f"dd failed lba={lba}")


def wait_uid(uid: str, timeout: float = 25.0) -> dict:
    t0 = time.time()
    while time.time() - t0 < timeout:
        st = get()
        s = stream_of(st)
        print(
            f"  arm {uid}: stream={s.get('uid')} active={s.get('active')} "
            f"size={s.get('size')} id3={s.get('id3Len')}",
            flush=True,
        )
        if s.get("active") and s.get("uid") == uid and int(s.get("size") or 0) > 0:
            return st
        time.sleep(0.5)
    raise SystemExit(f"timeout {uid}")


def paced(uid: str, seconds: float = 10.0, kib_per_s: float = 6.0) -> dict:
    print(f"===== paced {uid} =====", flush=True)
    print(post("/api/lab/stop"), flush=True)
    time.sleep(1)
    print(post("/api/lab/play", {"uid": uid}), flush=True)
    st = wait_uid(uid)
    slot = next(x for x in st["msc"]["slotMap"] if x["uid"] == uid)
    lba0 = int(slot["lba0"])
    print(f"fw={st['version']} uid={uid} lba0={lba0} name={slot.get('name')}", flush=True)

    bytes_per_s = kib_per_s * 1024.0
    chunk_bytes = 8 * 512
    interval = chunk_bytes / bytes_per_s
    before = get()
    b_msc = before["msc"]
    b_s = stream_of(before)
    off = 0
    n = 0
    t_end = time.time() + seconds
    while time.time() < t_end:
        dd_chunk(lba0 + off, 8)
        off += 8
        if off >= 900:
            off = 0
        n += 1
        time.sleep(max(0.0, interval))
    after = get()
    a_msc = after["msc"]
    a_s = stream_of(after)
    sb = int(a_msc.get("streamBytes") or 0) - int(b_msc.get("streamBytes") or 0)
    ud = int(a_s.get("underruns") or 0) - int(b_s.get("underruns") or 0)
    live = max(0, sb - ud)
    ratio = (live / sb) if sb else 0.0
    out = {
        "uid": uid,
        "name": slot.get("name"),
        "lba0": lba0,
        "chunks": n,
        "streamBytes": sb,
        "underruns": ud,
        "live": live,
        "live_ratio": ratio,
        "id3Len": a_s.get("id3Len"),
        "hasCover": a_s.get("hasCover"),
        "headResyncs_delta": int(a_s.get("headResyncs") or 0) - int(b_s.get("headResyncs") or 0),
    }
    print(json.dumps(out, indent=2), flush=True)
    return out


def main() -> None:
    results = [paced("fav0"), paced("fav1")]
    Path = __import__("pathlib").Path
    Path("/tmp/paced-fav0-fav1.json").write_text(json.dumps(results, indent=2))
    print("==== compare ====", flush=True)
    for r in results:
        print(
            f"{r['uid']} {r['name']}: live_ratio={r['live_ratio']:.3f} "
            f"streamB={r['streamBytes']} under={r['underruns']} id3={r['id3Len']} cover={r['hasCover']}",
            flush=True,
        )


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Lab: verify pump_bridge rapid-switch uses started_at (not forward heartbeat).

A) fav0 armed, wait 6s (heartbeat would refresh old last_audio_log), then fav1
   → must switch (stream uid=fav1)
B) fav1 armed, immediate fav0 (<2s)
   → ignore rapid OR still fav1 briefly; must NOT permanently stick wrong after 6s wait+retry
"""
from __future__ import annotations

import json
import time
import urllib.request

ESP = "http://192.168.178.88"


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


def wait_pump(timeout: float = 20.0) -> None:
    t0 = time.time()
    while time.time() - t0 < timeout:
        d = get()
        if d.get("pumpTcpUp"):
            print(f"  pump up peer={d.get('pumpTcpPeer')}", flush=True)
            return
        time.sleep(0.5)
    raise SystemExit("TIMEOUT pumpTcpUp")


def wait_stream_off(timeout: float = 15.0) -> None:
    t0 = time.time()
    while time.time() - t0 < timeout:
        s = stream_of(get())
        print(f"  stream_off? active={s.get('active')} uid={s.get('uid')}", flush=True)
        if not s.get("active"):
            return
        time.sleep(0.5)
    # soft: continue anyway after stop attempts
    print("  WARN stream still active after stop timeout", flush=True)


def wait_uid(uid: str, timeout: float = 35.0) -> dict:
    t0 = time.time()
    while time.time() - t0 < timeout:
        st = get()
        s = stream_of(st)
        print(
            f"  wait {uid}: play={st.get('playingUid')} stream={s.get('uid')} "
            f"active={s.get('active')} size={s.get('size')}",
            flush=True,
        )
        if s.get("active") and s.get("uid") == uid and int(s.get("size") or 0) > 0:
            return st
        time.sleep(0.5)
    raise SystemExit(f"TIMEOUT waiting for stream {uid}")


def hard_stop() -> None:
    print(post("/api/lab/stop"), flush=True)
    time.sleep(1)
    print(post("/api/lab/stop"), flush=True)
    time.sleep(2)
    wait_stream_off()


def main() -> None:
    wait_pump()
    print("=== hard stop ===", flush=True)
    hard_stop()

    print("=== A delayed switch: fav0 6s → fav1 (must switch) ===", flush=True)
    print(post("/api/lab/play", {"uid": "fav0"}), flush=True)
    wait_uid("fav0")
    print("  hold 6s…", flush=True)
    time.sleep(6.0)
    # confirm still fav0 / forwarding window
    s0 = stream_of(get())
    print(f"  still fav0? uid={s0.get('uid')} size={s0.get('size')}", flush=True)
    print(post("/api/lab/play", {"uid": "fav1"}), flush=True)
    wait_uid("fav1")
    print("PASS A: delayed fav0→fav1 while streaming", flush=True)

    print("=== B immediate switch: fav1 → fav0 within 2s ===", flush=True)
    # fav1 already active from A; play fav0 immediately
    t0 = time.time()
    print(post("/api/lab/play", {"uid": "fav0"}), flush=True)
    time.sleep(2.0)
    st = get()
    s = stream_of(st)
    age = time.time() - t0
    print(
        f"AFTER_IMMEDIATE dt={age:.1f}s stream={s.get('uid')} play={st.get('playingUid')}",
        flush=True,
    )
    # With fix: ignore if age since fav1 start <4s. fav1 started at end of A, so
    # immediate fav0 should be ignored → stream stays fav1.
    if s.get("uid") == "fav0":
        print("NOTE B: switched immediately (debounce window already elapsed)", flush=True)
    else:
        print("PASS B: immediate switch blocked/debounce (stream still fav1)", flush=True)
        # After >4s from fav1 start, switch must work
        print("  wait 5s then retry fav0…", flush=True)
        time.sleep(5.0)
        print(post("/api/lab/play", {"uid": "fav0"}), flush=True)
        wait_uid("fav0")
        print("PASS B2: fav0 switch after debounce window", flush=True)

    print("ALL GUARD TESTS PASS", flush=True)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Lab P0: Arm-Timeline — prep (RST/remount), read/producer history, dense cursor snaps.

Implements review consensus (GPT/Mistral 87d2523):
  - Find cursorArmed false→true and absBase/hostAbs at that moment
  - Versuch C: producer run (absBase>>0) then head burst
  - Prep matrix: none | soft_rst | usb_remount | rst_remount (field RST ≈ soft_rst + USB re-enumerate)

Does NOT change Detect policy. Per-read fileOff needs FW/reads JSONL — status polling only here.

Example:
  sg disk -c 'python3 tools/m3_lab_arm_timeline.py --prep soft_rst --producer-s 5'
  sg disk -c 'python3 tools/m3_lab_arm_timeline.py --prep usb_remount --mid-kib 256 --prefill-kb 96'
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


def http_post_allow_empty(url: str, body: bytes = b"{}", timeout: float = 12) -> dict:
    """POST that tolerates empty/non-JSON bodies (ESP /api/restart often returns none)."""
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        if not raw:
            return {"ok": True, "empty": True}
        try:
            return json.loads(raw.decode())
        except json.JSONDecodeError:
            return {"ok": True, "raw": raw.decode("utf-8", errors="replace")[:200]}


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

    def drain(self, seconds: float = 0.5) -> None:
        t_end = time.time() + seconds
        while time.time() < t_end:
            try:
                chunk = self.s.recv(4096)
                if not chunk:
                    break
            except (socket.timeout, ConnectionResetError, BrokenPipeError, OSError):
                continue

    def send_bin(self, kind: int, payload: bytes, gap_s: float = 0.002) -> None:
        off = 0
        while off < len(payload):
            chunk = payload[off : off + FRAME_MAX]
            hdr = bytes((0x01, kind, len(chunk) & 0xFF, (len(chunk) >> 8) & 0xFF))
            self.s.sendall(hdr + chunk)
            off += len(chunk)
            time.sleep(gap_s)


def id3(title: str) -> bytes:
    enc = b"\x00" + title.encode("latin-1", errors="replace")[:30]
    frame = b"TIT2" + struct.pack(">I", len(enc)) + b"\x00\x00" + enc
    size = len(frame)
    return b"ID3\x03\x00\x00" + bytes(
        [(size >> 21) & 0x7F, (size >> 14) & 0x7F, (size >> 7) & 0x7F, size & 0x7F]
    ) + frame


def snap(esp: str, mark: str = "") -> dict:
    st = http_json(f"{esp}/api/status")
    m = st.get("msc") or {}
    s = m.get("stream") or st.get("stream") or {}
    sb = int(m.get("streamBytes") or 0)
    ud = int(s.get("underruns") or 0)
    base = int(s.get("absBase") or 0)
    end = int(s.get("absEnd") or 0)
    host = int(s.get("hostAbsCursor") or 0)
    return {
        "ts": time.time(),
        "mark": mark,
        "uptime": st.get("uptime"),
        "usbSerial": m.get("usbSerial"),
        "remountGen": m.get("remountGen"),
        "playingUid": st.get("playingUid") or "",
        "playGuessCount": int(m.get("playGuessCount") or 0),
        "playRejectCount": int(m.get("playRejectCount") or 0),
        "stream_active": bool(s.get("active")),
        "cursorArmed": bool(s.get("cursorArmed")),
        "ring_size": int(s.get("size") or 0),
        "absBase": base,
        "absEnd": end,
        "hostAbsCursor": host,
        "streamBytes": sb,
        "underruns": ud,
        "liveBytes": max(0, sb - ud),
        "ahead": max(0, host - end) if end else 0,
        "behind_base": max(0, base - host) if base else 0,
        "in_window": end > base and base <= host < end,
        "headResyncs": int(s.get("headResyncs") or 0),
        "lastReadLba": m.get("lastReadLba"),
        "readOverflow": m.get("readOverflow"),
        "msSincePlug": m.get("msSincePlug"),
    }


def burst(dev: str, lba: int, total: int, chunk: int = 4096, gap_ms: float = 4.5) -> None:
    done = 0
    while done < total:
        dd(dev, lba + done // 512, max(1, chunk // 512))
        done += chunk
        time.sleep(gap_ms / 1000.0)


def burst_dense(
    dev: str,
    lba: int,
    total: int,
    esp: str,
    series: list[dict],
    prefix: str,
    chunk: int = 4096,
    gap_ms: float = 4.5,
) -> None:
    done = 0
    i = 0
    while done < total:
        series.append(snap(esp, f"{prefix}_pre_{i}"))
        dd(dev, lba + done // 512, max(1, chunk // 512))
        done += chunk
        series.append(snap(esp, f"{prefix}_post_{i}"))
        i += 1
        time.sleep(gap_ms / 1000.0)


def setup_menu(pump: PumpTcp) -> None:
    pump.send_json({"t": "hello", "ver": 1})
    pump.drain(0.8)
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
    pump.drain(1.2)


def apply_prep(esp: str, dev: str, prep: str) -> dict:
    log: dict = {"prep": prep, "steps": []}
    if prep in ("soft_rst", "rst_remount"):
        try:
            http_post_allow_empty(f"{esp}/api/restart", body=b"{}")
            log["steps"].append("POST /api/restart")
        except Exception as e:
            log["steps"].append(f"restart_err={e}")
        for _ in range(45):
            try:
                st = http_json(f"{esp}/api/status")
                if st.get("ok"):
                    log["serial_after"] = (st.get("msc") or {}).get("usbSerial")
                    log["uptime_after"] = st.get("uptime")
                    break
            except Exception:
                pass
            time.sleep(1)
        time.sleep(2)
        wait_dev(dev)
    if prep in ("usb_remount", "rst_remount"):
        try:
            r = http_json(f"{esp}/api/lab/remount", method="POST", body=b"{}")
            log["steps"].append(f"remount={r}")
        except Exception as e:
            log["steps"].append(f"remount_err={e}")
        time.sleep(1.5)
        wait_dev(dev)
        # host nudge like m3seq rehearsal
        try:
            dd(dev, 0, 8)
        except subprocess.CalledProcessError:
            pass
    if prep == "none":
        log["steps"].append("noop")
    return log


def pump_audio(pump: PumpTcp, uid: str, mp3: bytes, nbytes: int, tag: str) -> None:
    pump.send_json(
        {
            "t": "audio_start",
            "uid": uid,
            "codec": "mp3",
            "br": "48k",
            "cSrc": "lab",
            "cPath": tag,
            "cTry": tag,
        }
    )
    pump.drain(0.35)
    pump.send_bin(KIND_ID3, id3(tag[:20]), gap_s=0.05)
    n = min(len(mp3), nbytes)
    pump.send_bin(KIND_AUDIO, mp3[:n], gap_s=0.002)


def cursor_hold_allows(st: dict, ring_cap: int, next_chunk: int = 0) -> bool:
    """Producer may write only while window cannot fully outrun the host cursor.

    GPT rule: absEnd <= hostAbs + cap  (equiv. absBase <= hostAbs when ring full).
    Before cursor is armed / hostAbs==0: allow fill (Prefill/Pace warm-up).
    """
    if not st.get("cursorArmed") or int(st.get("hostAbsCursor") or 0) <= 0:
        return True
    host = int(st.get("hostAbsCursor") or 0)
    abs_base = int(st.get("absBase") or 0)
    abs_end = int(st.get("absEnd") or 0)
    if abs_end <= 0 and abs_base <= 0:
        return True
    projected_end = abs_end + max(0, next_chunk)
    if projected_end > host + ring_cap:
        return False
    if abs_base >= host and abs_end > 0:
        return False
    return True


def find_arm_transition(series: list[dict]) -> dict | None:
    prev_armed = None
    for r in series:
        armed = bool(r.get("cursorArmed"))
        if prev_armed is False and armed is True:
            return {
                "ts": r.get("ts"),
                "mark": r.get("mark"),
                "hostAbsCursor": r.get("hostAbsCursor"),
                "absBase": r.get("absBase"),
                "absEnd": r.get("absEnd"),
                "underruns": r.get("underruns"),
                "streamBytes": r.get("streamBytes"),
                "headResyncs": r.get("headResyncs"),
                "in_window": r.get("in_window"),
                "liveBytes": r.get("liveBytes"),
            }
        if prev_armed is None:
            prev_armed = armed
        else:
            prev_armed = armed
    # also: first sample where cursorArmed true
    for r in series:
        if r.get("cursorArmed"):
            return {
                "ts": r.get("ts"),
                "mark": r.get("mark"),
                "hostAbsCursor": r.get("hostAbsCursor"),
                "absBase": r.get("absBase"),
                "absEnd": r.get("absEnd"),
                "note": "first_armed_sample_not_edge",
                **{k: r.get(k) for k in ("underruns", "streamBytes", "headResyncs", "in_window", "liveBytes")},
            }
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--esp", default="http://192.168.178.88")
    ap.add_argument("--esp-ip", default="192.168.178.88")
    ap.add_argument("--dev", default="/dev/sda")
    ap.add_argument("--uid", default="fav1")
    ap.add_argument("--mp3", default="docs/betrieb/artifacts-2026-10-03-m3/mp3/L1.mp3")
    ap.add_argument("--out", default="")
    ap.add_argument(
        "--prep",
        choices=("none", "soft_rst", "usb_remount", "rst_remount"),
        default="soft_rst",
        help="none | soft_rst (field ESP-RST) | usb_remount | rst_remount",
    )
    ap.add_argument("--mid-kib", type=int, default=0, help="Mid-file reads before head (0=skip)")
    ap.add_argument("--producer-s", type=float, default=0, help="Pump audio this long before head (Versuch C)")
    ap.add_argument("--prefill-kb", type=int, default=0, help="Fixed prefill KiB immediately before head burst")
    ap.add_argument("--post-head-kib", type=int, default=256, help="Continue head sequential reads after arm")
    ap.add_argument("--dense", action="store_true", help="Snap before/after each 4KiB during head burst")
    ap.add_argument(
        "--bridge-mimic",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="After head tip / playGuess: audio_start like field bridge (needed for live path / cursorArm)",
    )
    ap.add_argument(
        "--post-pump-kb",
        type=int,
        default=0,
        help="While post-head reads continue, pump up to this many KiB (trickle; 0=no pump)",
    )
    ap.add_argument(
        "--post-pump-chunk",
        type=int,
        default=2048,
        help="Bytes pumped per host 4KiB step when post-pump active (use >4096 to outrun host)",
    )
    ap.add_argument(
        "--producer-gate",
        action="store_true",
        help="Pause post-pump when ring full (size>=cap); resume when size < cap/2 (Bridge-side, no FW)",
    )
    ap.add_argument(
        "--tail-pump-s",
        type=float,
        default=0,
        help="After post-head: pump this many seconds with NO host reads (field 18:07 window-ahead repro)",
    )
    ap.add_argument("--tail-pump-chunk", type=int, default=4096, help="Chunk size for --tail-pump-s")
    ap.add_argument(
        "--cursor-hold",
        action="store_true",
        help="Cursor-aware producer: pause pump when absBase > hostAbs (or absEnd > hostAbs+cap); no FW change",
    )
    ap.add_argument(
        "--host-pause-after-kib",
        type=int,
        default=0,
        help="During post-head: after this many KiB host reads, pause host for --host-pause-s (Versuch C)",
    )
    ap.add_argument(
        "--host-pause-s",
        type=float,
        default=0,
        help="Seconds of host-idle while producer may continue (pair with --host-pause-after-kib)",
    )
    ap.add_argument("--ring-cap", type=int, default=49152, help="Ring capacity for producer-gate / cursor-hold")
    ap.add_argument("--settle-s", type=float, default=3.0)
    ap.add_argument("--label", default="", help="Scenario label in report")
    args = ap.parse_args()

    esp = args.esp.rstrip("/")
    stamp = time.strftime("%H%M")
    day = time.strftime("%Y-%m-%d")
    out = Path(args.out) if args.out else Path(
        f"docs/betrieb/artifacts-{day}-lab/lab88-arm-timeline-{stamp}"
    )
    out.mkdir(parents=True, exist_ok=True)
    mp3 = Path(args.mp3).read_bytes()

    try:
        http_json(f"{esp}/api/lab/body_seed", method="POST", body=b'{"slot":0,"tag":"off"}')
    except Exception:
        pass
    try:
        http_json(f"{esp}/api/lab/stop", method="POST", body=b"{}")
    except Exception:
        pass
    time.sleep(0.3)

    prep_log = apply_prep(esp, args.dev, args.prep)
    (out / "prep.json").write_text(json.dumps(prep_log, indent=2))

    wait_dev(args.dev)
    series: list[dict] = []
    lba0 = need = 0
    pumped = 0
    gate_pauses = 0
    hold_pauses = 0
    hold_paused = False
    pump = PumpTcp(args.esp_ip)
    try:
        setup_menu(pump)
        wait_dev(args.dev)
        time.sleep(args.settle_s)
        series.append(snap(esp, "settle"))
        st = http_json(f"{esp}/api/status")
        slot = next(s for s in st["msc"]["slotMap"] if s["uid"] == args.uid)
        lba0 = int(slot["lba0"])
        pd = (st.get("msc") or {}).get("playDetect") or {}
        min_seq = int(pd.get("minSeqBytes") or 6000)
        need = max(min_seq + 2048, 12 * 1024)
        g0 = series[-1]["playGuessCount"]

        if args.mid_kib > 0:
            mid_lba = lba0 + (args.mid_kib * 1024 // 512)
            print(f"== mid history {args.mid_kib} KiB ==", flush=True)
            burst(args.dev, mid_lba, args.mid_kib * 1024, 4096, 4.5)
            series.append(snap(esp, "after_mid"))

        if args.producer_s > 0:
            print(f"== producer {args.producer_s}s (Versuch C) ==", flush=True)
            pump_audio(pump, args.uid, mp3, 64 * 1024, "prod_run")
            t_end = time.time() + args.producer_s
            while time.time() < t_end:
                pump.send_bin(KIND_AUDIO, mp3[:4096], gap_s=0.08)
                series.append(snap(esp, "producer_tick"))
                time.sleep(0.15)
            series.append(snap(esp, "after_producer"))

        if args.prefill_kb > 0:
            print(f"== prefill {args.prefill_kb} KiB ==", flush=True)
            pump_audio(pump, args.uid, mp3, args.prefill_kb * 1024, "prefill")
            time.sleep(0.35)
            series.append(snap(esp, "after_prefill"))

        # Head tip until Detect (field: HU reads lba0 ≥ minSeq)
        print("== head tip (Detect) ==", flush=True)
        series.append(snap(esp, "before_head"))
        if args.dense:
            burst_dense(args.dev, lba0, need, esp, series, "head_tip", 4096, 4.5)
        else:
            burst(args.dev, lba0, need, 4096, 4.5)
        for _ in range(16):
            series.append(snap(esp, "head_tip_poll"))
            if series[-1]["playGuessCount"] > g0 or series[-1]["playingUid"] == args.uid:
                break
            time.sleep(0.1)
        s_tip = series[-1]
        print(
            f"  tip guess={s_tip['playGuessCount']} play={s_tip['playingUid']!r} "
            f"active={s_tip['stream_active']} armed={s_tip['cursorArmed']}",
            flush=True,
        )

        # Field bridge: play_uid → audio_start. Without this, MSC stays off live path
        # (streamBytes=0, cursorArmed stays false) even after playGuess.
        already_streaming = bool(s_tip.get("stream_active")) or args.producer_s > 0 or args.prefill_kb > 0
        if args.bridge_mimic and not already_streaming:
            print("== bridge-mimic audio_start ==", flush=True)
            pump.send_json(
                {
                    "t": "audio_start",
                    "uid": args.uid,
                    "codec": "mp3",
                    "br": "48k",
                    "cSrc": "lab",
                    "cPath": "bridge_mimic",
                    "cTry": "bridge_mimic",
                }
            )
            pump.drain(0.35)
            pump.send_bin(KIND_ID3, id3("BridgeMimic"), gap_s=0.05)
            series.append(snap(esp, "after_audio_start"))
            print(
                f"  active={series[-1]['stream_active']} ring={series[-1]['ring_size']} "
                f"abs={series[-1]['absBase']}..{series[-1]['absEnd']}",
                flush=True,
            )

        # Post-arm host reads (field HU continues; cursor++ even on underrun)
        post = args.post_head_kib * 1024
        pumped = 0
        pump_budget = max(0, args.post_pump_kb * 1024)
        gate_pauses = 0
        hold_pauses = 0
        gate_paused = False
        hold_paused = False
        host_pause_done = False
        if post > 0:
            if args.producer_gate:
                mode = "gate"
            elif args.cursor_hold and pump_budget:
                mode = "cursor_hold"
            elif pump_budget:
                mode = "free"
            else:
                mode = "silent"
            print(
                f"== post-head {args.post_head_kib} KiB (cursor timeline, pump={mode}) ==",
                flush=True,
            )
            off = need
            done = 0
            i = 0
            while done < post:
                # optional host pause mid-burst (Versuch C)
                if (
                    args.host_pause_s > 0
                    and args.host_pause_after_kib > 0
                    and not host_pause_done
                    and done >= args.host_pause_after_kib * 1024
                ):
                    print(
                        f"== host-pause {args.host_pause_s}s after {args.host_pause_after_kib} KiB ==",
                        flush=True,
                    )
                    series.append(snap(esp, "before_host_pause"))
                    t_hp = time.time() + args.host_pause_s
                    hi = 0
                    while time.time() < t_hp:
                        st_now = series[-1]
                        allow = True
                        if args.cursor_hold:
                            allow = cursor_hold_allows(st_now, args.ring_cap, args.post_pump_chunk)
                            if not allow:
                                if not hold_paused:
                                    hold_pauses += 1
                                hold_paused = True
                            else:
                                hold_paused = False
                        elif args.producer_gate:
                            ring = int(st_now.get("ring_size") or 0)
                            if ring >= args.ring_cap:
                                allow = False
                                if not gate_paused:
                                    gate_pauses += 1
                                gate_paused = True
                            elif ring < args.ring_cap // 2:
                                gate_paused = False
                                allow = True
                            else:
                                allow = not gate_paused
                        if allow and pump_budget > 0 and pumped < pump_budget:
                            chunk_n = min(args.post_pump_chunk, pump_budget - pumped)
                            base = (pumped // max(1, chunk_n) * chunk_n) % max(1, len(mp3) - chunk_n)
                            pump.send_bin(KIND_AUDIO, mp3[base : base + chunk_n], gap_s=0.0005)
                            pumped += chunk_n
                        if hi % 4 == 0:
                            series.append(snap(esp, f"host_pause_{hi}"))
                        hi += 1
                        time.sleep(0.01)
                    series.append(snap(esp, "after_host_pause"))
                    print(
                        f"  pause end: host={series[-1]['hostAbsCursor']} "
                        f"abs={series[-1]['absBase']}..{series[-1]['absEnd']} "
                        f"behind={series[-1]['behind_base']}",
                        flush=True,
                    )
                    host_pause_done = True

                # optional trickle pump before each 4 KiB host read
                if pump_budget > 0 and pumped < pump_budget:
                    st_now = series[-1] if series else snap(esp, "pre_pump")
                    ring = int(st_now.get("ring_size") or 0)
                    allow = True
                    if args.cursor_hold:
                        allow = cursor_hold_allows(st_now, args.ring_cap, args.post_pump_chunk)
                        if not allow:
                            if not hold_paused:
                                hold_pauses += 1
                            hold_paused = True
                        else:
                            hold_paused = False
                    elif args.producer_gate:
                        if ring >= args.ring_cap:
                            if not gate_paused:
                                gate_pauses += 1
                            gate_paused = True
                        elif ring < args.ring_cap // 2:
                            gate_paused = False
                        allow = not gate_paused
                    if allow:
                        chunk_n = min(args.post_pump_chunk, pump_budget - pumped)
                        base = (pumped // max(1, chunk_n) * chunk_n) % max(1, len(mp3) - chunk_n)
                        pump.send_bin(KIND_AUDIO, mp3[base : base + chunk_n], gap_s=0.0005)
                        pumped += chunk_n
                if args.dense:
                    series.append(snap(esp, f"post_head_pre_{i}"))
                dd(args.dev, lba0 + (off + done) // 512, max(1, 4096 // 512))
                done += 4096
                series.append(snap(esp, f"post_head_post_{i}"))
                i += 1
                time.sleep(4.5 / 1000.0)

        # Field 18:07-like: host stopped (or slowed), producer keeps scrolling absBase ahead
        if args.tail_pump_s > 0:
            print(
                f"== tail-pump {args.tail_pump_s}s (no host reads"
                f"{', cursor-hold' if args.cursor_hold else ''}) ==",
                flush=True,
            )
            # ensure stream active
            if not (series and series[-1].get("stream_active")):
                pump.send_json(
                    {
                        "t": "audio_start",
                        "uid": args.uid,
                        "codec": "mp3",
                        "br": "48k",
                        "cSrc": "lab",
                        "cPath": "tail",
                        "cTry": "tail",
                    }
                )
                pump.drain(0.3)
                pump.send_bin(KIND_ID3, id3("TailPump"), gap_s=0.05)
            t_end_tp = time.time() + args.tail_pump_s
            ti = 0
            while time.time() < t_end_tp:
                if args.cursor_hold:
                    st_now = snap(esp, f"tail_chk_{ti}")
                    series.append(st_now)
                else:
                    st_now = series[-1] if series else snap(esp, "tail_pre")
                allow = True
                if args.cursor_hold:
                    allow = cursor_hold_allows(st_now, args.ring_cap, args.tail_pump_chunk)
                    if not allow:
                        if not hold_paused:
                            hold_pauses += 1
                        hold_paused = True
                    else:
                        hold_paused = False
                if allow:
                    base = (ti * args.tail_pump_chunk) % max(1, len(mp3) - args.tail_pump_chunk)
                    pump.send_bin(KIND_AUDIO, mp3[base : base + args.tail_pump_chunk], gap_s=0.002)
                    pumped += args.tail_pump_chunk
                if (not args.cursor_hold and ti % 8 == 0) or (args.cursor_hold and not allow and ti % 16 == 0):
                    if not args.cursor_hold:
                        series.append(snap(esp, f"tail_pump_{ti}"))
                ti += 1
                if not allow:
                    time.sleep(0.01)
            series.append(snap(esp, "after_tail_pump"))
            print(
                f"  after tail: host={series[-1]['hostAbsCursor']} "
                f"abs={series[-1]['absBase']}..{series[-1]['absEnd']} "
                f"behind={series[-1]['behind_base']} live={series[-1]['liveBytes']} "
                f"hold_pauses={hold_pauses}",
                flush=True,
            )

        t_end = time.time() + 2
        while time.time() < t_end:
            series.append(snap(esp, "tail"))
            time.sleep(0.15)

        s_last = series[-1]
        print(
            f"  guess={s_last['playGuessCount']} play={s_last['playingUid']} "
            f"armed={s_last['cursorArmed']} host={s_last['hostAbsCursor']} "
            f"abs={s_last['absBase']}..{s_last['absEnd']} live={s_last['liveBytes']} "
            f"behind={s_last['behind_base']} resync={s_last['headResyncs']} "
            f"sb={s_last['streamBytes']} und={s_last['underruns']} "
            f"pumped={pumped} gate_pauses={gate_pauses} hold_pauses={hold_pauses}",
            flush=True,
        )
    finally:
        try:
            pump.send_json({"t": "audio_stop"})
        except Exception:
            pass
        pump.close()

    (out / "series.jsonl").write_text("\n".join(json.dumps(r) for r in series) + "\n")
    arm_tx = find_arm_transition(series)
    settle = series[0] if series else {}
    final = series[-1] if series else {}

    report = {
        "label": args.label or f"prep={args.prep} mid_kib={args.mid_kib} prod_s={args.producer_s} prefill_kb={args.prefill_kb}",
        "prep": prep_log,
        "geometry": {"lba0": lba0 if "lba0" in dir() else None, "head_need": need if "need" in dir() else None},
        "arm_transition": arm_tx,
        "at_guess": {
            "playGuessCount": final.get("playGuessCount"),
            "playingUid": final.get("playingUid"),
            "hostAbsCursor": final.get("hostAbsCursor"),
            "absBase": final.get("absBase"),
            "absEnd": final.get("absEnd"),
            "liveBytes": final.get("liveBytes"),
            "in_window": final.get("in_window"),
            "behind_base": final.get("behind_base"),
            "streamBytes": final.get("streamBytes"),
            "underruns": final.get("underruns"),
        },
        "field_compare_253952": {
            "hostAbs": final.get("hostAbsCursor"),
            "is_62_sectors": (final.get("hostAbsCursor") or 0) == 253952,
            "host_eq_streamBytes": final.get("hostAbsCursor") == final.get("streamBytes"),
            "host_eq_underruns": final.get("hostAbsCursor") == final.get("underruns"),
            "sectors_4k": (final.get("hostAbsCursor") or 0) // 4096,
        },
        "bridge_mimic": bool(args.bridge_mimic),
        "producer_gate": bool(args.producer_gate),
        "cursor_hold": bool(args.cursor_hold),
        "post_pump_kb": args.post_pump_kb,
        "pumped_bytes": pumped,
        "gate_pauses": gate_pauses,
        "hold_pauses": hold_pauses,
        "settle_cursorArmed": settle.get("cursorArmed"),
        "n_samples": len(series),
        "live_summary": {
            "max_live": max((int(r.get("liveBytes") or 0) for r in series), default=0),
            "final_live": final.get("liveBytes"),
            "max_behind_base": max((int(r.get("behind_base") or 0) for r in series), default=0),
            "final_behind_base": final.get("behind_base"),
            "max_absBase": max((int(r.get("absBase") or 0) for r in series), default=0),
            "pass_streaming": (
                int(final.get("underruns") or 0) == 0
                and int(final.get("liveBytes") or 0) > 0
                and int(final.get("behind_base") or 0) == 0
            ),
        },
    }
    (out / "REPORT.json").write_text(json.dumps(report, indent=2))

    md = [
        "# Lab Arm-Timeline (P0)",
        "",
        f"**Label:** `{report['label']}` · **Out:** `{out}`",
        "",
        f"**Prep:** `{args.prep}` · serial `{prep_log.get('serial_after')}`",
        "",
        "## Arm-Übergang",
        f"```json\n{json.dumps(arm_tx, indent=2)}\n```" if arm_tx else "_kein cursorArmed-Übergang in Samples_",
        "",
        "## Endzustand",
        f"- guess={final.get('playGuessCount')} play=`{final.get('playingUid')}`",
        f"- host={final.get('hostAbsCursor')} abs={final.get('absBase')}..{final.get('absEnd')} "
        f"live={final.get('liveBytes')} behind_base={final.get('behind_base')}",
        "",
        "Freeze hält.",
    ]
    (out / "GESAMTBERICHT-ARM-TIMELINE.md").write_text("\n".join(md))
    print(f"OUT={out}", flush=True)
    print(json.dumps({"arm_transition": arm_tx, "at_guess": report["at_guess"]}, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

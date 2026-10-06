#!/usr/bin/env python3
"""Lab: asynchronous producer vs host (no pump↔read coupling).

GPT Versuch B after cursor-hold PASS: prove Prefill+Pace+Hold without
the artificial schedule pump(); read(); pump(); read().

Producer thread pumps at --pump-bps (independent).
Main thread issues MSC reads at --host-gap-ms (independent).
Optional --cursor-hold pauses producer when absEnd would outrun hostAbs+cap.

Example:
  sg disk -c 'python3 tools/m3_lab_async_producer.py --pump-bps 900000 --cursor-hold'
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
FRAME_MAX_DEFAULT = 512


def snap(esp: str, mark: str = "", retries: int = 4) -> dict:
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            st = http_json(f"{esp}/api/status", timeout=8)
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
                "playingUid": st.get("playingUid") or "",
                "playGuessCount": int(m.get("playGuessCount") or 0),
                "stream_active": bool(s.get("active")),
                "cursorArmed": bool(s.get("cursorArmed")),
                "ring_size": int(s.get("size") or 0),
                "absBase": base,
                "absEnd": end,
                "hostAbsCursor": host,
                "streamBytes": sb,
                "underruns": ud,
                "liveBytes": max(0, sb - ud),
                "behind_base": max(0, base - host) if base else 0,
                "ahead": max(0, host - end) if end else 0,
                "in_window": end > base and base <= host < end,
            }
        except Exception as e:
            last_err = e
            time.sleep(0.2 * (attempt + 1))
    raise RuntimeError(f"snap failed: {last_err}")


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


class PumpTcp:
    def __init__(
        self,
        host: str,
        port: int = 9090,
        frame_max: int = FRAME_MAX_DEFAULT,
        batch_frames: int = 1,
    ):
        self.host = host
        self.port = port
        self.frame_max = max(1, min(int(frame_max), 65535))
        self.batch_frames = max(1, int(batch_frames))
        self.lock = threading.Lock()
        self.s = self._connect()

    def _connect(self) -> socket.socket:
        s = socket.create_connection((self.host, self.port), timeout=8)
        s.settimeout(0.35)
        try:
            s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except OSError:
            pass
        return s

    def reconnect(self) -> None:
        try:
            self.s.close()
        except OSError:
            pass
        self.s = self._connect()

    def close(self) -> None:
        try:
            self.s.close()
        except OSError:
            pass

    def send_json(self, obj: dict) -> None:
        with self.lock:
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
        pending: list[bytes] = []
        frames_in_batch = 0
        while off < len(payload):
            chunk = payload[off : off + self.frame_max]
            hdr = bytes((0x01, kind, len(chunk) & 0xFF, (len(chunk) >> 8) & 0xFF))
            pending.append(hdr + chunk)
            frames_in_batch += 1
            off += len(chunk)
            if frames_in_batch >= self.batch_frames or off >= len(payload):
                with self.lock:
                    self.s.sendall(b"".join(pending))
                pending = []
                frames_in_batch = 0
                if gap_s > 0:
                    time.sleep(gap_s)


def id3(title: str) -> bytes:
    enc = b"\x00" + title.encode("latin-1", errors="replace")[:30]
    frame = b"TIT2" + struct.pack(">I", len(enc)) + b"\x00\x00" + enc
    size = len(frame)
    return b"ID3\x03\x00\x00" + bytes(
        [(size >> 21) & 0x7F, (size >> 14) & 0x7F, (size >> 7) & 0x7F, size & 0x7F]
    ) + frame


def cursor_hold_allows(st: dict, ring_cap: int, next_chunk: int = 0, margin: int = 4096) -> bool:
    """Producer may write only while window cannot fully outrun the host cursor.

    GPT rule: absEnd <= hostAbs + cap  (equiv. absBase <= hostAbs when ring full).
    Before cursor is armed / hostAbs==0: allow fill (Prefill/Pace warm-up).
    margin: stop early so poll lag cannot leave behind_base > 0.
    """
    if not st.get("cursorArmed") or int(st.get("hostAbsCursor") or 0) <= 0:
        return True
    host = int(st.get("hostAbsCursor") or 0)
    abs_base = int(st.get("absBase") or 0)
    abs_end = int(st.get("absEnd") or 0)
    if abs_end <= 0 and abs_base <= 0:
        return True
    m = max(0, int(margin))
    if abs_end + max(0, next_chunk) > host + ring_cap - m:
        return False
    if abs_base + m >= host and abs_end > 0:
        return False
    return True


def soft_rst(esp: str, dev: str) -> dict:
    log: dict = {"steps": []}
    try:
        http_json(f"{esp}/api/restart", method="POST", body=b"{}")
        log["steps"].append("restart")
    except Exception as e:
        log["steps"].append(f"restart_err={e}")
    for _ in range(45):
        try:
            st = http_json(f"{esp}/api/status")
            if st.get("ok"):
                log["serial"] = (st.get("msc") or {}).get("usbSerial")
                log["uptime"] = st.get("uptime")
                break
        except Exception:
            pass
        time.sleep(1)
    time.sleep(2)
    wait_dev(dev)
    return log


def setup_menu(pump: PumpTcp) -> None:
    def _once() -> None:
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

    try:
        _once()
    except (BrokenPipeError, ConnectionResetError, OSError):
        print("  setup_menu: reconnect after broken pipe", flush=True)
        time.sleep(0.5)
        pump.reconnect()
        _once()


class AsyncProducer(threading.Thread):
    def __init__(
        self,
        pump: PumpTcp,
        esp: str,
        mp3: bytes,
        *,
        bps: float,
        chunk: int,
        cursor_hold: bool,
        ring_cap: int,
        stop_evt: threading.Event,
        hold_poll_ms: float = 25.0,
        gap_s: float = 0.0002,
        hold_margin: int = 4096,
    ):
        super().__init__(daemon=True)
        self.pump = pump
        self.esp = esp
        self.mp3 = mp3
        self.bps = bps
        self.chunk = chunk
        self.cursor_hold = cursor_hold
        self.ring_cap = ring_cap
        self.stop_evt = stop_evt
        self.hold_poll_ms = hold_poll_ms
        self.gap_s = gap_s
        self.hold_margin = hold_margin
        self.pumped = 0
        self.hold_pauses = 0
        self.hold_paused = False
        self.ticks = 0
        self.t_start = 0.0
        self.t_stop = 0.0
        self._last_st: dict | None = None
        self._last_st_ts = 0.0
        self._local_abs_end: int | None = None
        self._local_abs_base: int | None = None

    def _status(self) -> dict | None:
        now = time.time()
        if self._last_st is not None and (now - self._last_st_ts) * 1000 < self.hold_poll_ms:
            return self._last_st
        try:
            self._last_st = snap(self.esp, "prod", retries=2)
            self._last_st_ts = time.time()
            # Resync local estimates from ESP truth
            self._local_abs_end = int(self._last_st.get("absEnd") or 0)
            self._local_abs_base = int(self._last_st.get("absBase") or 0)
            return self._last_st
        except Exception:
            return self._last_st

    def run(self) -> None:
        self.t_start = time.time()
        interval = self.chunk / max(1.0, self.bps)
        off = 0
        while not self.stop_evt.is_set():
            t0 = time.time()
            allow = True
            if self.cursor_hold:
                st = self._status()
                if st is not None:
                    # Use local end/base between polls so fast pump cannot overshoot.
                    st_eff = dict(st)
                    if self._local_abs_end is not None:
                        st_eff["absEnd"] = max(int(st.get("absEnd") or 0), self._local_abs_end)
                    if self._local_abs_base is not None:
                        # Ring full: base tracks end - cap
                        end = int(st_eff["absEnd"])
                        cap = self.ring_cap
                        if end >= cap:
                            st_eff["absBase"] = max(int(st.get("absBase") or 0), end - cap)
                    allow = cursor_hold_allows(
                        st_eff, self.ring_cap, self.chunk, margin=self.hold_margin
                    )
                if not allow:
                    if not self.hold_paused:
                        self.hold_pauses += 1
                    self.hold_paused = True
                else:
                    self.hold_paused = False
            if allow:
                n = min(self.chunk, len(self.mp3) - off)
                if n <= 0:
                    off = 0
                    n = min(self.chunk, len(self.mp3))
                try:
                    self.pump.send_bin(KIND_AUDIO, self.mp3[off : off + n], gap_s=self.gap_s)
                    self.pumped += n
                    if self._local_abs_end is not None:
                        self._local_abs_end += n
                    elif self.cursor_hold:
                        self._local_abs_end = n
                    off = (off + n) % max(1, len(self.mp3))
                except OSError:
                    break
            self.ticks += 1
            elapsed = time.time() - t0
            sleep_for = interval - elapsed
            if self.cursor_hold and self.hold_paused:
                time.sleep(max(0.005, min(sleep_for if sleep_for > 0 else 0.01, 0.03)))
            elif sleep_for > 0:
                time.sleep(sleep_for)
        self.t_stop = time.time()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--esp", default="http://192.168.178.88")
    ap.add_argument("--esp-ip", default="192.168.178.88")
    ap.add_argument("--dev", default="/dev/sda")
    ap.add_argument("--uid", default="fav1")
    ap.add_argument("--mp3", default="docs/betrieb/artifacts-2026-10-03-m3/mp3/L1.mp3")
    ap.add_argument("--out", default="")
    ap.add_argument("--soft-rst", action="store_true", default=True)
    ap.add_argument("--no-soft-rst", action="store_true")
    ap.add_argument("--prefill-kb", type=int, default=48)
    ap.add_argument("--post-head-kib", type=int, default=248)
    ap.add_argument("--host-gap-ms", type=float, default=4.5)
    ap.add_argument(
        "--host-slow-after-kib",
        type=int,
        default=0,
        help="After this many KiB of post-head, switch to --host-slow-gap-ms",
    )
    ap.add_argument(
        "--host-slow-gap-ms",
        type=float,
        default=800.0,
        help="Host gap after slow-after (≈5 KiB/s at 4 KiB reads)",
    )
    ap.add_argument("--pump-bps", type=float, default=900000, help="Independent producer bytes/sec")
    ap.add_argument("--pump-chunk", type=int, default=4096)
    ap.add_argument("--frame-max", type=int, default=FRAME_MAX_DEFAULT)
    ap.add_argument("--pump-gap-s", type=float, default=0.0002, help="Sleep between pump TCP frames")
    ap.add_argument("--batch-frames", type=int, default=1, help="Frames per sendall()")
    ap.add_argument("--cursor-hold", action="store_true")
    ap.add_argument("--hold-poll-ms", type=float, default=25.0)
    ap.add_argument("--hold-margin", type=int, default=4096, help="Stop Hold this many bytes early")
    ap.add_argument("--ring-cap", type=int, default=49152)
    ap.add_argument("--host-pause-after-kib", type=int, default=0)
    ap.add_argument("--host-pause-s", type=float, default=0)
    ap.add_argument("--settle-s", type=float, default=2.5)
    ap.add_argument("--label", default="")
    args = ap.parse_args()
    if args.no_soft_rst:
        args.soft_rst = False

    esp = args.esp.rstrip("/")
    stamp = time.strftime("%H%M")
    day = time.strftime("%Y-%m-%d")
    out = Path(args.out) if args.out else Path(
        f"docs/betrieb/artifacts-{day}-lab/lab88-async-prod-{stamp}"
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

    prep = soft_rst(esp, args.dev) if args.soft_rst else {"steps": ["noop"]}
    (out / "prep.json").write_text(json.dumps(prep, indent=2))

    wait_dev(args.dev)
    series: list[dict] = []
    pump = PumpTcp(args.esp_ip, frame_max=args.frame_max, batch_frames=args.batch_frames)
    stop_evt = threading.Event()
    producer: AsyncProducer | None = None
    prod_pumped = 0
    prod_holds = 0
    prod_life_s = 0.0
    burst_s = 0.0
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

        print("== head tip ==", flush=True)
        done = 0
        while done < need:
            dd(args.dev, lba0 + done // 512, max(1, 4096 // 512))
            done += 4096
            time.sleep(args.host_gap_ms / 1000.0)
        for _ in range(12):
            series.append(snap(esp, "tip_poll"))
            if series[-1]["playGuessCount"] > g0 or series[-1]["playingUid"] == args.uid:
                break
            time.sleep(0.1)

        print("== audio_start + prefill ==", flush=True)
        pump.send_json(
            {
                "t": "audio_start",
                "uid": args.uid,
                "codec": "mp3",
                "br": "48k",
                "cSrc": "lab",
                "cPath": "async",
                "cTry": "async",
            }
        )
        pump.drain(0.35)
        pump.send_bin(KIND_ID3, id3("AsyncProd"), gap_s=0.05)
        if args.prefill_kb > 0:
            n = min(len(mp3), args.prefill_kb * 1024)
            pump.send_bin(KIND_AUDIO, mp3[:n], gap_s=0.0005)
            time.sleep(0.25)
        series.append(snap(esp, "after_prefill"))

        # start async producer BEFORE host burst
        producer = AsyncProducer(
            pump,
            esp,
            mp3,
            bps=args.pump_bps,
            chunk=args.pump_chunk,
            cursor_hold=args.cursor_hold,
            ring_cap=args.ring_cap,
            stop_evt=stop_evt,
            gap_s=args.pump_gap_s,
            hold_poll_ms=args.hold_poll_ms,
            hold_margin=args.hold_margin,
        )
        producer.start()
        print(
            f"== async producer bps={args.pump_bps:.0f} hold={args.cursor_hold} "
            f"frame={args.frame_max} gap={args.pump_gap_s} ==",
            flush=True,
        )
        time.sleep(0.05)

        print(f"== host burst {args.post_head_kib} KiB gap={args.host_gap_ms}ms ==", flush=True)
        post = args.post_head_kib * 1024
        done = 0
        i = 0
        pause_done = False
        slow_armed = False
        t_burst0 = time.time()
        while done < post:
            if (
                args.host_pause_s > 0
                and args.host_pause_after_kib > 0
                and not pause_done
                and done >= args.host_pause_after_kib * 1024
            ):
                print(f"== host pause {args.host_pause_s}s ==", flush=True)
                try:
                    series.append(snap(esp, "before_host_pause", retries=2))
                except Exception as e:
                    print(f"  before_pause snap: {e}", flush=True)
                time.sleep(args.host_pause_s)
                try:
                    series.append(snap(esp, "after_host_pause", retries=2))
                    print(
                        f"  pause: host={series[-1]['hostAbsCursor']} "
                        f"abs={series[-1]['absBase']}..{series[-1]['absEnd']} "
                        f"behind={series[-1]['behind_base']}",
                        flush=True,
                    )
                except Exception as e:
                    print(f"  after_pause snap: {e}", flush=True)
                pause_done = True
            if (
                args.host_slow_after_kib > 0
                and not slow_armed
                and done >= args.host_slow_after_kib * 1024
            ):
                try:
                    series.append(snap(esp, "after_fast_burst", retries=2))
                except Exception as e:
                    print(f"  after_fast snap: {e}", flush=True)
                print(
                    f"== host slow gap={args.host_slow_gap_ms}ms after {args.host_slow_after_kib} KiB ==",
                    flush=True,
                )
                slow_armed = True
            dd(args.dev, lba0 + (need + done) // 512, max(1, 4096 // 512))
            done += 4096
            i += 1
            gap = (
                args.host_slow_gap_ms
                if (args.host_slow_after_kib > 0 and done > args.host_slow_after_kib * 1024)
                else args.host_gap_ms
            )
            time.sleep(gap / 1000.0)
        burst_s = time.time() - t_burst0
        try:
            series.append(snap(esp, "after_burst"))
        except Exception as e:
            print(f"  after_burst snap: {e}", flush=True)

        # stop producer BEFORE final status spam
        stop_evt.set()
        if producer is not None:
            producer.join(timeout=3)
            prod_pumped = producer.pumped
            prod_holds = producer.hold_pauses
            if producer.t_start and producer.t_stop:
                prod_life_s = max(0.001, producer.t_stop - producer.t_start)
            producer = None
        time.sleep(0.3)
        try:
            series.append(snap(esp, "final_running"))
        except Exception as e:
            print(f"  final_running snap: {e}", flush=True)
    finally:
        stop_evt.set()
        if producer is not None:
            producer.join(timeout=3)
            prod_pumped = getattr(producer, "pumped", 0)
            prod_holds = getattr(producer, "hold_pauses", 0)
            t0 = getattr(producer, "t_start", 0.0) or 0.0
            t1 = getattr(producer, "t_stop", 0.0) or time.time()
            if t0:
                prod_life_s = max(0.001, t1 - t0)
        try:
            pump.send_json({"t": "audio_stop"})
        except Exception:
            pass
        pump.close()

    try:
        series.append(snap(esp, "final"))
    except Exception as e:
        print(f"  final snap: {e}", flush=True)
        if series:
            series.append({**series[-1], "mark": "final_fallback", "ts": time.time()})
        else:
            raise

    (out / "series.jsonl").write_text("\n".join(json.dumps(r) for r in series) + "\n")

    final = series[-1]
    after_burst = next((r for r in reversed(series) if r.get("mark") == "after_burst"), final)
    after_fast = next((r for r in reversed(series) if r.get("mark") == "after_fast_burst"), None)
    after_pause = next((r for r in reversed(series) if r.get("mark") == "after_host_pause"), None)
    pumped = prod_pumped
    hold_p = prod_holds
    host_bps = (args.post_head_kib * 1024) / max(0.001, burst_s) if burst_s else 0
    # Claude: pumped_bytes is lifetime sum — NEVER divide by burst_s.
    pump_bps_obs = pumped / prod_life_s if prod_life_s > 0 else None
    report = {
        "label": args.label
        or f"async bps={args.pump_bps} hold={args.cursor_hold} pause={args.host_pause_s}",
        "prep": prep,
        "config": {
            "pump_bps": args.pump_bps,
            "pump_chunk": args.pump_chunk,
            "frame_max": args.frame_max,
            "pump_gap_s": args.pump_gap_s,
            "batch_frames": args.batch_frames,
            "host_gap_ms": args.host_gap_ms,
            "host_slow_after_kib": args.host_slow_after_kib,
            "host_slow_gap_ms": args.host_slow_gap_ms,
            "prefill_kb": args.prefill_kb,
            "post_head_kib": args.post_head_kib,
            "cursor_hold": args.cursor_hold,
            "host_pause_after_kib": args.host_pause_after_kib,
            "host_pause_s": args.host_pause_s,
        },
        "rates": {
            "host_bps_observed": host_bps,
            "pump_bps_target": args.pump_bps,
            "pump_target_over_host": (args.pump_bps / host_bps) if host_bps else None,
            "burst_s": burst_s if burst_s else None,
            "producer_life_s": prod_life_s if prod_life_s else None,
            "pumped_bytes": pumped,
            "pump_bps_observed": pump_bps_obs,
            "hold_pauses": hold_p,
            "note": "pump_bps_observed = pumped_bytes / producer_life_s (not burst_s)",
        },
        "after_burst": {
            "hostAbs": after_burst.get("hostAbsCursor"),
            "absBase": after_burst.get("absBase"),
            "absEnd": after_burst.get("absEnd"),
            "live": after_burst.get("liveBytes"),
            "und": after_burst.get("underruns"),
            "behind": after_burst.get("behind_base"),
            "in_window": after_burst.get("in_window"),
        },
        "after_fast_burst": {
            "hostAbs": after_fast.get("hostAbsCursor") if after_fast else None,
            "live": after_fast.get("liveBytes") if after_fast else None,
            "und": after_fast.get("underruns") if after_fast else None,
            "behind": after_fast.get("behind_base") if after_fast else None,
            "in_window": after_fast.get("in_window") if after_fast else None,
        }
        if after_fast
        else None,
        "after_pause": {
            "hostAbs": after_pause.get("hostAbsCursor") if after_pause else None,
            "behind": after_pause.get("behind_base") if after_pause else None,
            "absBase": after_pause.get("absBase") if after_pause else None,
        }
        if after_pause
        else None,
        "final": {
            "hostAbs": final.get("hostAbsCursor"),
            "absBase": final.get("absBase"),
            "absEnd": final.get("absEnd"),
            "live": final.get("liveBytes"),
            "und": final.get("underruns"),
            "behind": final.get("behind_base"),
            "in_window": final.get("in_window"),
        },
        "pass_streaming": (
            int(after_burst.get("underruns") or 0) == 0
            and int(after_burst.get("liveBytes") or 0) > 0
            and int(after_burst.get("behind_base") or 0) == 0
        ),
        "pass_pause": (
            after_pause is None or int(after_pause.get("behind_base") or 0) == 0
        ),
    }
    (out / "REPORT.json").write_text(json.dumps(report, indent=2))

    md = [
        "# Lab Async Producer",
        "",
        f"**Label:** `{report['label']}` · **Out:** `{out}`",
        "",
        f"- pump_target={args.pump_bps:.0f} pump_obs≈{(pump_bps_obs or 0):.0f} "
        f"host_bps≈{host_bps:.0f} hold={args.cursor_hold}",
        f"- life={prod_life_s:.2f}s pumped={pumped} burst={burst_s:.2f}s",
        f"- after_burst: und={after_burst.get('underruns')} live={after_burst.get('liveBytes')} "
        f"behind={after_burst.get('behind_base')} in_win={after_burst.get('in_window')}",
        f"- PASS streaming: {report['pass_streaming']}",
        "",
        "Freeze hält.",
    ]
    (out / "GESAMTBERICHT-ASYNC-PRODUCER.md").write_text("\n".join(md))
    print(f"OUT={out}", flush=True)
    print(json.dumps({k: report[k] for k in ("rates", "after_burst", "after_pause", "pass_streaming", "pass_pause")}, indent=2), flush=True)
    return 0 if report["pass_streaming"] and report["pass_pause"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

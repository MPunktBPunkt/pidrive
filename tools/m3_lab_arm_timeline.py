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
            http_json(f"{esp}/api/restart", method="POST", body=b"{}")
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
        help="After bridge-mimic audio_start, pump this many KiB while post-head reads continue (0=silence/underrun)",
    )
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
            if args.post_pump_kb > 0:
                n = min(len(mp3), args.post_pump_kb * 1024)
                pump.send_bin(KIND_AUDIO, mp3[:n], gap_s=0.002)
            series.append(snap(esp, "after_audio_start"))
            print(
                f"  active={series[-1]['stream_active']} ring={series[-1]['ring_size']} "
                f"abs={series[-1]['absBase']}..{series[-1]['absEnd']}",
                flush=True,
            )

        # Post-arm host reads (field HU continues; cursor++ even on underrun)
        post = args.post_head_kib * 1024
        if post > 0:
            print(f"== post-head {args.post_head_kib} KiB (cursor timeline) ==", flush=True)
            off = need
            if args.dense:
                burst_dense(
                    args.dev,
                    lba0 + off // 512,
                    post,
                    esp,
                    series,
                    "post_head",
                    4096,
                    4.5,
                )
            else:
                # Coarser: 16 KiB chunks with snap; optional trickle pump
                done = 0
                i = 0
                while done < post:
                    if args.post_pump_kb > 0 and i % 4 == 0:
                        pump.send_bin(KIND_AUDIO, mp3[(i * 2048) % max(1, len(mp3) - 2048) : (i * 2048) % max(1, len(mp3) - 2048) + 2048], gap_s=0.001)
                    burst(args.dev, lba0 + (off + done) // 512, 16384, 4096, 4.5)
                    done += 16384
                    series.append(snap(esp, f"post_head_{i}"))
                    i += 1

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
            f"sb={s_last['streamBytes']} und={s_last['underruns']}",
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
        "settle_cursorArmed": settle.get("cursorArmed"),
        "n_samples": len(series),
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

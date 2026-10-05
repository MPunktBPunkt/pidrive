#!/usr/bin/env python3
"""Lab Arm-Diagnose (P2): Head / Mid-cold / Tip vs playDetect + stream state at arm.

Uses field playDetect defaults from status-1541:
  plugWindowMs=500, minSeqBytes=6000, headLbaSlop=12, cooldownMs=5000

Phases (no Detect policy change):
  1) settle — wait indexSettled / quiet after plug window
  2) mid_cold — sequential mid-file reads (expect not_from_head / no guess++)
  3) tip_head — sequential from lba0 ≥ minSeqBytes (expect play.guess)
  4) field_like — mid probe then head tip (status-1541 mscTrace shape)
  Optional: pump prefill before tip to measure size/hostAbs/live at arm

Example:
  sg disk -c 'python3 tools/m3_lab_arm_diag.py --dev /dev/sda'
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


def wait_dev(dev: str, timeout: float = 20.0) -> None:
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

    def send_bin(self, kind: int, payload: bytes, gap_s: float = 0.002) -> None:
        off = 0
        while off < len(payload):
            chunk = payload[off : off + FRAME_MAX]
            hdr = bytes((0x01, kind, len(chunk) & 0xFF, (len(chunk) >> 8) & 0xFF))
            self.s.sendall(hdr + chunk)
            off += len(chunk)
            time.sleep(gap_s)

    def drain(self, seconds: float = 0.5) -> None:
        t_end = time.time() + seconds
        while time.time() < t_end:
            try:
                chunk = self.s.recv(4096)
                if not chunk:
                    break
            except (socket.timeout, ConnectionResetError, BrokenPipeError, OSError):
                continue


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
        "playingUid": st.get("playingUid") or "",
        "playingName": st.get("playingName") or "",
        "phase": m.get("phase"),
        "playGuessCount": m.get("playGuessCount"),
        "playRejectCount": m.get("playRejectCount"),
        "prefetchHits": m.get("prefetchHits"),
        "coldBodyBurstCount": m.get("coldBodyBurstCount"),
        "stream_active": bool(s.get("active")),
        "stream_uid": s.get("uid") or "",
        "cursorArmed": bool(s.get("cursorArmed")),
        "ring_size": int(s.get("size") or 0),
        "absBase": base,
        "absEnd": end,
        "hostAbsCursor": host,
        "streamBytes": sb,
        "underruns": ud,
        "liveBytes": max(0, sb - ud),
        "ahead": max(0, host - end) if end else 0,
        "in_window": end > base and base <= host < end,
        "msSincePlug": m.get("msSincePlug"),
        "msPlugToPlayGuess": m.get("msPlugToPlayGuess"),
        "playDetect": m.get("playDetect"),
        "readOverflow": m.get("readOverflow"),
        "readsEmit": m.get("readsEmit"),
        "readCount": m.get("readCount"),
    }


def burst(dev: str, lba: int, total: int, chunk: int = 4096, gap_ms: float = 4.5) -> None:
    done = 0
    while done < total:
        dd(dev, lba + done // 512, max(1, chunk // 512))
        done += chunk
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--esp", default="http://192.168.178.88")
    ap.add_argument("--esp-ip", default="192.168.178.88")
    ap.add_argument("--dev", default="/dev/sda")
    ap.add_argument("--uid", default="fav1")
    ap.add_argument("--mp3", default="docs/betrieb/artifacts-2026-10-03-m3/mp3/L1.mp3")
    ap.add_argument("--out", default="")
    ap.add_argument("--prefill-kb", type=int, default=0, help="pump audio before tip_head (0=none)")
    ap.add_argument("--settle-s", type=float, default=3.0)
    ap.add_argument("--soft-rst", action="store_true", help="POST /api/restart before run (clean stream)")
    args = ap.parse_args()

    esp = args.esp.rstrip("/")
    stamp = time.strftime("%H%M")
    day = time.strftime("%Y-%m-%d")
    out = Path(args.out) if args.out else Path(
        f"docs/betrieb/artifacts-{day}-lab/lab88-arm-diag-{stamp}"
    )
    out.mkdir(parents=True, exist_ok=True)

    if args.soft_rst:
        print("== soft-rst ==", flush=True)
        try:
            http_json(f"{esp}/api/restart", method="POST", body=b"{}")
        except Exception as e:
            print(f"  restart req: {e}", flush=True)
        # wait online
        for _ in range(40):
            try:
                st = http_json(f"{esp}/api/status")
                if st.get("ok"):
                    print(f"  up={st.get('uptime')} serial={(st.get('msc') or {}).get('usbSerial')}", flush=True)
                    break
            except Exception:
                pass
            time.sleep(1)
        time.sleep(2)

    try:
        http_json(f"{esp}/api/lab/body_seed", method="POST", body=b'{"slot":0,"tag":"off"}')
    except Exception:
        pass
    try:
        http_json(f"{esp}/api/lab/stop", method="POST", body=b"{}")
    except Exception:
        pass
    time.sleep(0.3)

    wait_dev(args.dev)
    series: list[dict] = []
    pump = PumpTcp(args.esp_ip)
    try:
        setup_menu(pump)
        wait_dev(args.dev)
        st = http_json(f"{esp}/api/status")
        (out / "status-00-menu.json").write_text(json.dumps(st, indent=2))
        slot = next(s for s in st["msc"]["slotMap"] if s["uid"] == args.uid)
        lba0 = int(slot["lba0"])
        lba1 = int(slot["lba1"])
        pd = (st.get("msc") or {}).get("playDetect") or {}
        min_seq = int(pd.get("minSeqBytes") or 6000)
        head_slop = int(pd.get("headLbaSlop") or 12)
        print(f"uid={args.uid} lba0={lba0}..{lba1} minSeq={min_seq} headSlop={head_slop}", flush=True)

        # settle past plug window + allow quiet/indexSettled
        print("== settle ==", flush=True)
        time.sleep(args.settle_s)
        # light FAT/dir touch already done by host; optional quiet wait
        series.append(snap(esp, "settle"))

        # --- mid_cold: start well past head slop ---
        print("== mid_cold ==", flush=True)
        mid_lba = lba0 + 64  # 32 KiB into file (> headSlop*512)
        g0 = series[-1]["playGuessCount"]
        r0 = series[-1]["playRejectCount"]
        burst(args.dev, mid_lba, 48 * 1024, 4096, 4.5)
        series.append(snap(esp, "after_mid_cold"))
        s_mid = series[-1]
        print(
            f"  guess {g0}->{s_mid['playGuessCount']} reject {r0}->{s_mid['playRejectCount']} "
            f"cold={s_mid['coldBodyBurstCount']} play={s_mid['playingUid']} "
            f"ring={s_mid['ring_size']} host={s_mid['hostAbsCursor']}",
            flush=True,
        )

        # --- tip_head: arm from head ---
        print("== tip_head ==", flush=True)
        if args.prefill_kb > 0:
            mp3 = Path(args.mp3).read_bytes()
            pump.send_json(
                {
                    "t": "audio_start",
                    "uid": args.uid,
                    "codec": "mp3",
                    "br": "48k",
                    "cSrc": "lab",
                    "cPath": "lab",
                    "cTry": "lab",
                }
            )
            pump.drain(0.4)
            pump.send_bin(KIND_ID3, id3("ArmDiag"), gap_s=0.05)
            n = min(len(mp3), args.prefill_kb * 1024)
            pump.send_bin(KIND_AUDIO, mp3[:n], gap_s=0.002)
            time.sleep(0.4)
            series.append(snap(esp, "after_prefill"))
            print(
                f"  prefill {n}B ring={series[-1]['ring_size']} "
                f"abs={series[-1]['absBase']}..{series[-1]['absEnd']}",
                flush=True,
            )

        g1 = series[-1]["playGuessCount"]
        # enough sequential from head to clear minSeqBytes
        need = max(min_seq + 2048, 12 * 1024)
        series.append(snap(esp, "before_tip_head"))
        burst(args.dev, lba0, need, 4096, 4.5)
        # poll until guess bumps or timeout
        t_end = time.time() + 8
        while time.time() < t_end:
            s = snap(esp, "tip_poll")
            series.append(s)
            if (s["playGuessCount"] or 0) > (g1 or 0) or s["playingUid"] == args.uid:
                break
            time.sleep(0.25)
        s_tip = series[-1]
        print(
            f"  guess {g1}->{s_tip['playGuessCount']} play={s_tip['playingUid']} "
            f"active={s_tip['stream_active']} ring={s_tip['ring_size']} "
            f"host={s_tip['hostAbsCursor']} live={s_tip['liveBytes']} "
            f"ahead={s_tip['ahead']} in={s_tip['in_window']} "
            f"ov={s_tip.get('readOverflow')}",
            flush=True,
        )

        # --- post_tip sustained (prefill path): host continues + producer pace ---
        if args.prefill_kb > 0 and (
            s_tip.get("playingUid") == args.uid
            or (s_tip.get("playGuessCount") or 0) > (g1 or 0)
            or s_tip.get("stream_active")
        ):
            print("== post_tip_prefill_sustain ==", flush=True)
            mp3 = Path(args.mp3).read_bytes()
            # keep feeding while host reads from head onward
            off = need
            live_pos = 0
            live_streak = 0
            max_live = 0
            max_streak = 0
            for i in range(24):
                # ~8 KiB host + ~3 KiB pump per step (~field-ish pace)
                burst(args.dev, lba0 + off // 512, 8192, 4096, 4.5)
                off += 8192
                chunk = mp3[(i * 3072) % max(1, len(mp3) - 3072) : (i * 3072) % max(1, len(mp3) - 3072) + 3072]
                if chunk:
                    pump.send_bin(KIND_AUDIO, chunk, gap_s=0.001)
                s = snap(esp, f"prefill_sustain_{i}")
                series.append(s)
                lv = int(s.get("liveBytes") or 0)
                max_live = max(max_live, lv)
                if lv > 0:
                    live_pos += 1
                    live_streak += 1
                    max_streak = max(max_streak, live_streak)
                else:
                    live_streak = 0
                if i % 4 == 0:
                    print(
                        f"  [{i}] live={lv} ring={s['ring_size']} host={s['hostAbsCursor']} "
                        f"ahead={s['ahead']} in={s['in_window']} ov={s.get('readOverflow')}",
                        flush=True,
                    )
            print(
                f"  sustain max_live={max_live} max_streak={max_streak} "
                f"live_pos={live_pos}/24 ring_at_arm={s_tip['ring_size']}",
                flush=True,
            )

        # --- field_like: mid then head (no stop between) ---
        print("== field_like mid→head ==", flush=True)
        try:
            http_json(f"{esp}/api/lab/stop", method="POST", body=b"{}")
        except Exception:
            pass
        time.sleep(0.5)
        try:
            pump.send_json({"t": "audio_stop"})
        except Exception:
            pass
        try:
            pump.close()
        except Exception:
            pass
        time.sleep(1.0)
        for attempt in range(5):
            try:
                pump = PumpTcp(args.esp_ip)
                setup_menu(pump)
                break
            except OSError as e:
                print(f"  pump reconnect {attempt}: {e}", flush=True)
                time.sleep(1.5)
        else:
            raise SystemExit("pump reconnect failed")
        wait_dev(args.dev)
        time.sleep(2.5)
        series.append(snap(esp, "field_like_settle"))
        g2 = series[-1]["playGuessCount"]
        # mid probe ~237 KiB like field lba 16929-16465
        mid_off_lba = lba0 + (237 * 1024 // 512)
        if mid_off_lba > lba1 - 16:
            mid_off_lba = lba0 + 80
        burst(args.dev, mid_off_lba, 16 * 1024, 4096, 4.5)
        series.append(snap(esp, "field_like_after_mid"))
        burst(args.dev, lba0, need, 4096, 4.5)
        t_end = time.time() + 8
        while time.time() < t_end:
            s = snap(esp, "field_like_tip_poll")
            series.append(s)
            if (s["playGuessCount"] or 0) > (g2 or 0) or s["playingUid"] == args.uid:
                break
            time.sleep(0.25)
        s_fl = series[-1]
        print(
            f"  guess {g2}->{s_fl['playGuessCount']} play={s_fl['playingUid']} "
            f"ring={s_fl['ring_size']} host={s_fl['hostAbsCursor']} live={s_fl['liveBytes']}",
            flush=True,
        )

        # continue burst after arm to see outrun without prefill
        if s_fl["playingUid"] == args.uid or (s_fl["playGuessCount"] or 0) > (g2 or 0):
            print("== post_arm_burst (no prefill) ==", flush=True)
            burst(args.dev, lba0 + need // 512, 128 * 1024, 4096, 4.5)
            # start late pump to mimic producer lag
            mp3 = Path(args.mp3).read_bytes()
            pump.send_json(
                {
                    "t": "audio_start",
                    "uid": args.uid,
                    "codec": "mp3",
                    "br": "48k",
                    "cSrc": "lab",
                    "cPath": "lab",
                    "cTry": "lab",
                }
            )
            pump.drain(0.3)
            pump.send_bin(KIND_ID3, id3("ArmLate"), gap_s=0.05)
            pump.send_bin(KIND_AUDIO, mp3[:80 * 1024], gap_s=0.002)
            for i in range(10):
                series.append(snap(esp, f"post_arm_{i}"))
                time.sleep(0.3)
            print(
                f"  final live={series[-1]['liveBytes']} und={series[-1]['underruns']} "
                f"ahead={series[-1]['ahead']} size={series[-1]['ring_size']}",
                flush=True,
            )
    finally:
        try:
            pump.send_json({"t": "audio_stop"})
        except Exception:
            pass
        pump.close()

    (out / "series.jsonl").write_text("\n".join(json.dumps(r) for r in series) + "\n")
    for _try in range(8):
        try:
            (out / "status-final.json").write_text(json.dumps(http_json(f"{esp}/api/status"), indent=2))
            break
        except Exception as e:
            print(f"  status-final retry: {e}", flush=True)
            time.sleep(1)

    # classify
    by = {r["mark"]: r for r in series if r.get("mark")}
    mid = by.get("after_mid_cold") or {}
    tip = next((r for r in reversed(series) if r["mark"] in ("tip_poll", "before_tip_head") and r["mark"] == "tip_poll"), None)
    tips = [r for r in series if r["mark"] == "tip_poll"]
    tip = tips[-1] if tips else {}
    fls = [r for r in series if r["mark"] == "field_like_tip_poll"]
    fl = fls[-1] if fls else {}
    settle = by.get("settle") or series[0]
    pref = by.get("after_prefill") or {}
    sust = [r for r in series if str(r.get("mark", "")).startswith("prefill_sustain_")]
    live_vals = [int(r.get("liveBytes") or 0) for r in sust]
    max_live = max(live_vals) if live_vals else 0
    # longest streak of live>0
    streak = best = 0
    for v in live_vals:
        if v > 0:
            streak += 1
            best = max(best, streak)
        else:
            streak = 0

    report = {
        "playDetect": settle.get("playDetect"),
        "prefill_kb": args.prefill_kb,
        "mid_cold": {
            "guess_delta": (mid.get("playGuessCount") or 0) - (settle.get("playGuessCount") or 0),
            "reject_delta": (mid.get("playRejectCount") or 0) - (settle.get("playRejectCount") or 0),
            "cold_delta": (mid.get("coldBodyBurstCount") or 0)
            - (settle.get("coldBodyBurstCount") or 0),
            "playingUid": mid.get("playingUid"),
            "snap": mid,
        },
        "tip_head": {
            "armed": tip.get("playingUid") == args.uid
            or (tip.get("playGuessCount") or 0) > (settle.get("playGuessCount") or 0)
            or bool(tip.get("stream_active")),
            "playingUid": tip.get("playingUid"),
            "ring_size_at_arm": tip.get("ring_size"),
            "hostAbs_at_arm": tip.get("hostAbsCursor"),
            "live_at_arm": tip.get("liveBytes"),
            "ahead_at_arm": tip.get("ahead"),
            "stream_active": tip.get("stream_active"),
            "readOverflow": tip.get("readOverflow"),
            "prefill_ring": pref.get("ring_size"),
            "snap": tip,
        },
        "prefill_sustain": {
            "n": len(sust),
            "max_live": max_live,
            "max_live_streak": best,
            "live_positive_samples": sum(1 for v in live_vals if v > 0),
            "pass_sustained": best >= 3 and max_live > 0,
        },
        "field_like": {
            "armed": fl.get("playingUid") == args.uid
            or (fl.get("playGuessCount") or 0) > (settle.get("playGuessCount") or 0),
            "ring_size_at_arm": fl.get("ring_size"),
            "hostAbs_at_arm": fl.get("hostAbsCursor"),
            "live_at_arm": fl.get("liveBytes"),
            "readOverflow": fl.get("readOverflow"),
            "snap": fl,
        },
    }
    (out / "REPORT.json").write_text(json.dumps(report, indent=2))

    md = [
        "# Lab Arm-Diagnose · Prefill-vor-Arm" if args.prefill_kb else "# Lab Arm-Diagnose · P2",
        "",
        f"**ESP:** `{esp}` · **Out:** `{out}` · Seed aus · prefill_kb={args.prefill_kb} · kein Detect-Umbau",
        "",
        "## playDetect",
        f"```json\n{json.dumps(report['playDetect'], indent=2)}\n```",
        "",
        "## Ergebnisse",
        f"- **mid_cold:** guessΔ={report['mid_cold']['guess_delta']} "
        f"rejectΔ={report['mid_cold']['reject_delta']} "
        f"coldΔ={report['mid_cold']['cold_delta']} play=`{report['mid_cold']['playingUid']}`",
        f"- **tip_head:** armed={report['tip_head']['armed']} "
        f"ring={report['tip_head']['ring_size_at_arm']} "
        f"prefill_ring={report['tip_head']['prefill_ring']} "
        f"hostAbs={report['tip_head']['hostAbs_at_arm']} "
        f"live={report['tip_head']['live_at_arm']} "
        f"ov={report['tip_head']['readOverflow']}",
        f"- **prefill_sustain:** max_live={report['prefill_sustain']['max_live']} "
        f"streak={report['prefill_sustain']['max_live_streak']} "
        f"pos={report['prefill_sustain']['live_positive_samples']}/"
        f"{report['prefill_sustain']['n']} "
        f"PASS={report['prefill_sustain']['pass_sustained']}",
        f"- **field_like mid→head:** armed={report['field_like']['armed']} "
        f"ring={report['field_like']['ring_size_at_arm']} "
        f"hostAbs={report['field_like']['hostAbs_at_arm']} "
        f"live={report['field_like']['live_at_arm']}",
        "",
        "## Erwartung",
        "- Mid-only: kein Arm",
        "- Prefill vor Head: ring>0 beim Arm; sustain liveBytes>0 anhaltend",
        "- field_like: Mid→Head armt (Head-Trigger-Form)",
        "",
        "Freeze hält.",
        "",
    ]
    (out / "GESAMTBERICHT-ARM-DIAG.md").write_text("\n".join(md))
    print(f"OUT={out}")
    print(json.dumps(report, indent=2)[:1500])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

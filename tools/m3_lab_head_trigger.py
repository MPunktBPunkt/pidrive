#!/usr/bin/env python3
"""Lab: Head-Trigger repro from field 15:41 (Mid→Head) vs controls.

Field 15:41: mscTrace starts mid (~lba 16929, +237 KiB into Bayern),
then jumps to lba0=16465 and sequential 4 KiB → play.guess=1.
Operator: BOB UI „läuft“, then HU switches to Bayern (no cold tip alone).

Phases (no Detect change, no prefill):
  A) bob_mid     — mid reads on fav2 only (expect no fav1 arm)
  B) mid_then_head — fav1 mid @ +237 KiB then head ≥ minSeq (15:41 shape)
  C) head_only   — fav1 head tip only (positive control)
  D) mid_only    — fav1 mid only (negative control)

Example:
  sg disk -c 'python3 tools/m3_lab_head_trigger.py --dev /dev/sda --soft-rst'
"""
from __future__ import annotations

import argparse
import json
import socket
import subprocess
import time
import urllib.request
from pathlib import Path


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

    def drain(self, seconds: float = 0.5) -> None:
        t_end = time.time() + seconds
        while time.time() < t_end:
            try:
                chunk = self.s.recv(4096)
                if not chunk:
                    break
            except (socket.timeout, ConnectionResetError, BrokenPipeError, OSError):
                continue


def snap(esp: str, mark: str = "") -> dict:
    st = http_json(f"{esp}/api/status")
    m = st.get("msc") or {}
    s = m.get("stream") or st.get("stream") or {}
    sb = int(m.get("streamBytes") or 0)
    ud = int(s.get("underruns") or 0)
    return {
        "ts": time.time(),
        "mark": mark,
        "playingUid": st.get("playingUid") or "",
        "playingName": st.get("playingName") or "",
        "phase": m.get("phase"),
        "playGuessCount": int(m.get("playGuessCount") or 0),
        "playRejectCount": int(m.get("playRejectCount") or 0),
        "coldBodyBurstCount": int(m.get("coldBodyBurstCount") or 0),
        "prefetchHits": int(m.get("prefetchHits") or 0),
        "stream_active": bool(s.get("active")),
        "ring_size": int(s.get("size") or 0),
        "hostAbsCursor": int(s.get("hostAbsCursor") or 0),
        "liveBytes": max(0, sb - ud),
        "readOverflow": m.get("readOverflow"),
        "lastReadLba": m.get("lastReadLba"),
        "msSincePlug": m.get("msSincePlug"),
        "playDetect": m.get("playDetect"),
        "slotBrief": [
            {
                "uid": x.get("uid"),
                "bytes": x.get("bytes"),
                "fromHead": x.get("fromHead"),
                "midFile": x.get("midFile"),
                "lastAgeMs": x.get("lastAgeMs"),
            }
            for x in (m.get("slotMap") or [])
        ],
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


def wait_guess(esp: str, g0: int, series: list, mark: str, uid: str, timeout: float = 6.0) -> dict:
    t_end = time.time() + timeout
    last = series[-1] if series else snap(esp, mark)
    while time.time() < t_end:
        s = snap(esp, mark)
        series.append(s)
        last = s
        if s["playGuessCount"] > g0 or s["playingUid"] == uid:
            break
        time.sleep(0.2)
    return last


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--esp", default="http://192.168.178.88")
    ap.add_argument("--esp-ip", default="192.168.178.88")
    ap.add_argument("--dev", default="/dev/sda")
    ap.add_argument("--uid", default="fav1", help="Bayern-like target")
    ap.add_argument("--bob-uid", default="fav2")
    ap.add_argument("--out", default="")
    ap.add_argument("--soft-rst", action="store_true")
    ap.add_argument("--mid-off-kib", type=int, default=237, help="field 15:41 mid offset")
    ap.add_argument("--settle-s", type=float, default=3.0)
    args = ap.parse_args()

    esp = args.esp.rstrip("/")
    stamp = time.strftime("%H%M")
    day = time.strftime("%Y-%m-%d")
    out = Path(args.out) if args.out else Path(
        f"docs/betrieb/artifacts-{day}-lab/lab88-head-trigger-{stamp}"
    )
    out.mkdir(parents=True, exist_ok=True)

    if args.soft_rst:
        print("== soft-rst ==", flush=True)
        try:
            http_json(f"{esp}/api/restart", method="POST", body=b"{}")
        except Exception as e:
            print(f"  restart: {e}", flush=True)
        for _ in range(40):
            try:
                st = http_json(f"{esp}/api/status")
                if st.get("ok"):
                    print(f"  up={st.get('uptime')} ser={(st.get('msc') or {}).get('usbSerial')}", flush=True)
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
        sm = {s["uid"]: s for s in st["msc"]["slotMap"]}
        bay = sm[args.uid]
        bob = sm[args.bob_uid]
        lba0 = int(bay["lba0"])
        lba1 = int(bay["lba1"])
        bob0 = int(bob["lba0"])
        pd = (st.get("msc") or {}).get("playDetect") or {}
        min_seq = int(pd.get("minSeqBytes") or 6000)
        need = max(min_seq + 2048, 12 * 1024)
        mid_off = args.mid_off_kib * 1024
        mid_lba = lba0 + mid_off // 512
        if mid_lba > lba1 - 32:
            mid_lba = lba0 + 80
        print(
            f"bay={args.uid} {lba0}..{lba1} bob={args.bob_uid} {bob0} "
            f"mid_lba={mid_lba} (+{args.mid_off_kib}KiB) need={need}",
            flush=True,
        )

        print("== settle ==", flush=True)
        time.sleep(args.settle_s)
        series.append(snap(esp, "settle"))
        g_base = series[-1]["playGuessCount"]

        # A) BOB mid only (station activity before switch)
        print("== A bob_mid ==", flush=True)
        g0 = series[-1]["playGuessCount"]
        burst(args.dev, bob0 + 64, 48 * 1024, 4096, 4.5)
        s = wait_guess(esp, g0, series, "after_bob_mid", args.bob_uid, timeout=3)
        print(
            f"  guess {g0}->{s['playGuessCount']} play={s['playingUid']!r} "
            f"rej={s['playRejectCount']} cold={s['coldBodyBurstCount']}",
            flush=True,
        )

        # B) 15:41 shape: mid then immediate head on Bayern (no audio)
        print("== B mid_then_head (15:41) ==", flush=True)
        g0 = series[-1]["playGuessCount"]
        burst(args.dev, mid_lba, 16 * 1024, 4096, 4.5)  # short mid like trace prelude
        series.append(snap(esp, "b_after_mid"))
        burst(args.dev, lba0, need, 4096, 4.5)
        s = wait_guess(esp, g0, series, "b_tip_poll", args.uid)
        armed_b = s["playGuessCount"] > g0 or s["playingUid"] == args.uid
        print(
            f"  guess {g0}->{s['playGuessCount']} play={s['playingUid']!r} armed={armed_b} "
            f"ring={s['ring_size']} live={s['liveBytes']} last={s['lastReadLba']}",
            flush=True,
        )

        # reset stream/play via lab stop + audio_stop (keep MSC map)
        try:
            http_json(f"{esp}/api/lab/stop", method="POST", body=b"{}")
        except Exception:
            pass
        pump.send_json({"t": "audio_stop"})
        cooldown = float((series[-1].get("playDetect") or {}).get("cooldownMs") or 5000) / 1000.0
        wait_cd = cooldown + 1.0
        print(f"  cooldown wait {wait_cd:.1f}s", flush=True)
        time.sleep(wait_cd)
        series.append(snap(esp, "after_stop"))

        # C) head only positive control
        print("== C head_only ==", flush=True)
        g0 = series[-1]["playGuessCount"]
        burst(args.dev, lba0, need, 4096, 4.5)
        s = wait_guess(esp, g0, series, "c_tip_poll", args.uid)
        armed_c = s["playGuessCount"] > g0 or s["playingUid"] == args.uid
        print(
            f"  guess {g0}->{s['playGuessCount']} play={s['playingUid']!r} armed={armed_c} "
            f"ring={s['ring_size']}",
            flush=True,
        )

        try:
            http_json(f"{esp}/api/lab/stop", method="POST", body=b"{}")
        except Exception:
            pass
        pump.send_json({"t": "audio_stop"})
        print(f"  cooldown wait {wait_cd:.1f}s", flush=True)
        time.sleep(wait_cd)
        series.append(snap(esp, "after_stop_c"))

        # D) mid only negative
        print("== D mid_only ==", flush=True)
        g0 = series[-1]["playGuessCount"]
        burst(args.dev, mid_lba, 48 * 1024, 4096, 4.5)
        s = wait_guess(esp, g0, series, "d_after_mid", args.uid, timeout=3)
        armed_d = s["playGuessCount"] > g0 or s["playingUid"] == args.uid
        print(
            f"  guess {g0}->{s['playGuessCount']} play={s['playingUid']!r} armed={armed_d} "
            f"rejΔ? rej={s['playRejectCount']}",
            flush=True,
        )
    finally:
        try:
            pump.send_json({"t": "audio_stop"})
        except Exception:
            pass
        pump.close()

    (out / "series.jsonl").write_text("\n".join(json.dumps(r) for r in series) + "\n")
    for _ in range(6):
        try:
            (out / "status-final.json").write_text(json.dumps(http_json(f"{esp}/api/status"), indent=2))
            break
        except Exception as e:
            print(f"  status-final: {e}", flush=True)
            time.sleep(1)

    def last(mark_prefix: str) -> dict:
        hits = [r for r in series if str(r.get("mark", "")).startswith(mark_prefix) or r.get("mark") == mark_prefix]
        return hits[-1] if hits else {}

    settle = last("settle")
    a = last("after_bob_mid")
    b_mid = last("b_after_mid")
    b = last("b_tip_poll")
    c = last("c_tip_poll")
    d = last("d_after_mid")

    def armed(s: dict, g0: int) -> bool:
        return bool(s) and (s.get("playGuessCount", 0) > g0 or s.get("playingUid") == args.uid)

    g_settle = settle.get("playGuessCount", 0)
    g_a = a.get("playGuessCount", g_settle)
    g_b0 = b_mid.get("playGuessCount", g_a)  # after mid before head tip start — use a as baseline for B
    # B baseline = after bob / before B tip: use after_bob_mid
    report = {
        "playDetect": settle.get("playDetect"),
        "geometry": {
            "uid": args.uid,
            "bob_uid": args.bob_uid,
            "mid_off_kib": args.mid_off_kib,
            "min_seq_need": need,
        },
        "A_bob_mid": {
            "guess_delta": (a.get("playGuessCount") or 0) - g_settle,
            "playingUid": a.get("playingUid"),
            "armed_target": a.get("playingUid") == args.uid,
            "snap": a,
        },
        "B_mid_then_head": {
            "armed": (b.get("playGuessCount") or 0) > g_a or b.get("playingUid") == args.uid,
            "guess_delta": (b.get("playGuessCount") or 0) - g_a,
            "playingUid": b.get("playingUid"),
            "ring_at_arm": b.get("ring_size"),
            "live_at_arm": b.get("liveBytes"),
            "snap": b,
        },
        "C_head_only": {
            "playingUid": c.get("playingUid"),
            "ring_at_arm": c.get("ring_size"),
            "snap": c,
        },
        "D_mid_only": {
            "playingUid": d.get("playingUid"),
            "guess": d.get("playGuessCount"),
            "snap": d,
        },
    }
    after_stops = [r for r in series if r.get("mark") == "after_stop"]
    g_c0 = after_stops[0]["playGuessCount"] if after_stops else g_a
    report["C_head_only"]["armed"] = (c.get("playGuessCount") or 0) > g_c0 or c.get("playingUid") == args.uid
    report["C_head_only"]["guess_delta"] = (c.get("playGuessCount") or 0) - g_c0

    before_d = None
    for r in series:
        if r.get("mark") == "d_after_mid":
            break
        before_d = r
    g_before_d = (before_d or {}).get("playGuessCount", 0)
    report["D_mid_only"]["armed"] = (d.get("playGuessCount") or 0) > g_before_d or d.get("playingUid") == args.uid
    report["D_mid_only"]["guess_delta"] = (d.get("playGuessCount") or 0) - g_before_d

    report["summary"] = {
        "B_reproduces_1541_shape": report["B_mid_then_head"]["armed"],
        "C_head_positive": report["C_head_only"]["armed"],
        "D_mid_negative": not report["D_mid_only"]["armed"],
        "pass_head_trigger_lab": report["B_mid_then_head"]["armed"]
        and report["C_head_only"]["armed"]
        and not report["D_mid_only"]["armed"],
    }
    (out / "REPORT.json").write_text(json.dumps(report, indent=2))

    md = [
        "# Lab Head-Trigger · 15:41 Mid→Head",
        "",
        f"**ESP:** `{esp}` · **Out:** `{out}` · Seed aus · kein Prefill · kein Detect-Umbau",
        "",
        "## Ergebnisse",
        f"- **A bob_mid:** guessΔ={report['A_bob_mid']['guess_delta']} play=`{report['A_bob_mid']['playingUid']}`",
        f"- **B mid→head (15:41):** armed={report['B_mid_then_head']['armed']} "
        f"guessΔ={report['B_mid_then_head']['guess_delta']} "
        f"ring={report['B_mid_then_head']['ring_at_arm']} live={report['B_mid_then_head']['live_at_arm']}",
        f"- **C head_only:** armed={report['C_head_only']['armed']} guessΔ={report['C_head_only']['guess_delta']}",
        f"- **D mid_only:** armed={report['D_mid_only']['armed']} guessΔ={report['D_mid_only']['guess_delta']}",
        "",
        f"**PASS:** {report['summary']['pass_head_trigger_lab']}",
        "",
        "Freeze hält.",
        "",
    ]
    (out / "GESAMTBERICHT-HEAD-TRIGGER.md").write_text("\n".join(md))
    print(f"OUT={out}", flush=True)
    print(json.dumps(report["summary"], indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

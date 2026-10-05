#!/usr/bin/env python3
"""Lab: HU-mimic of field 2026-10-05 15:41 Bayern window-miss.

Field profile (status-1541):
  - Ring cap 49152; HU body ~4 KiB @ ~4–5 ms gap (mscTrace)
  - stream.active + cursorArmed; hostAbs ahead of absEnd
  - underruns == streamBytes → liveBytes=0

Scenarios:
  A) race — tiny prefill, immediate mid-file 4KiB sequential burst (~256KiB)
  B) fill_then_pace — fill ring, head+sequential paced with producer
  C) fill_then_outrun — fill ring, then fast mid-file burst past window

Example:
  sg disk -c 'python3 tools/m3_lab_hu_mimic_1541.py --dev /dev/sda --scenario all'
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
KIND_AUDIO = 0x55
KIND_ID3 = 0x56


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
            except socket.timeout:
                continue
            except (ConnectionResetError, BrokenPipeError, OSError):
                break


def id3(title: str) -> bytes:
    enc = b"\x00" + title.encode("latin-1", errors="replace")[:30]
    frame = b"TIT2" + struct.pack(">I", len(enc)) + b"\x00\x00" + enc
    size = len(frame)
    header = b"ID3\x03\x00\x00" + bytes(
        [(size >> 21) & 0x7F, (size >> 14) & 0x7F, (size >> 7) & 0x7F, size & 0x7F]
    )
    return header + frame


def stream_snap(status: dict) -> dict:
    m = status.get("msc") or {}
    st = m.get("stream") or status.get("stream") or {}
    sb = int(m.get("streamBytes") or 0)
    ud = int(st.get("underruns") or 0)
    base = int(st.get("absBase") or 0)
    end = int(st.get("absEnd") or 0)
    host = int(st.get("hostAbsCursor") or 0)
    return {
        "ts": time.time(),
        "active": bool(st.get("active")),
        "uid": st.get("uid") or "",
        "cursorArmed": bool(st.get("cursorArmed")),
        "absBase": base,
        "absEnd": end,
        "hostAbsCursor": host,
        "size": int(st.get("size") or 0),
        "cap": int(st.get("cap") or 0),
        "streamBytes": sb,
        "underruns": ud,
        "liveBytes": max(0, sb - ud),
        "ahead": max(0, host - end) if end else 0,
        "in_window": end > base and base <= host < end,
        "play": status.get("playingUid") or "",
        "guess": m.get("playGuessCount"),
        "reject": m.get("playRejectCount"),
    }


def paced_burst(
    dev: str,
    lba0: int,
    file_off: int,
    total_bytes: int,
    chunk: int,
    gap_ms: float,
    esp: str,
    series: list,
    sample_every: int = 4,
    pump: PumpTcp | None = None,
    audio: bytearray | None = None,
    pump_each: int = 0,
) -> None:
    sectors = max(1, chunk // 512)
    done = 0
    step = 0
    while done < total_bytes:
        off = file_off + done
        lba = lba0 + off // 512
        dd(dev, lba, sectors)
        done += chunk
        step += 1
        if pump and audio is not None and pump_each > 0 and step % 2 == 0:
            take = bytes(audio[:pump_each])
            del audio[:pump_each]
            if take:
                pump.send_bin(KIND_AUDIO, take, gap_s=0.0004)
        if step % sample_every == 0 or done >= total_bytes:
            series.append(stream_snap(http_json(f"{esp}/api/status")))
        time.sleep(gap_ms / 1000.0)


def setup_menu_and_start(pump: PumpTcp, uid: str, mp3: bytes) -> None:
    pump.send_json({"t": "hello", "ver": 1})
    pump.drain(1.0)
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
    pump.drain(1.5)
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
    pump.drain(0.5)
    pump.send_bin(KIND_ID3, id3("HU-Mimic-1541"), gap_s=0.05)
    time.sleep(0.15)
    # caller feeds audio


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--esp", default="http://192.168.178.88")
    ap.add_argument("--esp-ip", default="192.168.178.88")
    ap.add_argument("--dev", default="/dev/sda")
    ap.add_argument("--scenario", choices=("A", "B", "C", "all"), default="all")
    ap.add_argument("--out", default="")
    ap.add_argument("--uid", default="fav1")
    ap.add_argument(
        "--mp3",
        default="docs/betrieb/artifacts-2026-10-03-m3/mp3/L1.mp3",
    )
    ap.add_argument(
        "--field-status",
        default="docs/betrieb/artifacts-2026-10-05-feld/feld-av-abend-1530/"
        "status-1541-bayern-stream-active-no-audio.json",
    )
    ap.add_argument("--gap-ms", type=float, default=4.5)
    args = ap.parse_args()

    esp = args.esp.rstrip("/")
    stamp = time.strftime("%H%M")
    day = time.strftime("%Y-%m-%d")
    out = Path(args.out) if args.out else Path(
        f"docs/betrieb/artifacts-{day}-lab/lab88-hu-mimic-{stamp}"
    )
    out.mkdir(parents=True, exist_ok=True)

    mp3_path = Path(args.mp3)
    if not mp3_path.is_file():
        raise SystemExit(f"missing mp3: {mp3_path}")
    mp3_all = mp3_path.read_bytes()

    field = {"gap_ms": args.gap_ms, "xfer": 4096, "ring_cap": 49152}
    if Path(args.field_status).is_file():
        fs = json.loads(Path(args.field_status).read_text())
        fst = (fs.get("msc") or {}).get("stream") or fs.get("stream") or {}
        field.update(
            {
                "field_hostAbs": fst.get("hostAbsCursor"),
                "field_absBase": fst.get("absBase"),
                "field_absEnd": fst.get("absEnd"),
                "field_underruns": fst.get("underruns"),
                "field_streamBytes": (fs.get("msc") or {}).get("streamBytes"),
                "field_size": fst.get("size"),
            }
        )

    try:
        http_json(f"{esp}/api/lab/body_seed", method="POST", body=b'{"slot":0,"tag":"off"}')
    except Exception:
        pass
    http_json(f"{esp}/api/lab/stop", method="POST", body=b"{}")
    time.sleep(0.3)

    wait_dev(args.dev)
    scenarios = ["A", "B", "C"] if args.scenario == "all" else [args.scenario]
    report: dict = {"field_profile": field, "scenarios": {}, "mp3": str(mp3_path)}

    for sc in scenarios:
        print(f"\n== scenario {sc} ==", flush=True)
        series: list[dict] = []
        http_json(f"{esp}/api/lab/stop", method="POST", body=b"{}")
        time.sleep(0.35)

        # settle between scenarios (ESP pump peer can reset)
        time.sleep(1.0)
        pump = PumpTcp(args.esp_ip)
        audio = bytearray(mp3_all)
        try:
            setup_menu_and_start(pump, args.uid, bytes(audio))
            wait_dev(args.dev)
            st = http_json(f"{esp}/api/status")
            (out / f"status-{sc}-menu.json").write_text(json.dumps(st, indent=2))
            sm = st.get("msc", {}).get("slotMap") or []
            hit = next((s for s in sm if s.get("uid") == args.uid), None)
            if not hit:
                raise SystemExit(f"uid {args.uid} missing in slotMap: {[s.get('uid') for s in sm]}")
            lba0 = int(hit["lba0"])
            print(f"  lba0={lba0} serial={(st.get('msc') or {}).get('usbSerial')}", flush=True)

            mid_off = 32 * 1024

            if sc == "A":
                # tiny prefill then race (field-like: cursor ahead, all underrun)
                take = bytes(audio[:4096])
                del audio[:4096]
                pump.send_bin(KIND_AUDIO, take, gap_s=0.001)
                time.sleep(0.05)
                series.append(stream_snap(http_json(f"{esp}/api/status")))
                paced_burst(
                    args.dev,
                    lba0,
                    mid_off,
                    256 * 1024,
                    4096,
                    args.gap_ms,
                    esp,
                    series,
                    sample_every=4,
                    pump=pump,
                    audio=audio,
                    pump_each=512,
                )
                paced_burst(
                    args.dev,
                    lba0,
                    mid_off + 256 * 1024,
                    48 * 1024,
                    4096,
                    args.gap_ms,
                    esp,
                    series,
                    sample_every=4,
                    pump=pump,
                    audio=audio,
                    pump_each=1024,
                )

            elif sc == "B":
                feed = min(len(audio), 220 * 1024)
                print(f"  feed {feed}", flush=True)
                pump.send_bin(KIND_AUDIO, bytes(audio[:feed]), gap_s=0.002)
                del audio[:feed]
                time.sleep(0.6)
                series.append(stream_snap(http_json(f"{esp}/api/status")))
                s0 = series[-1]
                print(f"  window {s0['absBase']}..{s0['absEnd']} size={s0['size']}", flush=True)
                # head then sequential with paced producer
                paced_burst(
                    args.dev,
                    lba0,
                    0,
                    12 * 1024,
                    4096,
                    args.gap_ms,
                    esp,
                    series,
                    sample_every=2,
                    pump=pump,
                    audio=audio,
                    pump_each=1536,
                )
                paced_burst(
                    args.dev,
                    lba0,
                    12 * 1024,
                    96 * 1024,
                    4096,
                    args.gap_ms + 3,
                    esp,
                    series,
                    sample_every=4,
                    pump=pump,
                    audio=audio,
                    pump_each=2048,
                )

            else:  # C
                feed = min(len(audio), 180 * 1024)
                pump.send_bin(KIND_AUDIO, bytes(audio[:feed]), gap_s=0.002)
                del audio[:feed]
                time.sleep(0.5)
                series.append(stream_snap(http_json(f"{esp}/api/status")))
                paced_burst(
                    args.dev,
                    lba0,
                    mid_off,
                    320 * 1024,
                    4096,
                    1.0,
                    esp,
                    series,
                    sample_every=4,
                    pump=pump,
                    audio=audio,
                    pump_each=256,
                )

            final = stream_snap(http_json(f"{esp}/api/status"))
            series.append(final)
        finally:
            try:
                pump.send_json({"t": "audio_stop"})
            except Exception:
                pass
            pump.close()

        (out / f"series-{sc}.jsonl").write_text("\n".join(json.dumps(r) for r in series) + "\n")
        (out / f"status-{sc}-final.json").write_text(
            json.dumps(http_json(f"{esp}/api/status"), indent=2)
        )

        max_live = max((r["liveBytes"] for r in series), default=0)
        max_ahead = max((r["ahead"] for r in series), default=0)
        any_in = any(r["in_window"] for r in series)
        und_eq = final["streamBytes"] > 0 and final["streamBytes"] == final["underruns"]
        cls = {
            "max_liveBytes": max_live,
            "max_ahead": max_ahead,
            "any_in_window": any_in,
            "final": final,
            "underruns_eq_streamBytes": und_eq,
            "mirrors_1541": bool(und_eq and max_ahead > 0 and max_live == 0),
        }
        report["scenarios"][sc] = cls
        print(
            f"  max_live={max_live} max_ahead={max_ahead} any_in={any_in} "
            f"und==sb={und_eq} mirrors_1541={cls['mirrors_1541']}",
            flush=True,
        )

    (out / "REPORT.json").write_text(json.dumps(report, indent=2))
    lines = [
        "# Lab HU-Mimic Feld 15:41 · Fenster-Miss",
        "",
        f"**ESP:** `{esp}` · **Dev:** `{args.dev}` · **Artefakt:** `{out}`",
        f"**FW/Profil:** Ring 48 KiB · HU 4 KiB @ {args.gap_ms} ms · Seed aus",
        "",
        "## Feldreferenz (status-1541)",
        "```",
        json.dumps(field, indent=2),
        "```",
        "",
        "## Szenarien",
        "",
        "| Sc | max_live | max_ahead | any_in | und==sb | mirrors_1541 |",
        "|----|----------|-----------|--------|---------|--------------|",
    ]
    for sc, cls in report["scenarios"].items():
        lines.append(
            f"| {sc} | {cls['max_liveBytes']} | {cls['max_ahead']} | {cls['any_in_window']} "
            f"| {cls['underruns_eq_streamBytes']} | {cls['mirrors_1541']} |"
        )
    lines += [
        "",
        "## Semantik",
        "Siehe [`STREAM-COUNTER-SEMANTIK.md`](STREAM-COUNTER-SEMANTIK.md) — "
        "Cursor steigt auch bei Underrun; Outside bleibt Outside ohne Head-Resync.",
        "",
        "## Freeze",
        "Kein Lock/Detect/Ring-Umbau. Sequenz-GO gesperrt.",
        "",
    ]
    (out / "GESAMTBERICHT-HU-MIMIC-1541.md").write_text("\n".join(lines) + "\n")
    print(f"OUT={out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""M3 Lab: paced read across PDMK markers — correlate LBA timeline vs marker index.

Requires stream OFF (silence path). Lab-Host only — not NBT A–E.

Example:
  python3 tools/m3_lab_marker_pace.py --esp http://192.168.178.88 \\
    --host root@192.168.178.108 --seconds 90
"""
from __future__ import annotations

import argparse
import json
import struct
import subprocess
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HEAD = 252
FRAME = 156
INTERVAL = 180000
MAGIC = b"PDMK"


def http_json(url: str, method: str = "GET", body: bytes | None = None):
    req = urllib.request.Request(url, data=body, method=method)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode())


def ssh(host: str, cmd: str) -> bytes:
    return subprocess.check_output(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", host, cmd]
    )


def marker_file_off(idx: int) -> int:
    body = (idx * INTERVAL // FRAME) * FRAME
    return HEAD + body


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--esp", default="http://192.168.178.88")
    ap.add_argument("--host", default="root@192.168.178.108")
    ap.add_argument("--dev", default="/dev/sda")
    ap.add_argument("--seconds", type=float, default=90.0)
    ap.add_argument("--kib-s", type=float, default=6.0)
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    esp = args.esp.rstrip("/")
    stamp = datetime.now().strftime("%H%M%S")
    day = datetime.now().strftime("%Y-%m-%d")
    out = Path(args.out) if args.out else Path(f"docs/betrieb/artifacts-{day}-m3/lab88-marker-pace-{stamp}")
    out.mkdir(parents=True, exist_ok=True)

    try:
        http_json(f"{esp}/api/lab/stop", method="POST", body=b"{}")
    except Exception:
        pass
    time.sleep(0.5)
    st = http_json(f"{esp}/api/status")
    if (st.get("msc") or {}).get("stream", {}).get("active"):
        print("WARN stream still active — markers may be wrong")
    slot = next(s for s in st["msc"]["slotMap"] if s["uid"] == "fav0")
    lba0, lba1 = int(slot["lba0"]), int(slot["lba1"])
    slot_bytes = (lba1 - lba0 + 1) * 512
    # Cover markers reachable in this pace window (+2 slack), capped by slot size.
    bytes_reach = int(args.seconds * args.kib_s * 1024) + 2 * INTERVAL
    nmark = min(slot_bytes // INTERVAL + 1, max(4, bytes_reach // INTERVAL + 2))

    markers = []
    for i in range(nmark):
        fo = marker_file_off(i)
        if fo + 10 >= slot_bytes:
            break
        markers.append({"idx": i, "file_off": fo, "lba": lba0 + fo // 512})

    # verify first/last mark present before pace
    def read_stamp(idx: int) -> bytes:
        fo = marker_file_off(idx) + 4
        lba = lba0 + fo // 512
        within = fo % 512
        blob = ssh(
            args.host,
            f"dd if={args.dev} bs=512 skip={lba} count=2 iflag=direct status=none 2>/dev/null",
        )
        return blob[within : within + 6]

    pre = []
    for m in markers[:3]:
        got = read_stamp(m["idx"])
        pre.append({"idx": m["idx"], "ok": got == MAGIC + struct.pack(">H", m["idx"]), "got": got.hex()})

    # paced consume; record (t, lba, file_off, nearest_marker)
    bytes_s = args.kib_s * 1024.0
    script = (
        "import time, subprocess, json\n"
        f"lba0,lba1,seconds,bytes_s,dev={lba0},{lba1},{float(args.seconds)},{bytes_s},{args.dev!r}\n"
        "lba=lba0\n"
        "t0=time.time()\n"
        "rows=[]\n"
        "while time.time()-t0 < seconds:\n"
        "    if lba>lba1: lba=lba0\n"
        "    cnt=min(8, lba1-lba+1)\n"
        "    subprocess.check_call(['dd','if=%s'%dev,'bs=512','skip=%d'%lba,'count=%d'%cnt,"
        "'iflag=direct','status=none','of=/dev/null'], stderr=subprocess.DEVNULL)\n"
        "    fo=(lba-lba0)*512\n"
        "    rows.append({'t':round(time.time()-t0,3),'lba':lba,'file_off':fo})\n"
        "    lba+=cnt\n"
        "    time.sleep((cnt*512)/bytes_s)\n"
        "print(json.dumps(rows))\n"
    )
    raw = ssh(args.host, "python3 - <<'PY'\n" + script + "PY").decode()
    rows = json.loads(raw)
    (out / "pace_rows.json").write_text(json.dumps(rows), encoding="utf-8")

    # annotate nearest marker behind cursor
    hits = []
    seen = set()
    for r in rows:
        fo = r["file_off"]
        behind = [m for m in markers if m["file_off"] <= fo]
        nearest = behind[-1] if behind else None
        if nearest and nearest["idx"] not in seen and fo >= nearest["file_off"]:
            # crossed this marker
            seen.add(nearest["idx"])
            hits.append({"t": r["t"], "marker": nearest["idx"], "file_off": fo, "lba": r["lba"]})

    # expected time at 6 KiB/s to each marker
    expected = []
    for m in markers:
        expected.append({"idx": m["idx"], "t_est_s": round(m["file_off"] / bytes_s, 2)})

    after = http_json(f"{esp}/api/status")
    report = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "version": st.get("version"),
        "serial": st["msc"].get("usbSerial"),
        "stream_active_before": st["msc"]["stream"].get("active"),
        "pre_verify": pre,
        "markers": markers,
        "expected_t_at_kib_s": expected,
        "pace_seconds": args.seconds,
        "kib_s": args.kib_s,
        "rows": len(rows),
        "marker_crossings": hits,
        "delta_readCount": int(after["msc"]["readCount"]) - int(st["msc"]["readCount"]),
        "classification_note": (
            "Lab-Host paced cursor crossings — proves measurement can bind time↔marker. "
            "Not NBT A–E."
        ),
        "ok_pre": all(p["ok"] for p in pre) if pre else False,
        "crossed": len(hits),
    }
    (out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (out / "EAR.txt").write_text(
        f"marker-pace {stamp} ver={report['version']}\n"
        f"pre_ok={report['ok_pre']} crossings={report['crossed']} Δrc={report['delta_readCount']}\n"
        + "\n".join(f"t={h['t']}s marker={h['marker']} off={h['file_off']}" for h in hits)
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({k: report[k] for k in ("ok_pre", "crossed", "marker_crossings", "delta_readCount", "expected_t_at_kib_s")}, indent=2))
    print("OUT", out)
    return 0 if report["ok_pre"] and report["crossed"] > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

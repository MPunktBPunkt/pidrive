#!/usr/bin/env python3
"""60s field pass helper — continuous MSC-read capture + per-UID isolation.

Central question (GPT/Claude 2026-10-02): Does the BMW NBT keep reading live
MSC data during playback, or only burst-then-cache?

Hard rules encoded here:
  - msc_reads.jsonl must grow during the FULL listen window (not only around play)
  - each UID is its own pass/folder — fav0 success is NOT evidence for fav1
  - status snapshots at start, mid (optional), and end; poll streamBytes while listening

Typical use (from laptop on home LAN, Auto ESP .89, bridge on Pi):

  # before car session: point bridge at .89, Guard-Fix deployed
  python3 tools/feld_60s_live_pass.py --uid fav0 --note "sync 14:05 OTG"
  # in car: select Rock Antenne, listen 60s, then press Enter when prompted
  # repeat for fav1 / fav2 with separate --uid

Artifacts land under docs/betrieb/artifacts-YYYY-MM-DD-60s/<uid>-<HHMMSS>/
and must be committed to GitHub after the session for review.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

DEFAULT_ESP = "http://192.168.178.89"
DEFAULT_PI = "pidrive@192.168.178.105"
READS = "/tmp/pidrive_msc_reads.jsonl"
DIAG = "/tmp/pidrive_msc_diag.jsonl"
BRIDGE_LOG = "/tmp/pump_bridge_manual.log"


def http_json(url: str, timeout: float = 5.0) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.load(r)


def stream_of(st: dict) -> dict:
    s = st.get("stream")
    if isinstance(s, dict) and s:
        return s
    return (st.get("msc") or {}).get("stream") or {}


def slim_status(st: dict) -> dict:
    m = st.get("msc") or {}
    s = stream_of(st)
    slots = []
    for it in m.get("slotMap") or []:
        slots.append(
            {
                "uid": it.get("uid"),
                "name": it.get("name"),
                "bytes": it.get("bytes"),
                "maxSeq": it.get("maxSeq"),
                "fromHead": it.get("fromHead"),
                "lba0": it.get("lba0"),
                "lba1": it.get("lba1"),
            }
        )
    return {
        "ts_wall": time.time(),
        "version": st.get("version"),
        "uptime": st.get("uptime"),
        "playingUid": st.get("playingUid"),
        "playingName": st.get("playingName"),
        "pumpTcpUp": st.get("pumpTcpUp"),
        "pumpTcpPeer": st.get("pumpTcpPeer"),
        "usbSerial": m.get("usbSerial"),
        "remountGen": m.get("remountGen"),
        "phase": m.get("phase"),
        "readCount": m.get("readCount"),
        "bytesFile": m.get("bytesFile"),
        "streamBytes": m.get("streamBytes"),
        "preWarmHostBytes": m.get("preWarmHostBytes"),
        "readOverflow": m.get("readOverflow"),
        "msSincePlug": m.get("msSincePlug"),
        "stream": {
            "active": s.get("active"),
            "uid": s.get("uid"),
            "size": s.get("size"),
            "underruns": s.get("underruns"),
            "id3Len": s.get("id3Len"),
            "hasCover": s.get("hasCover"),
            "cursorArmed": s.get("cursorArmed"),
            "hostAbsCursor": s.get("hostAbsCursor"),
            "headResyncs": s.get("headResyncs"),
        },
        "slotMap": slots,
    }


def ssh(pi: str, cmd: str) -> str:
    return subprocess.check_output(["ssh", "-o", "BatchMode=yes", pi, cmd], text=True)


def scp_from(pi: str, remote: str, local: Path) -> None:
    subprocess.check_call(["scp", "-o", "BatchMode=yes", f"{pi}:{remote}", str(local)])


def remote_size(pi: str, path: str) -> int:
    out = ssh(pi, f"stat -c %s {path} 2>/dev/null || echo 0").strip()
    try:
        return int(out.splitlines()[-1])
    except ValueError:
        return 0


def extract_tail_bytes(pi: str, path: str, offset: int, dest: Path) -> int:
    """Copy bytes from offset to EOF of remote file into dest. Returns bytes copied."""
    size = remote_size(pi, path)
    if size <= offset:
        dest.write_bytes(b"")
        return 0
    # dd skip is in blocks; use tail via python on pi for byte offset
    ssh(
        pi,
        "python3 - <<'PY'\n"
        f"p={path!r}; off={offset}\n"
        "import pathlib\n"
        "b=pathlib.Path(p).read_bytes()[off:]\n"
        f"pathlib.Path('/tmp/_feld_slice.bin').write_bytes(b)\n"
        "print(len(b))\n"
        "PY",
    )
    scp_from(pi, "/tmp/_feld_slice.bin", dest)
    return dest.stat().st_size


def write_json(path: Path, obj: object) -> None:
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--uid", required=True, help="Pass UID label: fav0|fav1|fav2 (isolation!)")
    ap.add_argument("--esp", default=DEFAULT_ESP)
    ap.add_argument("--pi", default=DEFAULT_PI)
    ap.add_argument("--seconds", type=float, default=60.0)
    ap.add_argument("--poll", type=float, default=2.0, help="status poll interval while listening")
    ap.add_argument("--note", default="", help="sync marker / ear note")
    ap.add_argument(
        "--out-root",
        default="",
        help="default: docs/betrieb/artifacts-YYYY-MM-DD-60s under repo",
    )
    ap.add_argument(
        "--auto-start",
        action="store_true",
        help="do not wait for Enter — start timer immediately (lab)",
    )
    args = ap.parse_args()

    repo = Path(__file__).resolve().parents[1]
    day = datetime.now().strftime("%Y-%m-%d")
    out_root = Path(args.out_root) if args.out_root else repo / "docs" / "betrieb" / f"artifacts-{day}-60s"
    stamp = datetime.now().strftime("%H%M%S")
    out = out_root / f"{args.uid}-{stamp}"
    out.mkdir(parents=True, exist_ok=False)

    print(f"ESP {args.esp}", flush=True)
    st0 = http_json(args.esp.rstrip("/") + "/api/status")
    write_json(out / "status-before.json", st0)
    write_json(out / "status-before-slim.json", slim_status(st0))
    print(
        f"before: fw={st0.get('version')} play={st0.get('playingUid')} "
        f"pump={st0.get('pumpTcpUp')} peer={st0.get('pumpTcpPeer')} "
        f"sb={st0.get('msc',{}).get('streamBytes')} serial={st0.get('msc',{}).get('usbSerial')}",
        flush=True,
    )
    if not st0.get("pumpTcpUp"):
        print("WARN: pumpTcpUp=false — msc.reads will NOT append on Pi until bridge links", flush=True)

    off_reads = remote_size(args.pi, READS)
    off_diag = remote_size(args.pi, DIAG)
    off_bridge = remote_size(args.pi, BRIDGE_LOG)
    meta = {
        "uid": args.uid,
        "note": args.note,
        "esp": args.esp,
        "pi": args.pi,
        "seconds": args.seconds,
        "poll": args.poll,
        "wall_start": None,
        "wall_end": None,
        "jsonl_offsets": {"reads": off_reads, "diag": off_diag, "bridge": off_bridge},
        "central_question": (
            "Does NBT keep reading live MSC data during playback, or burst-then-cache?"
        ),
        "isolation_rule": "This folder is ONLY for this uid — do not mix with other passes.",
    }
    write_json(out / "meta-pre.json", meta)

    if not args.auto_start:
        print(
            f"\n>>> Im Auto jetzt '{args.uid}' wählen, Sync-Marker notieren, "
            f"dann ENTER — Timer {args.seconds:.0f}s startet.",
            flush=True,
        )
        input()

    t0 = time.time()
    meta["wall_start"] = t0
    meta["note_at_start"] = args.note
    polls: list[dict] = []
    print(f"LISTEN {args.seconds:.0f}s — keep hearing; reads must keep appending…", flush=True)

    while True:
        now = time.time()
        elapsed = now - t0
        try:
            st = http_json(args.esp.rstrip("/") + "/api/status")
            row = slim_status(st)
            row["t_rel"] = round(elapsed, 2)
            # live growth of remote jsonl (proves capture is running)
            row["reads_file_bytes"] = remote_size(args.pi, READS)
            polls.append(row)
            s = row["stream"]
            print(
                f"  t={elapsed:5.1f}s play={row.get('playingUid')} "
                f"stream={s.get('uid')} sb={row.get('streamBytes')} "
                f"under={s.get('underruns')} readsF={row.get('readCount')} "
                f"jsonl={row['reads_file_bytes'] - off_reads:+d}B",
                flush=True,
            )
        except Exception as e:  # noqa: BLE001
            polls.append({"t_rel": round(elapsed, 2), "error": str(e)})
            print(f"  t={elapsed:5.1f}s ERROR {e}", flush=True)
        if elapsed >= args.seconds:
            break
        time.sleep(max(0.2, min(args.poll, args.seconds - elapsed)))

    t1 = time.time()
    meta["wall_end"] = t1
    write_json(out / "polls.json", polls)

    st1 = http_json(args.esp.rstrip("/") + "/api/status")
    write_json(out / "status-after.json", st1)
    write_json(out / "status-after-slim.json", slim_status(st1))

    n_reads = extract_tail_bytes(args.pi, READS, off_reads, out / "pidrive_msc_reads.jsonl")
    n_diag = extract_tail_bytes(args.pi, DIAG, off_diag, out / "pidrive_msc_diag.jsonl")
    n_br = extract_tail_bytes(args.pi, BRIDGE_LOG, off_bridge, out / "bridge-slice.log")

    # summarize reads
    read_rows = []
    for line in (out / "pidrive_msc_reads.jsonl").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                read_rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    total_b = sum(int(r.get("bytes") or 0) for r in read_rows)
    sb0 = (polls[0].get("streamBytes") if polls else None)
    sb1 = slim_status(st1).get("streamBytes")
    under0 = (polls[0].get("stream") or {}).get("underruns") if polls else None
    under1 = slim_status(st1)["stream"].get("underruns")

    summary = {
        **meta,
        "duration_s": round(t1 - t0, 2),
        "msc_reads_lines": len(read_rows),
        "msc_reads_bytes_sum": total_b,
        "msc_reads_file_delta_B": n_reads,
        "diag_file_delta_B": n_diag,
        "bridge_file_delta_B": n_br,
        "streamBytes_before": sb0,
        "streamBytes_after": sb1,
        "streamBytes_delta": (None if sb0 is None or sb1 is None else sb1 - sb0),
        "underruns_before": under0,
        "underruns_after": under1,
        "underruns_delta": (
            None if under0 is None or under1 is None else int(under1) - int(under0)
        ),
        "playing_after": st1.get("playingUid"),
        "stream_uid_after": slim_status(st1)["stream"].get("uid"),
        "verdict_hints": {
            "live_consume_if": "streamBytes_delta >> 0 AND msc_reads continue after t~2s",
            "cache_if": "msc_reads stop after initial burst AND streamBytes_delta≈0 while audio heard",
            "isolation": f"ONLY valid for {args.uid} — do not cite for other UIDs",
        },
    }
    write_json(out / "summary.json", summary)

    ear = out / "EAR.txt"
    ear.write_text(
        f"UID: {args.uid}\n"
        f"Sync/note: {args.note}\n"
        f"Wall: {datetime.fromtimestamp(t0).isoformat()} → "
        f"{datetime.fromtimestamp(t1).isoformat()}\n"
        f"Heard (fill in): \n"
        f"  - live / stub / silence / loop?\n"
        f"  - ID3 cover yes/no?\n"
        f"  - approx when audio started (s after select):\n",
        encoding="utf-8",
    )

    # root README
    readme = out_root / "README.md"
    if not readme.exists():
        readme.write_text(
            f"# Feld 60s Live-Read Passes — {day}\n\n"
            "**Zentrale Frage:** Liest die BMW-NBT während der Wiedergabe "
            "kontinuierlich Live-MSC-Daten, oder nur Burst + Cache?\n\n"
            "**Regeln:**\n"
            "- `pidrive_msc_reads.jsonl` muss die **gesamten** 60 s abdecken "
            "(Capture vor dem Select starten / Offset-Slice).\n"
            "- Jeder Sender = eigener Ordner; **fav0 ≠ Nachweis für fav1**.\n"
            "- Nach der Session: Ordner committen + in "
            "`FELDTEST-ESP-MSC-BMW-2026-09-28.md` §11.x eintragen und pushen.\n\n"
            f"Tool: `tools/feld_60s_live_pass.py`\n",
            encoding="utf-8",
        )

    print("\n=== PASS DONE ===", flush=True)
    print(json.dumps(summary, indent=2), flush=True)
    print(f"\nArtifacts: {out}", flush=True)
    print("Fill EAR.txt, then git add/commit/push for review.", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\naborted", file=sys.stderr)
        raise SystemExit(130)

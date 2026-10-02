#!/usr/bin/env python3
"""B7 field pass — ≥150s single-station slot/reread capture (no FW change).

Central question after §11.10: Does the NBT re-read MSC after the mount-scan
cache window (orientation ~28s / ~87s), or never?

Hard rules:
  - Start capture BEFORE station select (Enter after marker, then select in car)
  - One UID per folder; heard station MUST match playingUid for UID verdicts
  - Read-flat observation remains valid even if UID mismatches (note it)

Typical use:

  ./tools/feld_prepare_homecoming.sh   # bridge → .89, FW 0.4.36 check
  python3 tools/feld_150s_slot_pass.py --uid fav1 --note "16:05 OTG PD0xxx"
  # ENTER when ready → select station → listen ≥150s → fill EAR stopwatch

Artifacts: docs/betrieb/artifacts-YYYY-MM-DD-b7/<uid>-<HHMMSS>/
"""
from __future__ import annotations

import argparse
import json
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
BRIDGE_LOG_CANDIDATES = (
    "/tmp/pump_bridge_manual.log",
    "/tmp/pump_bridge_lab88.log",
    "/tmp/pump_bridge_89.log",
)
# Rechenorientierung only (not event guarantees)
ORIENT_S = (28.0, 87.0, 120.0, 150.0)


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
        "lastReadLba": m.get("lastReadLba"),
        "bytesFile": m.get("bytesFile"),
        "bytesRead": m.get("bytesRead"),
        "streamBytes": m.get("streamBytes"),
        "preWarmHostBytes": m.get("preWarmHostBytes"),
        "readOverflow": m.get("readOverflow"),
        "playRejectCount": m.get("playRejectCount"),
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


def pick_bridge_log(pi: str) -> str:
    best = BRIDGE_LOG_CANDIDATES[0]
    best_sz = -1
    for path in BRIDGE_LOG_CANDIDATES:
        sz = remote_size(pi, path)
        if sz > best_sz:
            best, best_sz = path, sz
    return best


def extract_tail_bytes(pi: str, path: str, offset: int, dest: Path) -> int:
    size = remote_size(pi, path)
    if size <= offset:
        dest.write_bytes(b"")
        return 0
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


def analyze_polls(polls: list[dict], expected_uid: str) -> dict:
    ok = [p for p in polls if "error" not in p and p.get("readCount") is not None]
    if not ok:
        return {"ok_samples": 0}
    live = []
    for i in range(1, len(ok)):
        if (
            ok[i].get("readCount") != ok[i - 1].get("readCount")
            or ok[i].get("streamBytes") != ok[i - 1].get("streamBytes")
            or ok[i].get("lastReadLba") != ok[i - 1].get("lastReadLba")
        ):
            live.append(ok[i])
    uid_ok = all(p.get("playingUid") == expected_uid for p in ok)
    uid_set = sorted({p.get("playingUid") for p in ok})
    markers = {}
    tmax = float(ok[-1].get("t_rel") or 0)
    for t_mark in ORIENT_S:
        if t_mark > tmax + 1.0:
            continue  # don't fake marks beyond the actual listen window
        near = min(ok, key=lambda p: abs(float(p.get("t_rel") or 0) - t_mark))
        markers[f"t≈{t_mark:.0f}s"] = {
            "t_rel": near.get("t_rel"),
            "readCount": near.get("readCount"),
            "streamBytes": near.get("streamBytes"),
            "lastReadLba": near.get("lastReadLba"),
            "playingUid": near.get("playingUid"),
        }
    return {
        "ok_samples": len(ok),
        "live_samples": len(live),
        "readCount_delta": int(ok[-1]["readCount"]) - int(ok[0]["readCount"]),
        "streamBytes_delta": int(ok[-1].get("streamBytes") or 0)
        - int(ok[0].get("streamBytes") or 0),
        "readOverflow_delta": int(ok[-1].get("readOverflow") or 0)
        - int(ok[0].get("readOverflow") or 0),
        "first_live_t": live[0].get("t_rel") if live else None,
        "last_live_t": live[-1].get("t_rel") if live else None,
        "playingUid_matches_pass_uid": uid_ok,
        "playingUids_seen": uid_set,
        "orientation_snapshots": markers,
        "verdict_hints": {
            "reread_if": "readCount rises after t>~10s (past mount burst) especially near ~28s/~87s",
            "cache_only_if": "readCount flat for full ≥150s after select while audio heard",
            "uid_verdict_valid_if": f"playingUid always == {expected_uid}",
            "read_flat_still_valid_if_uid_mismatch": True,
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--uid", required=True, help="Pass UID: fav0|fav1|fav2")
    ap.add_argument("--esp", default=DEFAULT_ESP)
    ap.add_argument("--pi", default=DEFAULT_PI)
    ap.add_argument("--seconds", type=float, default=150.0)
    ap.add_argument("--poll", type=float, default=2.0)
    ap.add_argument("--note", default="", help="sync marker / OTG time / serial")
    ap.add_argument("--out-root", default="")
    ap.add_argument("--bridge-log", default="")
    ap.add_argument("--auto-start", action="store_true")
    args = ap.parse_args()

    if args.seconds < 120:
        print(
            f"WARN: B7 wants ≥150s (got {args.seconds}); continuing anyway",
            flush=True,
        )

    bridge_log = args.bridge_log or pick_bridge_log(args.pi)
    repo = Path(__file__).resolve().parents[1]
    day = datetime.now().strftime("%Y-%m-%d")
    out_root = (
        Path(args.out_root)
        if args.out_root
        else repo / "docs" / "betrieb" / f"artifacts-{day}-b7"
    )
    stamp = datetime.now().strftime("%H%M%S")
    out = out_root / f"{args.uid}-{stamp}"
    out.mkdir(parents=True, exist_ok=False)

    print(f"B7 ESP {args.esp}  bridge_log={bridge_log}  out={out}", flush=True)
    st0 = http_json(args.esp.rstrip("/") + "/api/status")
    write_json(out / "status-before.json", st0)
    write_json(out / "status-before-slim.json", slim_status(st0))
    print(
        f"before: fw={st0.get('version')} play={st0.get('playingUid')} "
        f"rc={st0.get('msc',{}).get('readCount')} sb={st0.get('msc',{}).get('streamBytes')} "
        f"serial={st0.get('msc',{}).get('usbSerial')} pump={st0.get('pumpTcpUp')}",
        flush=True,
    )
    if "0.4.36" not in str(st0.get("version") or ""):
        print("WARN: expected FW 0.4.36-dev — no OTA in this tool", flush=True)

    off_reads = remote_size(args.pi, READS)
    off_diag = remote_size(args.pi, DIAG)
    off_bridge = remote_size(args.pi, bridge_log)
    meta = {
        "pass": "B7-150s",
        "uid": args.uid,
        "note": args.note,
        "esp": args.esp,
        "pi": args.pi,
        "bridge_log": bridge_log,
        "seconds": args.seconds,
        "poll": args.poll,
        "fw_required": "0.4.36-dev (no change)",
        "orientation_s": list(ORIENT_S),
        "jsonl_offsets": {"reads": off_reads, "diag": off_diag, "bridge": off_bridge},
        "central_question": (
            "After mount-scan cache, does NBT re-read MSC past slot/track orientation marks?"
        ),
    }
    write_json(out / "meta-pre.json", meta)

    if not args.auto_start:
        print(
            f"\n>>> 1) Sync-Marker notieren (Uhr + OTG/serial)\n"
            f">>> 2) ENTER hier → Timer {args.seconds:.0f}s startet\n"
            f">>> 3) Sofort im Auto '{args.uid}' wählen und ≥{args.seconds:.0f}s hören\n"
            f">>> 4) Stoppuhr: Ton-Start / Ton-Ende (s nach Select)\n",
            flush=True,
        )
        input()

    t0 = time.time()
    meta["wall_start"] = t0
    polls: list[dict] = []
    announced = set()
    print(f"LISTEN {args.seconds:.0f}s …", flush=True)

    while True:
        now = time.time()
        elapsed = now - t0
        for mark in ORIENT_S:
            if elapsed >= mark and mark not in announced:
                announced.add(mark)
                print(f"  --- orientation mark t≈{mark:.0f}s ---", flush=True)
        try:
            st = http_json(args.esp.rstrip("/") + "/api/status")
            row = slim_status(st)
            row["t_rel"] = round(elapsed, 2)
            row["reads_file_bytes"] = remote_size(args.pi, READS)
            polls.append(row)
            s = row["stream"]
            match = "OK" if row.get("playingUid") == args.uid else "UID≠"
            print(
                f"  t={elapsed:6.1f}s {match} play={row.get('playingUid')} "
                f"rc={row.get('readCount')} sb={row.get('streamBytes')} "
                f"lba={row.get('lastReadLba')} ov={row.get('readOverflow')} "
                f"cur={s.get('cursorArmed')}/{s.get('hostAbsCursor')} "
                f"jsonl={row['reads_file_bytes'] - off_reads:+d}B",
                flush=True,
            )
        except Exception as e:  # noqa: BLE001
            polls.append({"t_rel": round(elapsed, 2), "error": str(e)})
            print(f"  t={elapsed:6.1f}s ERROR {e}", flush=True)
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
    n_br = extract_tail_bytes(args.pi, bridge_log, off_bridge, out / "bridge-slice.log")

    analysis = analyze_polls(polls, args.uid)
    summary = {
        **meta,
        "duration_s": round(t1 - t0, 2),
        "msc_reads_file_delta_B": n_reads,
        "diag_file_delta_B": n_diag,
        "bridge_file_delta_B": n_br,
        "analysis": analysis,
        "playing_after": st1.get("playingUid"),
    }
    write_json(out / "summary.json", summary)

    (out / "EAR.txt").write_text(
        f"UID pass label: {args.uid}\n"
        f"Sync/note: {args.note}\n"
        f"Wall: {datetime.fromtimestamp(t0).isoformat()} → "
        f"{datetime.fromtimestamp(t1).isoformat()}\n"
        f"FW: {st0.get('version')} (must stay 0.4.36 — no OTA for B7)\n\n"
        f"Stoppuhr (Pflicht):\n"
        f"  - Select-Zeitpunkt (Uhr):\n"
        f"  - Ton-Start (s nach Select):\n"
        f"  - Ton-Ende / still (s nach Select):\n"
        f"  - Cover ja/nein:\n"
        f"  - Gehörte Station == {args.uid}? ja/nein\n\n"
        f"Bei Stationswechsel-Pass (Auftrag B) extra Marker pro Wechsel.\n",
        encoding="utf-8",
    )

    readme = out_root / "README.md"
    if not readme.exists():
        readme.write_text(
            f"# Feld B7 150s Slot/Reread — {day}\n\n"
            "Frage: Liest die NBT nach Mount-Scan erneut (über ~28s/~87s hinaus)?\n\n"
            "FW: **0.4.36-dev unverändert**. Tool: `tools/feld_150s_slot_pass.py`\n"
            "Auftrag: `docs/auftraege/AUFTRAG-B7-HU-REREAD.md`\n",
            encoding="utf-8",
        )

    print("\n=== B7 PASS DONE ===", flush=True)
    print(json.dumps(summary, indent=2), flush=True)
    print(f"\nArtifacts: {out}", flush=True)
    print("Fill EAR.txt stopwatch → commit/push for review.", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\naborted", file=sys.stderr)
        raise SystemExit(130)

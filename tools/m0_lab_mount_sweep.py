#!/usr/bin/env python3
"""M0 Lab Mount-Sweep — verify readCount == Σ(burst.n) + drops for one session.

No FW changes. Requires:
  - ESP lab (default http://192.168.178.88) with USB host attached (e.g. Proxmox)
  - pump_bridge on Pi pointed at that ESP (writes /tmp/pidrive_msc_reads.jsonl)

Usage:
  python3 tools/m0_lab_mount_sweep.py --esp http://192.168.178.88 --pi pidrive@192.168.178.105 --runs 2
"""
from __future__ import annotations

import argparse
import json
import subprocess
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


READS = "/tmp/pidrive_msc_reads.jsonl"
DIAG = "/tmp/pidrive_msc_diag.jsonl"


def http_json(url: str, method: str = "GET", body: bytes | None = None, timeout: float = 8.0):
    req = urllib.request.Request(url, data=body, method=method)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def ssh(pi: str, cmd: str) -> str:
    return subprocess.check_output(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", pi, cmd], text=True)


def remote_size(pi: str, path: str) -> int:
    out = ssh(pi, f"stat -c %s {path} 2>/dev/null || echo 0").strip()
    return int(out.splitlines()[-1])


def extract_tail(pi: str, path: str, offset: int, dest: Path) -> int:
    """Copy bytes after offset from remote file; return bytes written."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    # dd skip is in blocks; use tail via python on remote for byte offset
    data = ssh(
        pi,
        f"python3 -c \"import sys;p='{path}';o=int('{offset}');"
        f"f=open(p,'rb');f.seek(o);sys.stdout.buffer.write(f.read())\"",
    )
    # ssh returns text — for binary jsonl UTF-8 this is fine
    raw = data.encode("utf-8") if isinstance(data, str) else data
    # Actually check_output text=True already decoded — use bytes mode
    return -1  # placeholder, replaced below


def extract_tail_bytes(pi: str, path: str, offset: int, dest: Path) -> int:
    dest.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=8",
            pi,
            f"python3 -c \"import sys;p='{path}';o={offset};"
            f"f=open(p,'rb');f.seek(o);sys.stdout.buffer.write(f.read())\"",
        ],
        capture_output=True,
        check=True,
    )
    dest.write_bytes(proc.stdout)
    return len(proc.stdout)


def slim_status(d: dict) -> dict:
    m = d.get("msc") or {}
    return {
        "version": d.get("version"),
        "uptime": d.get("uptime"),
        "ip": d.get("ip"),
        "usbSerial": m.get("usbSerial"),
        "remountGen": m.get("remountGen"),
        "plugCount": m.get("plugCount"),
        "msSincePlug": m.get("msSincePlug"),
        "phase": m.get("phase"),
        "readCount": m.get("readCount"),
        "readsEmit": m.get("readsEmit"),
        "readOverflow": m.get("readOverflow"),
        "bytesRead": m.get("bytesRead"),
        "bytesFile": m.get("bytesFile"),
        "pumpTcpUp": d.get("pumpTcpUp"),
        "pumpTcpPeer": d.get("pumpTcpPeer"),
        "otgUp": d.get("otgUp"),
        "sessionKey": f"{d.get('version')}|{m.get('usbSerial')}|{m.get('remountGen')}|{d.get('uptime')}",
    }


def parse_bursts(path: Path) -> tuple[int, int, int]:
    """Return (lines, sum_n, sum_bytes)."""
    lines = 0
    sn = 0
    sb = 0
    if not path.exists() or path.stat().st_size == 0:
        return 0, 0, 0
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue
        lines += 1
        sn += int(o.get("n") or 0)
        sb += int(o.get("bytes") or 0)
    return lines, sn, sb


def wait_sweep(esp: str, rc_before: int, timeout_s: float = 45.0, stable_s: float = 3.0) -> dict:
    """After remount: wait for readCount to rise, then stabilize."""
    t0 = time.time()
    last_rc = rc_before
    stable_since = None
    saw_increase = False
    last = None
    while time.time() - t0 < timeout_s:
        last = http_json(f"{esp}/api/status")
        rc = int((last.get("msc") or {}).get("readCount") or 0)
        if rc > rc_before:
            saw_increase = True
        if rc != last_rc:
            last_rc = rc
            stable_since = time.time()
        elif saw_increase and stable_since and (time.time() - stable_since) >= stable_s:
            return last
        time.sleep(0.4)
    return last or http_json(f"{esp}/api/status")


def host_nudge(host: str) -> str:
    """Best-effort Linux host rescan/read after soft remount."""
    if not host:
        return "skip"
    cmd = (
        "serial=$(cat /sys/block/sda/device/serial 2>/dev/null || true); "
        "echo serial=$serial; "
        "dd if=/dev/sda of=/dev/null bs=4K count=64 status=none 2>/dev/null || true; "
        "blockdev --rereadpt /dev/sda 2>/dev/null || true; "
        "echo nudged"
    )
    try:
        return subprocess.check_output(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", host, cmd],
            text=True,
            stderr=subprocess.STDOUT,
        )
    except subprocess.CalledProcessError as e:
        return f"nudge_fail:{e.output}"


def one_run(args, out: Path, idx: int) -> dict:
    esp = args.esp.rstrip("/")
    pi = args.pi
    run_dir = out / f"sweep-{idx}"
    run_dir.mkdir(parents=True, exist_ok=True)

    before = http_json(f"{esp}/api/status")
    (run_dir / "status-before.json").write_text(json.dumps(before), encoding="utf-8")
    off_r = remote_size(pi, READS)
    off_d = remote_size(pi, DIAG)
    slim_b = slim_status(before)

    # remount triggers host rescan
    try:
        rem = http_json(f"{esp}/api/lab/remount", method="POST", body=b"{}")
    except Exception as e:
        rem = {"ok": False, "error": str(e)}
    (run_dir / "remount.json").write_text(json.dumps(rem), encoding="utf-8")

    time.sleep(0.8)
    nudge = host_nudge(args.host)
    (run_dir / "host-nudge.txt").write_text(nudge, encoding="utf-8")

    rc0 = int(slim_b["readCount"] or 0)
    after = wait_sweep(esp, rc_before=rc0, timeout_s=args.wait, stable_s=args.stable)
    (run_dir / "status-after.json").write_text(json.dumps(after), encoding="utf-8")
    slim_a = slim_status(after)

    n_r = extract_tail_bytes(pi, READS, off_r, run_dir / "pidrive_msc_reads.jsonl")
    n_d = extract_tail_bytes(pi, DIAG, off_d, run_dir / "pidrive_msc_diag.jsonl")
    lines, sum_n, sum_b = parse_bursts(run_dir / "pidrive_msc_reads.jsonl")

    rc1 = int(slim_a["readCount"] or 0)
    # Soft remount does NOT reset readCount_ (only USB plug edge). Use window delta.
    if rc1 < rc0:
        session_rc = rc1
        session_note = "readCount decreased (USB replug reset?) — absolute after"
    else:
        session_rc = rc1 - rc0
        session_note = "ΔreadCount over remount window (soft remount keeps counters)"

    ov = int(slim_a["readOverflow"] or 0) - int(slim_b["readOverflow"] or 0)
    if ov < 0:
        ov = int(slim_a["readOverflow"] or 0)

    emit0 = int(slim_b["readsEmit"] or 0)
    emit1 = int(slim_a["readsEmit"] or 0)
    emit_delta = emit1 - emit0 if emit1 >= emit0 else emit1

    balance_ok = session_rc == (sum_n + ov)
    empty_fail = n_r == 0 and session_rc > 0
    emit_lines_ok = emit_delta == lines

    summary = {
        "run": idx,
        "ts": datetime.now(timezone.utc).isoformat(),
        "session_before": slim_b,
        "session_after": slim_a,
        "session_note": session_note,
        "host_nudge": nudge.strip().splitlines()[-1] if nudge else "",
        "delta_readCount": session_rc,
        "reads_jsonl_bytes": n_r,
        "diag_jsonl_bytes": n_d,
        "burst_lines": lines,
        "sum_burst_n": sum_n,
        "sum_burst_bytes": sum_b,
        "overflow_delta": ov,
        "readsEmit_before": emit0,
        "readsEmit_after": emit1,
        "readsEmit_delta": emit_delta,
        "readsEmit_eq_burst_lines": emit_lines_ok,
        "equation": "ΔreadCount = Σ(burst.n) + Δdrops",
        "balance": {"left": session_rc, "right": sum_n + ov, "ok": balance_ok},
        "empty_export_fail": empty_fail,
        "pumpTcpUp_after": slim_a.get("pumpTcpUp"),
        "verdict": (
            "PASS"
            if balance_ok and not empty_fail and (session_rc > 0 or lines == 0)
            else (
                "FAIL_EMPTY_EXPORT"
                if empty_fail
                else ("FAIL_NO_HOST_READS" if session_rc == 0 else "FAIL_BALANCE")
            )
        ),
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return summary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--esp", default="http://192.168.178.88")
    ap.add_argument("--pi", default="pidrive@192.168.178.105")
    ap.add_argument("--host", default="root@192.168.178.108", help="Linux USB host for remount nudge")
    ap.add_argument("--runs", type=int, default=2)
    ap.add_argument("--wait", type=float, default=40.0)
    ap.add_argument("--stable", type=float, default=3.0)
    ap.add_argument(
        "--out",
        default="",
        help="artifact dir (default docs/betrieb/artifacts-YYYY-MM-DD-m0/lab88-...)",
    )
    args = ap.parse_args()
    day = datetime.now().strftime("%Y-%m-%d")
    stamp = datetime.now().strftime("%H%M%S")
    out = Path(args.out) if args.out else Path(f"docs/betrieb/artifacts-{day}-m0/lab88-{stamp}")
    out.mkdir(parents=True, exist_ok=True)

    pre = slim_status(http_json(f"{args.esp.rstrip('/')}/api/status"))
    meta = {
        "esp": args.esp,
        "pi": args.pi,
        "pre": pre,
        "note": "M0 mount-sweep; equation readCount = Σ(burst.n) + drops",
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    if not pre.get("pumpTcpUp"):
        print("WARN: pumpTcpUp=false — readsEmit/jsonl may stay empty; start pump_bridge first")

    results = []
    for i in range(1, args.runs + 1):
        print(f"=== sweep {i}/{args.runs} ===")
        results.append(one_run(args, out, i))
        time.sleep(2)

    rcs = [r["delta_readCount"] for r in results]
    report = {
        "runs": results,
        "delta_readCount_spread": {"values": rcs, "same": len(set(rcs)) == 1},
        "all_pass": all(r["verdict"] == "PASS" for r in results),
        "note": "Soft remount keeps readCount; equation uses Δ. readsEmit never resets on remount.",
    }
    (out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (out / "EAR.txt").write_text(
        f"M0 lab mount-sweep {stamp}\n"
        f"all_pass={report['all_pass']} spread={report['delta_readCount_spread']}\n"
        + "\n".join(
            f"run{r['run']}: {r['verdict']} Δrc={r['delta_readCount']} Σn={r['sum_burst_n']} "
            f"lines={r['burst_lines']} emitΔ={r['readsEmit_delta']} emit==lines={r['readsEmit_eq_burst_lines']}"
            for r in results
        )
        + "\n",
        encoding="utf-8",
    )
    print("REPORT", json.dumps(report, indent=2))
    print("OUT", out)
    return 0 if report["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

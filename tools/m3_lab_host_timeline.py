#!/usr/bin/env python3
"""M3 Lab host timeline — Sweep-Ende → Quiet → optional paced read (Lab-Host ≠ NBT).

Measures MSC read activity on Proxmox against ESP virtual stick with static silence.
Classifies A–E for *this* host only; BMW confirmation remains Auto-only.

Phases:
  1) remount + host nudge → capture until readCount stable (sweep end)
  2) idle --idle-s — any new payload reads?
  3) optional --paced-s: sequential LBA reads @ ~6 KiB/s on fav0 (cooperative host)

Example:
  python3 tools/m3_lab_host_timeline.py --esp http://192.168.178.88 \\
    --pi pidrive@192.168.178.105 --host root@192.168.178.108 --idle-s 90 --paced-s 60
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


def http_json(url: str, method: str = "GET", body: bytes | None = None, timeout: float = 10.0):
    req = urllib.request.Request(url, data=body, method=method)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def ssh(host: str, cmd: str) -> str:
    return subprocess.check_output(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", host, cmd],
        text=True,
        stderr=subprocess.STDOUT,
    )


def remote_size(pi: str, path: str) -> int:
    return int(ssh(pi, f"stat -c %s {path} 2>/dev/null || echo 0").strip().splitlines()[-1])


def extract_tail(pi: str, path: str, offset: int, dest: Path) -> int:
    dest.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [
            "ssh",
            "-o",
            "BatchMode=yes",
            pi,
            f"python3 -c \"import sys;f=open('{path}','rb');f.seek({offset});"
            f"sys.stdout.buffer.write(f.read())\"",
        ],
        capture_output=True,
        check=True,
    )
    dest.write_bytes(proc.stdout)
    return len(proc.stdout)


def slim(d: dict) -> dict:
    m = d.get("msc") or {}
    fav0 = next((s for s in (m.get("slotMap") or []) if s.get("uid") == "fav0"), {})
    return {
        "version": d.get("version"),
        "uptime": d.get("uptime"),
        "usbSerial": m.get("usbSerial"),
        "remountGen": m.get("remountGen"),
        "phase": m.get("phase"),
        "readCount": m.get("readCount"),
        "readsEmit": m.get("readsEmit"),
        "readOverflow": m.get("readOverflow"),
        "bytesFile": m.get("bytesFile"),
        "streamActive": (m.get("stream") or {}).get("active"),
        "fav0_lba0": fav0.get("lba0"),
        "fav0_lba1": fav0.get("lba1"),
        "pumpTcpUp": d.get("pumpTcpUp"),
    }


def parse_bursts(path: Path) -> dict:
    lines = 0
    sn = 0
    sb = 0
    first_ms = None
    last_ms = None
    lbas = []
    if path.exists() and path.stat().st_size:
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
            ms = o.get("ms")
            if ms is not None:
                first_ms = ms if first_ms is None else first_ms
                last_ms = ms
            if "lba0" in o:
                lbas.append(int(o["lba0"]))
    return {
        "lines": lines,
        "sum_n": sn,
        "sum_bytes": sb,
        "esp_ms0": first_ms,
        "esp_ms1": last_ms,
        "esp_span_ms": (last_ms - first_ms) if first_ms is not None and last_ms is not None else 0,
        "lba_min": min(lbas) if lbas else None,
        "lba_max": max(lbas) if lbas else None,
    }


def wait_stable(esp: str, rc0: int, timeout: float, stable_s: float) -> dict:
    t0 = time.time()
    last_rc = rc0
    stable_since = None
    saw = False
    last = None
    while time.time() - t0 < timeout:
        last = http_json(f"{esp}/api/status")
        rc = int((last.get("msc") or {}).get("readCount") or 0)
        if rc > rc0:
            saw = True
        if rc != last_rc:
            last_rc = rc
            stable_since = time.time()
        elif saw and stable_since and time.time() - stable_since >= stable_s:
            return last
        time.sleep(0.4)
    return last or http_json(f"{esp}/api/status")


def classify(sweep_n: int, idle_n: int, paced_n: int, idle_s: float) -> dict:
    """A–E for Lab host observation window."""
    if sweep_n > 0 and idle_n == 0 and paced_n == 0:
        code = "A_or_E"
        detail = "Initial sweep then no further reads in idle (Lab-Host cache/done). Paced not run or 0."
    elif sweep_n > 0 and idle_n == 0 and paced_n > 0:
        code = "A_then_forced_C"
        detail = "Sweep+quiet, then paced host reads produced new LBAs (cooperative host ≠ NBT)."
    elif sweep_n > 0 and idle_n > 0 and paced_n == 0:
        code = "B"
        detail = "Reads after sweep during idle without clear cursor proof."
    elif paced_n > 0 and idle_n == 0:
        code = "C_lab_paced"
        detail = "Cursor-like only under explicit paced consume."
    else:
        code = "mixed"
        detail = "See phase deltas."
    return {
        "code": code,
        "detail": detail,
        "levels": {
            "1_host_read": sweep_n + idle_n + paced_n > 0,
            "2_read_ahead": "unknown_without_play_cursor",
            "3_play_read": paced_n > 0,
            "4_live_usable": False,
        },
        "note": "Lab-Host classification only — not BMW NBT A–E",
        "idle_s": idle_s,
    }


def paced_fav0(host: str, dev: str, lba0: int, lba1: int, seconds: float, kib_s: float) -> dict:
    """Run paced dd on remote host; return ok + approx bytes."""
    bytes_s = kib_s * 1024.0
    script = f"""
import time, subprocess
lba = {int(lba0)}
end = {int(lba1)}
t0 = time.time()
n = 0
bytes_s = {bytes_s}
seconds = {float(seconds)}
dev = {dev!r}
while time.time() - t0 < seconds:
    if lba > end:
        lba = {int(lba0)}
    cnt = min(8, end - lba + 1)
    subprocess.check_call(
        ["dd", f"if={{dev}}", "bs=512", f"skip={{lba}}", f"count={{cnt}}",
         "iflag=direct", "status=none", "of=/dev/null"],
        stderr=subprocess.DEVNULL,
    )
    lba += cnt
    n += cnt * 512
    time.sleep((cnt * 512) / bytes_s)
print("bytes", n)
"""
    # fix nested braces for dd format - rewrite without double format issues
    script = (
        "import time, subprocess\n"
        f"lba = {int(lba0)}\n"
        f"end = {int(lba1)}\n"
        f"t0 = time.time()\n"
        f"n = 0\n"
        f"bytes_s = {bytes_s}\n"
        f"seconds = {float(seconds)}\n"
        f"dev = {dev!r}\n"
        "while time.time() - t0 < seconds:\n"
        f"    if lba > end:\n"
        f"        lba = {int(lba0)}\n"
        "    cnt = min(8, end - lba + 1)\n"
        "    subprocess.check_call(\n"
        "        ['dd', 'if=%s' % dev, 'bs=512', 'skip=%d' % lba, 'count=%d' % cnt,\n"
        "         'iflag=direct', 'status=none', 'of=/dev/null'],\n"
        "        stderr=subprocess.DEVNULL,\n"
        "    )\n"
        "    lba += cnt\n"
        "    n += cnt * 512\n"
        "    time.sleep((cnt * 512) / bytes_s)\n"
        "print('bytes', n)\n"
    )
    out = ssh(host, "python3 - <<'PY'\n" + script + "PY")
    return {"raw": out.strip(), "ok": "bytes" in out}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--esp", default="http://192.168.178.88")
    ap.add_argument("--pi", default="pidrive@192.168.178.105")
    ap.add_argument("--host", default="root@192.168.178.108")
    ap.add_argument("--dev", default="/dev/sda")
    ap.add_argument("--idle-s", type=float, default=90.0)
    ap.add_argument("--paced-s", type=float, default=60.0)
    ap.add_argument("--kib-s", type=float, default=6.0)
    ap.add_argument("--wait", type=float, default=40.0)
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    esp = args.esp.rstrip("/")
    stamp = datetime.now().strftime("%H%M%S")
    day = datetime.now().strftime("%Y-%m-%d")
    out = Path(args.out) if args.out else Path(f"docs/betrieb/artifacts-{day}-m3/lab88-timeline-{stamp}")
    out.mkdir(parents=True, exist_ok=True)

    # ensure no live stream
    try:
        http_json(f"{esp}/api/lab/stop", method="POST", body=b"{}")
    except Exception:
        pass
    time.sleep(0.5)

    before = http_json(f"{esp}/api/status")
    (out / "status-00-before.json").write_text(json.dumps(before), encoding="utf-8")
    s0 = slim(before)
    off_r = remote_size(args.pi, READS)
    off_d = remote_size(args.pi, DIAG)
    rc0 = int(s0["readCount"] or 0)

    # Phase 1: remount + nudge
    try:
        rem = http_json(f"{esp}/api/lab/remount", method="POST", body=b"{}")
    except Exception as e:
        rem = {"ok": False, "error": str(e)}
    (out / "remount.json").write_text(json.dumps(rem), encoding="utf-8")
    time.sleep(0.8)
    try:
        nudge = ssh(
            args.host,
            f"dd if={args.dev} of=/dev/null bs=4K count=128 iflag=direct status=none; echo nudged",
        )
    except Exception as e:
        nudge = str(e)
    (out / "host-nudge.txt").write_text(nudge, encoding="utf-8")

    after_sweep = wait_stable(esp, rc0, args.wait, 3.0)
    (out / "status-01-sweep-end.json").write_text(json.dumps(after_sweep), encoding="utf-8")
    s1 = slim(after_sweep)
    extract_tail(args.pi, READS, off_r, out / "reads-phase1-sweep.jsonl")
    extract_tail(args.pi, DIAG, off_d, out / "diag-phase1.jsonl")
    p1 = parse_bursts(out / "reads-phase1-sweep.jsonl")
    off_r2 = remote_size(args.pi, READS)
    off_d2 = remote_size(args.pi, DIAG)
    d_rc1 = int(s1["readCount"] or 0) - rc0

    # Phase 2: idle
    t_idle0 = time.time()
    time.sleep(args.idle_s)
    after_idle = http_json(f"{esp}/api/status")
    (out / "status-02-after-idle.json").write_text(json.dumps(after_idle), encoding="utf-8")
    s2 = slim(after_idle)
    extract_tail(args.pi, READS, off_r2, out / "reads-phase2-idle.jsonl")
    p2 = parse_bursts(out / "reads-phase2-idle.jsonl")
    off_r3 = remote_size(args.pi, READS)
    d_rc2 = int(s2["readCount"] or 0) - int(s1["readCount"] or 0)

    # Phase 3: paced
    p3 = {"lines": 0, "sum_n": 0, "sum_bytes": 0}
    paced_meta = {"skipped": True}
    d_rc3 = 0
    if args.paced_s > 0 and s2.get("fav0_lba0") is not None:
        paced_meta = paced_fav0(
            args.host,
            args.dev,
            int(s2["fav0_lba0"]),
            int(s2["fav0_lba1"]),
            args.paced_s,
            args.kib_s,
        )
        after_paced = http_json(f"{esp}/api/status")
        (out / "status-03-after-paced.json").write_text(json.dumps(after_paced), encoding="utf-8")
        s3 = slim(after_paced)
        extract_tail(args.pi, READS, off_r3, out / "reads-phase3-paced.jsonl")
        p3 = parse_bursts(out / "reads-phase3-paced.jsonl")
        d_rc3 = int(s3["readCount"] or 0) - int(s2["readCount"] or 0)
    else:
        s3 = s2
        (out / "reads-phase3-paced.jsonl").write_text("", encoding="utf-8")

    cls = classify(d_rc1, d_rc2, d_rc3, args.idle_s)
    report = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "esp": esp,
        "geometry": "L0 lab 4MiB / 1MiB slots (static Mp3Silence)",
        "session": {"before": s0, "sweep_end": s1, "after_idle": s2, "after_paced": s3},
        "phase1_sweep": {"delta_readCount": d_rc1, "bursts": p1, "balance_ok": d_rc1 == p1["sum_n"]},
        "phase2_idle": {"delta_readCount": d_rc2, "bursts": p2, "idle_s": args.idle_s},
        "phase3_paced": {
            "delta_readCount": d_rc3,
            "bursts": p3,
            "paced_s": args.paced_s,
            "kib_s": args.kib_s,
            "meta": paced_meta,
        },
        "classification": cls,
        "equation_check_phase1": "ΔreadCount == Σ(burst.n)",
    }
    (out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (out / "EAR.txt").write_text(
        f"M3 lab timeline {stamp}\n"
        f"phase1 Δrc={d_rc1} Σn={p1['sum_n']} balance={d_rc1 == p1['sum_n']}\n"
        f"phase2 idle {args.idle_s}s Δrc={d_rc2}\n"
        f"phase3 paced {args.paced_s}s Δrc={d_rc3}\n"
        f"class {cls['code']}: {cls['detail']}\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2))
    print("OUT", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

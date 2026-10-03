#!/usr/bin/env python3
"""M3 Lab export calibration — Pre-Connect (A) and Burst-gap (B).

A: known host reads while bridge DOWN, then connect → measure export loss (ov=0 gap).
B: bridge UP, controlled dd bursts with gaps around kBurstGapMs=50 → M0 + LBA completeness.

Example:
  python3 tools/m3_lab_export_calib.py --esp http://192.168.178.88 \\
    --pi pidrive@192.168.178.105 --host root@192.168.178.108
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


def ssh(target: str, cmd: str, timeout: int = 120, check: bool = True) -> bytes:
    r = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", target, cmd],
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    if check and r.returncode != 0:
        raise subprocess.CalledProcessError(r.returncode, cmd, r.stdout, r.stderr)
    return r.stdout


def ensure_bridge(pi: str, esp_host: str, esp: str, no_audio: bool = True, retries: int = 4) -> None:
    flag = " --no-audio" if no_audio else ""
    last_err = ""
    for attempt in range(1, retries + 1):
        ssh(pi, "pkill -f '/home/pidrive/pump_bridge.py' || true", check=False)
        time.sleep(1.5)
        # Wait until ESP drops stale TCP before reconnecting (avoids BrokenPipe on hello)
        wait_tcp(esp, False, timeout=8.0)
        time.sleep(0.5)
        out = ssh(
            pi,
            f"setsid nohup /usr/bin/python3 -u /home/pidrive/pump_bridge.py --transport tcp "
            f"--host {esp_host} --tcp-port 9090 --interval 0.5 --bitrate 48k{flag} "
            f">>/tmp/pump_bridge_lab88_calib.log 2>&1 </dev/null & echo LIVE:$!",
            check=True,
        ).decode().strip()
        time.sleep(3.0)
        alive = ssh(pi, "pgrep -af '/home/pidrive/pump_bridge.py' || true", check=False).decode()
        tcp_ok = wait_tcp(esp, True, timeout=12.0)
        if "pump_bridge.py" in alive and tcp_ok:
            return
        last_err = f"attempt={attempt} start={out!r} alive={alive!r} tcp={tcp_ok}"
        ssh(pi, "pkill -f '/home/pidrive/pump_bridge.py' || true", check=False)
        time.sleep(1.0)
    raise RuntimeError(f"bridge failed to stay up: {last_err}")


def kill_bridge(pi: str, esp: str) -> None:
    for _ in range(5):
        ssh(pi, "pkill -9 -f '/home/pidrive/pump_bridge.py' || true", check=False)
        time.sleep(1.0)
        if wait_tcp(esp, False, timeout=5.0):
            return
    raise RuntimeError("kill_bridge: pumpTcpUp still true after pkill")


def bridge_alive(pi: str, esp: str) -> bool:
    alive = ssh(pi, "pgrep -af '/home/pidrive/pump_bridge.py' || true", check=False).decode()
    try:
        d = http_json(f"{esp}/api/status")
        return ("pump_bridge.py" in alive) and bool(d.get("pumpTcpUp"))
    except Exception:
        return False


def slim(d: dict) -> dict:
    m = d.get("msc") or {}
    return {
        "version": d.get("version"),
        "uptime": d.get("uptime"),
        "usbSerial": m.get("usbSerial"),
        "remountGen": m.get("remountGen"),
        "plugged": m.get("plugged"),
        "phase": m.get("phase"),
        "readCount": m.get("readCount"),
        "readsEmit": m.get("readsEmit"),
        "readOverflow": m.get("readOverflow"),
        "bytesFile": m.get("bytesFile"),
        "bytesRead": m.get("bytesRead"),
        "lastReadLba": m.get("lastReadLba"),
        "pumpTcpUp": d.get("pumpTcpUp"),
        "msSincePlug": m.get("msSincePlug"),
    }


def parse_reads(blob: bytes) -> list[dict]:
    rows = []
    for line in blob.decode("utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def sum_n(rows: list[dict]) -> int:
    return sum(int(o.get("n") or 0) for o in rows)


def sum_bytes(rows: list[dict]) -> int:
    return sum(int(o.get("bytes") or 0) for o in rows)


def truncate_traces(pi: str) -> None:
    # Copy then truncate SAME inode so an open bridge append-fd keeps writing
    # into the live file (mv + : > would orphan writes into the archive inode).
    ssh(
        pi,
        f"mkdir -p /tmp/msc_archive; ts=$(date +%H%M%S); "
        f"for f in {READS} {DIAG}; do "
        f"[ -s $f ] && cp -a $f /tmp/msc_archive/$(basename $f).pre-$ts; "
        f"truncate -s 0 $f || : > $f; chmod 666 $f; done; "
        f"wc -c {READS} {DIAG}",
    )


def remount(esp: str) -> dict:
    try:
        http_json(f"{esp}/api/lab/stop", method="POST", body=b"{}")
    except Exception:
        pass
    time.sleep(0.3)
    return http_json(f"{esp}/api/lab/remount", method="POST", body=b"{}")


def host_read_range(host: str, lba0: int, n_sectors: int, gap_s: float) -> dict:
    """Sequential dd of n_sectors as count=8 chunks (4 KiB), sleep gap_s between."""
    script = (
        "import time,subprocess\n"
        f"lba,n,gap,dev={lba0},{n_sectors},{gap_s},'/dev/sda'\n"
        "done=0; calls=0\n"
        "while done<n:\n"
        "  c=min(8,n-done)\n"
        "  subprocess.check_call(['dd','if=%s'%dev,'bs=512','skip=%d'%(lba+done),"
        "'count=%d'%c,'iflag=direct','status=none','of=/dev/null'],"
        "stderr=subprocess.DEVNULL)\n"
        "  done+=c; calls+=1\n"
        "  if gap>0: time.sleep(gap)\n"
        "import json\n"
        "print(json.dumps({'calls':calls,'sectors':done,'gap_s':gap}))\n"
    )
    out = ssh(host, "python3 - <<'PY'\n" + script + "PY").decode()
    return json.loads(out.strip().splitlines()[-1])

def wait_tcp(esp: str, want: bool, timeout: float = 20.0) -> bool:
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            d = http_json(f"{esp}/api/status")
            if bool(d.get("pumpTcpUp")) == want:
                return True
        except Exception:
            if not want:
                return True
        time.sleep(0.5)
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--esp", default="http://192.168.178.88")
    ap.add_argument("--pi", default="pidrive@192.168.178.105")
    ap.add_argument("--host", default="root@192.168.178.108")
    ap.add_argument("--esp-ip", default="192.168.178.88")
    ap.add_argument("--out", default="")
    ap.add_argument("--fav0-lba", type=int, default=81)
    args = ap.parse_args()
    esp = args.esp.rstrip("/")
    day = datetime.now().strftime("%Y-%m-%d")
    stamp = datetime.now().strftime("%H%M%S")
    out = Path(args.out) if args.out else Path(f"docs/betrieb/artifacts-{day}-m3/lab88-export-calib-{stamp}")
    out.mkdir(parents=True, exist_ok=True)

    report: dict = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "esp": esp,
        "note": "Lab export calibration A (pre-connect) + B (burst gaps)",
        "arms": {},
    }

    # Baseline: stop overlay, bridge on .88, truncate
    try:
        http_json(f"{esp}/api/lab/stop", method="POST", body=b"{}")
    except Exception:
        pass
    ensure_bridge(args.pi, args.esp_ip, esp, no_audio=True)
    assert wait_tcp(esp, True), "bridge tcp not up"
    truncate_traces(args.pi)
    time.sleep(0.5)
    st0 = http_json(f"{esp}/api/status")
    (out / "status-00-baseline.json").write_text(json.dumps(st0, indent=2), encoding="utf-8")

    # ---------- Arm A1: bridge UP, known reads (control) ----------
    off_a1 = int(ssh(args.pi, f"stat -c %s {READS}").decode().strip())
    before = slim(http_json(f"{esp}/api/status"))
    remount(esp)
    time.sleep(0.8)
    if not bridge_alive(args.pi, esp):
        ensure_bridge(args.pi, args.esp_ip, esp, no_audio=True)
    # 64 sectors = 8 calls × 8 sectors @ gap 0.08s (>50ms)
    stim = host_read_range(args.host, args.fav0_lba + 100, 64, 0.08)
    time.sleep(1.5)
    after = slim(http_json(f"{esp}/api/status"))
    blob = ssh(
        args.pi,
        f"python3 -c \"import sys;f=open('{READS}','rb');f.seek({off_a1});sys.stdout.buffer.write(f.read())\"",
    )
    rows = parse_reads(blob)
    d_rc = after["readCount"] - before["readCount"]
    d_em = after["readsEmit"] - before["readsEmit"]
    d_ov = after["readOverflow"] - before["readOverflow"]
    sn = sum_n(rows)
    report["arms"]["A1_bridge_up_control"] = {
        "stimulus": stim,
        "before": before,
        "after": after,
        "delta_readCount": d_rc,
        "delta_readsEmit": d_em,
        "delta_overflow": d_ov,
        "jsonl_lines": len(rows),
        "sum_burst_n": sn,
        "sum_bytes": sum_bytes(rows),
        "balance_ok": (d_rc == sn + d_ov),
        "export_complete_vs_rc": (sn == d_rc) if d_ov == 0 else None,
    }
    (out / "A1-reads.jsonl").write_bytes(blob)
    print("A1", json.dumps(report["arms"]["A1_bridge_up_control"], indent=2))

    # ---------- Arm A2: bridge DOWN during reads, then connect ----------
    kill_bridge(args.pi, esp)
    assert wait_tcp(esp, False, timeout=10), "A2: expected pumpTcpUp=false after kill"
    time.sleep(1)
    truncate_traces(args.pi)
    before = slim(http_json(f"{esp}/api/status"))
    assert before["pumpTcpUp"] is False, "A2 before: bridge still up"
    remount(esp)
    time.sleep(0.5)
    # Aggressive sweep while bridge down: 256 sectors (~32×4KiB)
    stim = host_read_range(args.host, args.fav0_lba + 200, 256, 0.0)
    time.sleep(0.5)
    mid = slim(http_json(f"{esp}/api/status"))
    assert mid["pumpTcpUp"] is False, "A2 mid: bridge came up during blind reads"
    # start bridge — any queued pending may flush; early reads may be gone
    ensure_bridge(args.pi, args.esp_ip, esp, no_audio=True)
    assert wait_tcp(esp, True, timeout=15), "A2: bridge did not come up"
    time.sleep(2.0)
    after = slim(http_json(f"{esp}/api/status"))
    blob = ssh(args.pi, f"python3 -c \"import sys;sys.stdout.buffer.write(open('{READS}','rb').read())\"")
    rows = parse_reads(blob)
    d_rc_blind = mid["readCount"] - before["readCount"]
    d_rc_total = after["readCount"] - before["readCount"]
    d_em = after["readsEmit"] - before["readsEmit"]
    d_ov = after["readOverflow"] - before["readOverflow"]
    sn = sum_n(rows)
    report["arms"]["A2_pre_connect_gap"] = {
        "stimulus_while_bridge_down": stim,
        "before": before,
        "after_blind_reads": mid,
        "after_bridge_up": after,
        "delta_rc_while_down": d_rc_blind,
        "delta_rc_total": d_rc_total,
        "delta_readsEmit_after_connect": d_em,
        "delta_overflow": d_ov,
        "jsonl_lines_after_connect": len(rows),
        "sum_burst_n": sn,
        "sum_bytes": sum_bytes(rows),
        "reads_not_in_export_estimate": max(0, d_rc_blind - sn),
        "export_fraction_of_blind_rc": round(sn / d_rc_blind, 4) if d_rc_blind else None,
        "interpretation": (
            "If export_fraction << 1 and overflow small: reads never queued (pre-bridge gap), "
            "not classic overflow. Operator: keep bridge up before plug/remount stimulus."
        ),
    }
    (out / "A2-reads.jsonl").write_bytes(blob)
    (out / "status-A2-mid.json").write_text(json.dumps(mid, indent=2), encoding="utf-8")
    print("A2", json.dumps(report["arms"]["A2_pre_connect_gap"], indent=2))

    # ---------- Arm B: burst gaps 10 / 50 / 100 ms ----------
    truncate_traces(args.pi)
    time.sleep(0.5)
    ensure_bridge(args.pi, args.esp_ip, esp, no_audio=True)
    assert wait_tcp(esp, True), "B: bridge tcp not up"
    b_results = []
    base_lba = args.fav0_lba + 500
    for gap_ms, nsec in [(10, 48), (50, 48), (100, 48)]:
        if not bridge_alive(args.pi, esp):
            ensure_bridge(args.pi, args.esp_ip, esp, no_audio=True)
        off = int(ssh(args.pi, f"stat -c %s {READS}").decode().strip())
        before = slim(http_json(f"{esp}/api/status"))
        stim = host_read_range(args.host, base_lba, nsec, gap_ms / 1000.0)
        base_lba += nsec + 16
        time.sleep(1.0)
        after = slim(http_json(f"{esp}/api/status"))
        blob = ssh(
            args.pi,
            f"python3 -c \"import sys;f=open('{READS}','rb');f.seek({off});sys.stdout.buffer.write(f.read())\"",
        )
        rows = parse_reads(blob)
        d_rc = after["readCount"] - before["readCount"]
        d_ov = after["readOverflow"] - before["readOverflow"]
        sn = sum_n(rows)
        starts = sorted({int(o["lba0"]) for o in rows if "lba0" in o})
        item = {
            "gap_ms": gap_ms,
            "stimulus": stim,
            "delta_readCount": d_rc,
            "delta_overflow": d_ov,
            "jsonl_lines": len(rows),
            "sum_burst_n": sn,
            "sum_bytes": sum_bytes(rows),
            "balance_ok": d_rc == sn + d_ov,
            "unique_lba0": len(starts),
            "export_complete": (d_ov == 0 and sn == d_rc),
            "bridge_alive": bridge_alive(args.pi, esp),
        }
        b_results.append(item)
        (out / f"B-gap{gap_ms}ms-reads.jsonl").write_bytes(blob)
        print("B", gap_ms, item)
        time.sleep(0.5)

    report["arms"]["B_burst_gaps"] = b_results

    # Verdict
    a2 = report["arms"]["A2_pre_connect_gap"]
    a1 = report["arms"]["A1_bridge_up_control"]
    report["verdict"] = {
        "A1_control_export_ok": bool(a1.get("export_complete_vs_rc")),
        "A2_pre_connect_loss": a2.get("export_fraction_of_blind_rc"),
        "A2_confirms_pre_bridge_gap": (
            a2.get("export_fraction_of_blind_rc") is not None
            and a2.get("export_fraction_of_blind_rc") < 0.5
            and (a2.get("delta_overflow") or 0)
            < max(1, (a2.get("delta_rc_while_down") or 0) // 4)
        ),
        "B_all_gaps_complete": all(x.get("export_complete") for x in b_results),
        "B_by_gap": {x["gap_ms"]: x.get("export_complete") for x in b_results},
        "operator_rule": "Bridge TCP up BEFORE remount/plug/host stimulus for quantitative M3seq.",
    }

    (out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    ear = [
        f"export-calib {stamp} ver={st0.get('version')}",
        f"A1 bridge-up control complete={report['verdict']['A1_control_export_ok']} "
        f"d_rc={a1['delta_readCount']} sum_n={a1['sum_burst_n']} ov={a1['delta_overflow']}",
        f"A2 pre-connect export_frac={a2.get('export_fraction_of_blind_rc')} "
        f"blind_rc={a2.get('delta_rc_while_down')} sum_n={a2.get('sum_burst_n')} ov={a2.get('delta_overflow')} "
        f"gap_confirmed={report['verdict']['A2_confirms_pre_bridge_gap']}",
        "B gaps: " + ", ".join(f"{x['gap_ms']}ms complete={x['export_complete']} d_rc={x['delta_readCount']} n={x['sum_burst_n']}" for x in b_results),
        report["verdict"]["operator_rule"],
    ]
    (out / "EAR.txt").write_text("\n".join(ear) + "\n", encoding="utf-8")
    print("OUT", out)
    print("VERDICT", json.dumps(report["verdict"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

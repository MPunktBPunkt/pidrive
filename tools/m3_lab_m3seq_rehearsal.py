#!/usr/bin/env python3
"""Lab M3seq rehearsal — Idle / Select-ohne-Remount / Soft-Remount (Lab-Host ≠ NBT).

Does not claim BMW answers for Q1–Q3. Produces calibrated Lab baselines:
  Arm0 idle after sweep
  Arm1 select fav1 LBAs without remount
  Arm3 soft remount scan

Example:
  python3 tools/m3_lab_m3seq_rehearsal.py --esp http://192.168.178.88 \\
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


def ensure_bridge(pi: str, esp_host: str, esp: str, retries: int = 4) -> None:
    for attempt in range(1, retries + 1):
        ssh(pi, "pkill -f '/home/pidrive/pump_bridge.py' || true", check=False)
        time.sleep(1.5)
        wait_tcp(esp, False, timeout=8.0)
        time.sleep(0.5)
        ssh(
            pi,
            f"setsid nohup /usr/bin/python3 -u /home/pidrive/pump_bridge.py --transport tcp "
            f"--host {esp_host} --tcp-port 9090 --interval 0.5 --bitrate 48k --no-audio "
            f">>/tmp/pump_bridge_lab88_m3seq.log 2>&1 </dev/null & echo LIVE:$!",
        )
        time.sleep(3.0)
        alive = ssh(pi, "pgrep -af '/home/pidrive/pump_bridge.py' || true", check=False).decode()
        if "pump_bridge.py" in alive and wait_tcp(esp, True, timeout=12.0):
            return
        ssh(pi, "pkill -f '/home/pidrive/pump_bridge.py' || true", check=False)
        time.sleep(1.0)
    raise RuntimeError(f"bridge failed after {retries} attempts")


def truncate_traces(pi: str) -> None:
    ssh(
        pi,
        f"mkdir -p /tmp/msc_archive; ts=$(date +%H%M%S); "
        f"for f in {READS} {DIAG}; do "
        f"[ -s $f ] && cp -a $f /tmp/msc_archive/$(basename $f).pre-$ts; "
        f"truncate -s 0 $f || : > $f; chmod 666 $f; done",
    )


def remount(esp: str) -> dict:
    try:
        http_json(f"{esp}/api/lab/stop", method="POST", body=b"{}")
    except Exception:
        pass
    time.sleep(0.3)
    return http_json(f"{esp}/api/lab/remount", method="POST", body=b"{}")


def host_nudge(host: str, sectors: int = 256) -> str:
    """Force Lab-Host to issue MSC reads after soft remount (Linux may otherwise stay quiet)."""
    return ssh(
        host,
        f"dd if=/dev/sda of=/dev/null bs=512 count={sectors} iflag=direct status=none; echo nudged:{sectors}",
    ).decode().strip()


def slim(d: dict) -> dict:
    m = d.get("msc") or {}
    slots = {}
    for s in m.get("slotMap") or []:
        uid = s.get("uid") or f"i{s.get('i')}"
        slots[uid] = {
            "lba0": s.get("lba0"),
            "lba1": s.get("lba1"),
            "bytes": s.get("bytes"),
            "maxSeq": s.get("maxSeq"),
            "fromHead": s.get("fromHead"),
        }
    return {
        "version": d.get("version"),
        "usbSerial": m.get("usbSerial"),
        "remountGen": m.get("remountGen"),
        "plugged": m.get("plugged"),
        "phase": m.get("phase"),
        "readCount": m.get("readCount"),
        "readsEmit": m.get("readsEmit"),
        "readOverflow": m.get("readOverflow"),
        "bytesFile": m.get("bytesFile"),
        "lastReadLba": m.get("lastReadLba"),
        "pumpTcpUp": d.get("pumpTcpUp"),
        "playingUid": d.get("playingUid"),
        "slots": slots,
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


def host_read_range(host: str, lba0: int, n_sectors: int, gap_s: float = 0.08) -> dict:
    script = (
        "import time,subprocess,json\n"
        f"lba,n,gap,dev={lba0},{n_sectors},{gap_s},'/dev/sda'\n"
        "done=0; calls=0\n"
        "while done<n:\n"
        "  c=min(8,n-done)\n"
        "  subprocess.check_call(['dd','if=%s'%dev,'bs=512','skip=%d'%(lba+done),"
        "'count=%d'%c,'iflag=direct','status=none','of=/dev/null'],"
        "stderr=subprocess.DEVNULL)\n"
        "  done+=c; calls+=1\n"
        "  if gap>0: time.sleep(gap)\n"
        "print(json.dumps({'calls':calls,'sectors':done,'gap_s':gap,'lba0':lba}))\n"
    )
    out = ssh(host, "python3 - <<'PY'\n" + script + "PY").decode()
    return json.loads(out.strip().splitlines()[-1])


def wait_idle(esp: str, stable_s: float = 8.0, timeout: float = 45.0) -> dict:
    """Wait until readCount unchanged for stable_s."""
    t0 = time.time()
    last = None
    since = time.time()
    while time.time() - t0 < timeout:
        st = slim(http_json(f"{esp}/api/status"))
        rc = st["readCount"]
        if last is None or rc != last:
            last = rc
            since = time.time()
        elif time.time() - since >= stable_s:
            return st
        time.sleep(0.5)
    return slim(http_json(f"{esp}/api/status"))


def fetch_reads(pi: str, offset: int) -> bytes:
    return ssh(
        pi,
        f"python3 -c \"import sys;f=open('{READS}','rb');f.seek({offset});"
        f"sys.stdout.buffer.write(f.read())\"",
    )


def arm_delta(before: dict, after: dict, rows: list[dict], stim: dict | None = None) -> dict:
    d_rc = after["readCount"] - before["readCount"]
    d_em = after["readsEmit"] - before["readsEmit"]
    d_ov = after["readOverflow"] - before["readOverflow"]
    sn = sum_n(rows)
    slot_bytes = {}
    for uid in sorted(set(before.get("slots", {})) | set(after.get("slots", {}))):
        b0 = (before.get("slots") or {}).get(uid, {}).get("bytes") or 0
        b1 = (after.get("slots") or {}).get(uid, {}).get("bytes") or 0
        if b1 != b0:
            slot_bytes[uid] = {"before": b0, "after": b1, "delta": b1 - b0}
    return {
        "stimulus": stim,
        "before": before,
        "after": after,
        "delta_readCount": d_rc,
        "delta_readsEmit": d_em,
        "delta_overflow": d_ov,
        "delta_remountGen": (after["remountGen"] or 0) - (before["remountGen"] or 0),
        "jsonl_lines": len(rows),
        "sum_burst_n": sn,
        "balance_ok": d_rc == sn + d_ov,
        "slot_bytes_delta": slot_bytes,
        "lastReadLba_after": after.get("lastReadLba"),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--esp", default="http://192.168.178.88")
    ap.add_argument("--pi", default="pidrive@192.168.178.105")
    ap.add_argument("--host", default="root@192.168.178.108")
    ap.add_argument("--esp-ip", default="192.168.178.88")
    ap.add_argument("--idle-s", type=float, default=30.0)
    ap.add_argument("--select-sectors", type=int, default=64)
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    esp = args.esp.rstrip("/")
    stamp = datetime.now().strftime("%H%M%S")
    day = datetime.now().strftime("%Y-%m-%d")
    out = Path(args.out) if args.out else Path(f"docs/betrieb/artifacts-{day}-m3/lab88-m3seq-rehearsal-{stamp}")
    out.mkdir(parents=True, exist_ok=True)

    report: dict = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "esp": esp,
        "note": "Lab M3seq rehearsal (Lab-Host ≠ NBT). Arms: idle / select-no-remount / soft-remount.",
        "arms": {},
    }

    try:
        http_json(f"{esp}/api/lab/stop", method="POST", body=b"{}")
    except Exception:
        pass
    ensure_bridge(args.pi, args.esp_ip, esp)
    truncate_traces(args.pi)

    # --- remount + host nudge + sweep settle ---
    remount(esp)
    time.sleep(1.0)
    if not wait_tcp(esp, True, timeout=12):
        ensure_bridge(args.pi, args.esp_ip, esp)
    nudge0 = host_nudge(args.host, 256)
    (out / "host-nudge-00.txt").write_text(nudge0 + "\n", encoding="utf-8")
    sweep_end = wait_idle(esp, stable_s=8.0, timeout=50.0)
    (out / "status-00-sweep-end.json").write_text(
        json.dumps(http_json(f"{esp}/api/status"), indent=2), encoding="utf-8"
    )
    fav1 = (sweep_end.get("slots") or {}).get("fav1") or {}
    fav1_lba0 = int(fav1.get("lba0") or 16465)
    print("sweep_end rc=", sweep_end["readCount"], "fav1_lba0=", fav1_lba0, flush=True)

    # --- Arm0 Idle ---
    off = int(ssh(args.pi, f"stat -c %s {READS}").decode().strip())
    before = slim(http_json(f"{esp}/api/status"))
    time.sleep(args.idle_s)
    after = slim(http_json(f"{esp}/api/status"))
    blob = fetch_reads(args.pi, off)
    rows = parse_reads(blob)
    arm0 = arm_delta(before, after, rows, stim={"kind": "idle", "s": args.idle_s})
    arm0["label"] = "S0_idle_after_sweep"
    arm0["expect"] = "delta_readCount≈0 (Lab-Host quiet after mount sweep)"
    report["arms"]["arm0_idle"] = arm0
    (out / "arm0-idle-reads.jsonl").write_bytes(blob)
    print("ARM0", json.dumps({k: arm0[k] for k in ("delta_readCount", "delta_overflow", "sum_burst_n", "balance_ok")}, indent=2), flush=True)

    # --- Arm1 Select without remount (fav1 head) ---
    if not wait_tcp(esp, True, timeout=5):
        ensure_bridge(args.pi, args.esp_ip, esp)
    off = int(ssh(args.pi, f"stat -c %s {READS}").decode().strip())
    before = slim(http_json(f"{esp}/api/status"))
    gen0 = before["remountGen"]
    stim = host_read_range(args.host, fav1_lba0, args.select_sectors, 0.08)
    time.sleep(1.2)
    after = slim(http_json(f"{esp}/api/status"))
    blob = fetch_reads(args.pi, off)
    rows = parse_reads(blob)
    arm1 = arm_delta(before, after, rows, stim=stim)
    arm1["label"] = "S1_select_fav1_no_remount"
    arm1["expect"] = "delta_readCount>0, remountGen unchanged, fav1 slot.bytes↑"
    arm1["remount_unchanged"] = after["remountGen"] == gen0
    arm1["fav1_bytes_grew"] = ((arm1.get("slot_bytes_delta") or {}).get("fav1") or {}).get("delta", 0) > 0
    report["arms"]["arm1_select_no_remount"] = arm1
    (out / "arm1-select-reads.jsonl").write_bytes(blob)
    (out / "status-arm1-after.json").write_text(
        json.dumps(http_json(f"{esp}/api/status"), indent=2), encoding="utf-8"
    )
    print(
        "ARM1",
        json.dumps(
            {
                k: arm1[k]
                for k in (
                    "delta_readCount",
                    "sum_burst_n",
                    "balance_ok",
                    "remount_unchanged",
                    "fav1_bytes_grew",
                    "slot_bytes_delta",
                )
            },
            indent=2,
        ),
        flush=True,
    )

    # --- Arm3a Soft remount WITHOUT host nudge (Lab-Host may stay quiet) ---
    if not wait_tcp(esp, True, timeout=5):
        ensure_bridge(args.pi, args.esp_ip, esp)
    truncate_traces(args.pi)
    time.sleep(0.3)
    before = slim(http_json(f"{esp}/api/status"))
    remount(esp)
    time.sleep(1.0)
    if not wait_tcp(esp, True, timeout=12):
        ensure_bridge(args.pi, args.esp_ip, esp)
    time.sleep(8.0)  # observe passive window
    mid = slim(http_json(f"{esp}/api/status"))
    blob_a = fetch_reads(args.pi, 0)
    rows_a = parse_reads(blob_a)
    arm3a = arm_delta(before, mid, rows_a, stim={"kind": "soft_remount_no_nudge", "observe_s": 8})
    arm3a["label"] = "SR_soft_remount_passive"
    arm3a["expect"] = "remountGen+1; Lab-Host Δrc may be 0 without nudge"
    report["arms"]["arm3a_remount_passive"] = arm3a
    (out / "arm3a-remount-passive-reads.jsonl").write_bytes(blob_a)
    print(
        "ARM3a",
        json.dumps(
            {k: arm3a[k] for k in ("delta_readCount", "delta_remountGen", "sum_burst_n", "balance_ok")},
            indent=2,
        ),
        flush=True,
    )

    # --- Arm3b Soft remount + host nudge → expect scan reads ---
    truncate_traces(args.pi)
    time.sleep(0.3)
    before = slim(http_json(f"{esp}/api/status"))
    remount(esp)
    time.sleep(1.0)
    if not wait_tcp(esp, True, timeout=12):
        ensure_bridge(args.pi, args.esp_ip, esp)
    nudge = host_nudge(args.host, 256)
    (out / "host-nudge-arm3b.txt").write_text(nudge + "\n", encoding="utf-8")
    after_scan = wait_idle(esp, stable_s=8.0, timeout=50.0)
    after = slim(http_json(f"{esp}/api/status"))
    blob = fetch_reads(args.pi, 0)
    rows = parse_reads(blob)
    arm3 = arm_delta(before, after, rows, stim={"kind": "soft_remount_plus_nudge", "nudge": nudge})
    arm3["label"] = "SR_soft_remount_nudged"
    arm3["expect"] = "remountGen+1 and delta_readCount>0 after host nudge"
    arm3["sweep_end_rc"] = after_scan["readCount"]
    report["arms"]["arm3b_remount_nudged"] = arm3
    (out / "arm3b-remount-nudged-reads.jsonl").write_bytes(blob)
    (out / "status-arm3b-after.json").write_text(
        json.dumps(http_json(f"{esp}/api/status"), indent=2), encoding="utf-8"
    )
    print(
        "ARM3b",
        json.dumps(
            {
                k: arm3[k]
                for k in ("delta_readCount", "delta_remountGen", "sum_burst_n", "balance_ok", "delta_overflow")
            },
            indent=2,
        ),
        flush=True,
    )

    report["verdict"] = {
        "arm0_idle_quiet": arm0["delta_readCount"] == 0 and arm0["delta_overflow"] == 0,
        "arm1_select_reads": arm1["delta_readCount"] > 0 and arm1.get("remount_unchanged") and arm1["balance_ok"],
        "arm1_fav1_attribution": bool(arm1.get("fav1_bytes_grew")),
        "arm3a_remount_gen_only": arm3a["delta_remountGen"] == 1,
        "arm3a_passive_quiet_ok": arm3a["delta_readCount"] == 0,  # Lab-Host finding
        "arm3b_remount_scan": arm3["delta_remountGen"] == 1 and arm3["delta_readCount"] > 0 and arm3["balance_ok"],
        "lab_host_note": (
            "Lab-Host: Select-ohne-Remount instrumentierbar; Soft-Remount allein erzeugt hier "
            "keine Reads (Nudge nötig). BMW Q1–Q3 bleiben Auto-only."
        ),
    }
    (out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    ear = [
        f"m3seq-rehearsal {stamp} ver={sweep_end.get('version')}",
        f"Arm0 idle Δrc={arm0['delta_readCount']} quiet={report['verdict']['arm0_idle_quiet']}",
        f"Arm1 select fav1 Δrc={arm1['delta_readCount']} sum_n={arm1['sum_burst_n']} "
        f"remount_unchanged={arm1.get('remount_unchanged')} fav1_bytes↑={arm1.get('fav1_bytes_grew')} "
        f"balance={arm1['balance_ok']}",
        f"Arm3a remount-passive Δrc={arm3a['delta_readCount']} Δgen={arm3a['delta_remountGen']}",
        f"Arm3b remount+nudge Δrc={arm3['delta_readCount']} Δgen={arm3['delta_remountGen']} "
        f"sum_n={arm3['sum_burst_n']} ov={arm3['delta_overflow']} balance={arm3['balance_ok']}",
        report["verdict"]["lab_host_note"],
    ]
    (out / "EAR.txt").write_text("\n".join(ear) + "\n", encoding="utf-8")
    print("OUT", out)
    print("VERDICT", json.dumps(report["verdict"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

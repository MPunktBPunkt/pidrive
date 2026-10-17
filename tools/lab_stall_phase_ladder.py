#!/usr/bin/env python3
"""Lab Stall-Leiter in drei Phasen: Menü → ID3 → Audio (Messinstrument).

Firmware gate: stallMaxMs ≤ 15000. Ladder: 0, 1, 2, 5, 10, 15 s.
Writes VORHERSAGE.json before each phase. Soft-Cycle freeze gate: caller must
keep stall off between Soft-USB matrix runs.

Phases (Lab Linux host via SG_IO — never plain read()/dd as MSC truth):
  menu  — LBA 0..63 style meta (MBR/FAT/DIR region)
  id3   — fav0 file head (sticky ID3), after pump arm
  audio — fav0 body at id3Len offset, 240-block CBW, after play.guess path

Example:
  python3 tools/lab_stall_phase_ladder.py \\
    --esp http://192.168.178.88 --host root@192.168.178.108 --pct 100 \\
    --phases menu,id3,audio --ms 0,1000,2000 \\
    -o docs/betrieb/artifacts-2026-10-17-lab/stall-ladder-smoke
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

DEFAULT_MS = [0, 1000, 2000, 5000, 10000, 15000]


def http_json(url: str, method: str = "GET", body: dict | None = None, timeout: float = 25) -> dict:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def set_stall(esp: str, enable: bool, max_ms: int, scope: int = 2) -> dict:
    """scope=2: all live-body reads (lab QD/timeout probe). scope=1: only after play.guess."""
    return http_json(
        f"{esp.rstrip('/')}/api/config",
        "POST",
        {
            "stallEnable": enable,
            "stallScope": scope if enable else 1,
            "stallTimer": 0,  # cmd
            "stallMaxMs": max_ms,
            "stallChunkBytes": 4096,
            "stallRetryMs": 2,
        },
    )


def stall_off(esp: str) -> dict:
    try:
        http_json(f"{esp.rstrip('/')}/api/lab/situation", "POST", {"name": "stall_off"})
    except Exception:
        pass
    return set_stall(esp, False, 1000, scope=1)


def snap(esp: str) -> dict:
    st = http_json(f"{esp.rstrip('/')}/api/status")
    m = st.get("msc") or {}
    s = m.get("stream") or {}
    stall = m.get("stall") or {}
    return {
        "ts": time.time(),
        "version": st.get("version"),
        "playingUid": st.get("playingUid"),
        "otgUp": st.get("otgUp"),
        "pumpTcpUp": st.get("pumpTcpUp"),
        "freeHeap": st.get("freeHeap"),
        "bytesRead": m.get("bytesRead"),
        "readCount": m.get("readCount"),
        "lastReadLba": m.get("lastReadLba"),
        "usbSerial": m.get("usbSerial"),
        "stall": {
            k: stall.get(k)
            for k in (
                "enable",
                "armed",
                "maxMs",
                "scope",
                "cmds",
                "retries",
                "partials",
                "timeouts",
                "waitMsMax",
                "waitMsLast",
                "botResets",
            )
            if k in stall or True
        },
        "stream": {
            k: s.get(k)
            for k in (
                "active",
                "id3Len",
                "cursorArmed",
                "hostAbsCursor",
                "absBase",
                "absEnd",
                "underruns",
                "size",
            )
        },
        "http_alive": True,
    }


def host_exec(host: str, pct: int, cmd: str, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", host, "pct", "exec", str(pct), "--", "bash", "-lc", cmd],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def push_sgio(host: str, pct: int) -> None:
    src = ROOT / "tools" / "sgio_read10.py"
    subprocess.run(
        ["scp", "-o", "BatchMode=yes", str(src), f"{host}:/tmp/sgio_read10.py"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["ssh", "-o", "BatchMode=yes", host, "pct", "push", str(pct), "/tmp/sgio_read10.py", "/tmp/sgio_read10.py"],
        check=True,
        capture_output=True,
    )


def sgio_read(host: str, pct: int, sg: str, lba: int, blocks: int, timeout_ms: int) -> dict:
    remote = (
        "python3 - <<'PY'\n"
        "import json,sys\n"
        "sys.path.insert(0,'/tmp')\n"
        "import sgio_read10 as s, os\n"
        f"fd=os.open({sg!r}, os.O_RDWR)\n"
        "try:\n"
        f"  data, meta = s.read10(fd, {lba}, {blocks}, timeout_ms={timeout_ms})\n"
        "finally:\n"
        "  os.close(fd)\n"
        "meta['first16']=data[:16].hex()\n"
        "meta['starts_id3']=data.startswith(b'ID3')\n"
        "print(json.dumps(meta))\n"
        "PY"
    )
    # Host SG timeout must exceed stallMaxMs
    r = host_exec(host, pct, remote, timeout=max(60, timeout_ms // 1000 + 30))
    if r.returncode != 0:
        return {"error": "host_fail", "stderr": (r.stderr or "")[:800], "stdout": (r.stdout or "")[:400]}
    try:
        return json.loads((r.stdout or "").strip().splitlines()[-1])
    except Exception as e:
        return {"error": f"parse:{e}", "stdout": (r.stdout or "")[:400]}


def ensure_id3(esp: str, esp_ip: str) -> dict:
    from nbt_hu_sim import prep_lab, arm_uid, KIND_AUDIO, make_pdsq_chunk  # type: ignore

    pump = prep_lab(esp, esp_ip, None, remount=False)
    arm_uid(pump, "fav0", 3200)
    for i in range(48):
        pump.send_bin(KIND_AUDIO, make_pdsq_chunk(i, i * 256, 256))
    time.sleep(0.25)
    st = snap(esp)
    try:
        # keep pump open? close to avoid holding socket across long stalls
        pump.close()
    except Exception:
        pass
    return st


def phase_prediction(phase: str, ms: int) -> dict:
    return {
        "phase": phase,
        "stallMaxMs": ms,
        "predict": {
            "menu": "Meta READ opens; UI/host waits ≤ stallMaxMs then data or silence fallback; botResets==0 expected under 15s Lab SG timeout",
            "id3": "Head READ returns ID3 if stall allows; starts_id3 True; underruns stay 0 for first id3Len",
            "audio": "240-block body READ stays single outstanding (QD=1); retries rise with ms; no second LBA while first open",
        }.get(phase, ""),
        "measure": [
            "stall.retries",
            "stall.waitMsMax",
            "stall.timeouts",
            "stall.botResets",
            "http_alive",
            "host wall_ms",
            "esp Δbytes",
        ],
    }


def run_step(
    *,
    esp: str,
    esp_ip: str,
    host: str,
    pct: int,
    sg: str,
    phase: str,
    ms: int,
    out_dir: Path,
) -> dict:
    pred = phase_prediction(phase, ms)
    (out_dir / f"VORHERSAGE-{phase}-{ms}ms.json").write_text(json.dumps(pred, indent=2) + "\n")

    stall_off(esp)
    if phase in ("id3", "audio"):
        ensure_id3(esp, esp_ip)

    st = http_json(f"{esp.rstrip('/')}/api/status")
    slots = (st.get("msc") or {}).get("slotMap") or []
    fav0 = next((s for s in slots if s.get("uid") == "fav0"), {"lba0": 81})
    lba0 = int(fav0["lba0"])
    id3_len = int(((st.get("msc") or {}).get("stream") or {}).get("id3Len") or 3200)

    if phase == "menu":
        lba, blocks = 0, 8
        scope = 2
    elif phase == "id3":
        lba, blocks = lba0, 16  # 8 KiB head covers 3200 ID3
        scope = 2
    else:  # audio
        # first body CBW after ID3
        lba = lba0 + (id3_len + 511) // 512
        blocks = 240
        scope = 2

    enable = ms > 0
    cfg = set_stall(esp, enable, max(ms, 1) if enable else 1000, scope=scope)
    before = snap(esp)
    http_json(
        f"{esp.rstrip('/')}/api/lab/mess",
        "POST",
        {"enable": True, "reset": True, "mode": "ram_local", "mark": f"stall_{phase}_{ms}"},
    )

    # SG timeout: stall wait + transfer margin
    sg_timeout = max(8000, ms + 5000)
    host_row = sgio_read(host, pct, sg, lba, blocks, sg_timeout)
    time.sleep(0.2)
    after = snap(esp)
    http_json(f"{esp.rstrip('/')}/api/lab/mess", "POST", {"stop": True, "reason": f"stall_{phase}_{ms}"})

    row = {
        "phase": phase,
        "stallMaxMs": ms,
        "lba": lba,
        "blocks": blocks,
        "config": cfg,
        "before": before,
        "after": after,
        "host": host_row,
        "d_bytes": int(after.get("bytesRead") or 0) - int(before.get("bytesRead") or 0),
        "d_retries": int((after.get("stall") or {}).get("retries") or 0)
        - int((before.get("stall") or {}).get("retries") or 0),
        "d_timeouts": int((after.get("stall") or {}).get("timeouts") or 0)
        - int((before.get("stall") or {}).get("timeouts") or 0),
        "botResets": (after.get("stall") or {}).get("botResets"),
        "http_alive": True,
        "prediction": pred,
    }
    stall_off(esp)
    (out_dir / f"step-{phase}-{ms}ms.json").write_text(json.dumps(row, indent=2) + "\n")
    return row


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--esp", default="http://192.168.178.88")
    ap.add_argument("--esp-ip", default="192.168.178.88")
    ap.add_argument("--host", default="root@192.168.178.108")
    ap.add_argument("--pct", type=int, default=100)
    ap.add_argument("--sg", default="/dev/sg0")
    ap.add_argument("--phases", default="menu,id3,audio")
    ap.add_argument("--ms", default=",".join(str(x) for x in DEFAULT_MS))
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    phases = [p.strip() for p in args.phases.split(",") if p.strip()]
    ms_list = [int(x) for x in args.ms.split(",") if x.strip()]

    plan = {
        "phases": phases,
        "stallMaxMs": ms_list,
        "method": "SG_IO + MessCapture; stall as HU measuring instrument",
        "fw_limit_ms": 15000,
        "note_qd1": "Audio phase: while 240-block READ open under BUSY, watch for second LBA in capture",
    }
    (out / "PLAN.json").write_text(json.dumps(plan, indent=2) + "\n")
    if args.dry_run:
        print(json.dumps(plan, indent=2))
        return 0

    push_sgio(args.host, args.pct)
    rows: list[dict[str, Any]] = []
    try:
        for phase in phases:
            for ms in ms_list:
                print(f"=== {phase} stallMaxMs={ms} ===", flush=True)
                row = run_step(
                    esp=args.esp,
                    esp_ip=args.esp_ip,
                    host=args.host,
                    pct=args.pct,
                    sg=args.sg,
                    phase=phase,
                    ms=ms,
                    out_dir=out,
                )
                rows.append(row)
                print(
                    json.dumps(
                        {
                            "phase": phase,
                            "ms": ms,
                            "d_bytes": row["d_bytes"],
                            "d_retries": row["d_retries"],
                            "host_err": row["host"].get("error"),
                            "wall_ms": row["host"].get("wall_ms"),
                            "starts_id3": row["host"].get("starts_id3"),
                        }
                    ),
                    flush=True,
                )
    finally:
        stall_off(args.esp)

    summary = {
        "n": len(rows),
        "rows": [
            {
                "phase": r["phase"],
                "ms": r["stallMaxMs"],
                "d_bytes": r["d_bytes"],
                "d_retries": r["d_retries"],
                "d_timeouts": r["d_timeouts"],
                "wall_ms": (r.get("host") or {}).get("wall_ms"),
                "starts_id3": (r.get("host") or {}).get("starts_id3"),
                "error": (r.get("host") or {}).get("error"),
            }
            for r in rows
        ],
    }
    (out / "SUMMARY.json").write_text(json.dumps(summary, indent=2) + "\n")
    md = ["# Stall-Phasen-Leiter", "", f"Phasen: `{phases}` · ms: `{ms_list}`", ""]
    md += ["| phase | ms | Δbytes | Δretries | wall_ms | id3 | err |", "|---|---:|---:|---:|---:|:---:|---|"]
    for r in summary["rows"]:
        md.append(
            f"| {r['phase']} | {r['ms']} | {r['d_bytes']} | {r['d_retries']} | {r['wall_ms']} | {r['starts_id3']} | {r['error'] or ''} |"
        )
    (out / "ERGEBNIS.md").write_text("\n".join(md) + "\n")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

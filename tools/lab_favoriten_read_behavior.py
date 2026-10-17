#!/usr/bin/env python3
"""Favoriten-Layout read-behavior: Soft-Cycle / Root / Favoriten — MSC truth via SG_IO.

Replaces the earlier dd-triggered C-phase (methodik: no dd/read as MSC proof).

Example:
  python3 tools/lab_favoriten_read_behavior.py \\
    -o docs/betrieb/artifacts-2026-10-17-lab/favoriten-read-behavior-sgio-01
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

# L3 geometry
BANDS = [
    ("boot", 0, 0),
    ("fat", 1, 32),
    ("root", 33, 64),
    ("dir_favoriten", 65, 72),
    ("dir_menue", 73, 80),
    ("file_fav0", 81, 16464),
    ("file_fav1", 16465, 17488),
    ("file_fav2", 17489, 18512),
    ("file_menue", 18513, 18525),
]


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


def host_exec(host: str, pct: int, cmd: str, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", host, "pct", "exec", str(pct), "--", "bash", "-lc", cmd],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def push_sgio(host: str, pct: int) -> None:
    src = ROOT / "tools" / "sgio_read10.py"
    subprocess.run(["scp", "-o", "BatchMode=yes", str(src), f"{host}:/tmp/sgio_read10.py"], check=True, capture_output=True)
    subprocess.run(
        ["ssh", "-o", "BatchMode=yes", host, "pct", "push", str(pct), "/tmp/sgio_read10.py", "/tmp/sgio_read10.py"],
        check=True,
        capture_output=True,
    )


def sgio(host: str, pct: int, sg: str, lba: int, blocks: int) -> dict:
    remote = (
        "python3 - <<'PY'\n"
        "import json,sys,os\n"
        "sys.path.insert(0,'/tmp')\n"
        "import sgio_read10 as s\n"
        f"fd=os.open({sg!r}, os.O_RDWR)\n"
        "try:\n"
        f"  data, meta = s.read10(fd, {lba}, {blocks}, timeout_ms=8000)\n"
        "finally:\n"
        "  os.close(fd)\n"
        "print(json.dumps(meta))\n"
        "PY"
    )
    r = host_exec(host, pct, remote, timeout=30)
    if r.returncode != 0:
        return {"error": "host_fail", "stderr": (r.stderr or "")[:400]}
    try:
        return json.loads((r.stdout or "").strip().splitlines()[-1])
    except Exception as e:
        return {"error": f"parse:{e}", "stdout": (r.stdout or "")[:200]}


def classify(lba: int) -> str:
    for name, a, b in BANDS:
        if a <= lba <= b:
            return name
    return "other"


def mess_cmds(esp: str) -> list[dict]:
    mess = http_json(f"{esp.rstrip('/')}/api/lab/mess")
    cmds = list(mess.get("cmds") or [])
    after = 0
    for _ in range(40):
        page = http_json(f"{esp.rstrip('/')}/api/lab/mess?after={after}")
        pc = page.get("cmds") or []
        if not pc:
            break
        cmds.extend(pc)
        seqs = [c.get("seq") for c in pc if c.get("seq") is not None]
        nxt = page.get("nextAfter") or page.get("nextSeq") or page.get("next")
        if nxt is not None:
            after = int(nxt)
        elif seqs:
            after = max(int(x) for x in seqs) + 1
        else:
            break
    seen: set = set()
    out = []
    for c in cmds:
        s = c.get("seq")
        if s in seen:
            continue
        if s is not None:
            seen.add(s)
        out.append(c)
    return out


def summarize(cmds: list[dict], label: str) -> dict:
    read10 = [c for c in cmds if int(c.get("op") or 0) == 40]
    bands: Counter = Counter()
    for c in read10:
        bands[classify(int(c.get("lba") or 0))] += 1
    file_bands = sorted(k for k in bands if k.startswith("file_fav"))
    return {
        "label": label,
        "read10_n": len(read10),
        "bands": dict(sorted(bands.items())),
        "file_slot_reads": sum(v for k, v in bands.items() if k.startswith("file_")),
        "unique_file_bands": file_bands,
        "method": "SG_IO + MessCapture ram_local",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--esp", default="http://192.168.178.88")
    ap.add_argument("--host", default="root@192.168.178.108")
    ap.add_argument("--pct", type=int, default=100)
    ap.add_argument("--sg", default="/dev/sg0")
    ap.add_argument("-o", "--out", required=True)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    esp = args.esp.rstrip("/")

    push_sgio(args.host, args.pct)
    try:
        http_json(f"{esp}/api/lab/situation", "POST", {"name": "stall_off"})
    except Exception:
        pass
    try:
        http_json(f"{esp}/api/lab/stop", "POST", {})
    except Exception:
        pass

    # A: soft-cycle alone
    http_json(f"{esp}/api/lab/mess", "POST", {"enable": True, "reset": True, "mode": "ram_local", "mark": "fav_A"})
    http_json(f"{esp}/api/lab/situation", "POST", {"name": "usb_cycle", "holdMs": 700, "keepIdentity": True})
    time.sleep(8.0)
    http_json(f"{esp}/api/lab/mess", "POST", {"stop": True, "reason": "A"})
    sum_a = summarize(mess_cmds(esp), "A_soft_cycle_alone")

    # B: remount + SG_IO root sector only (no file LBA)
    http_json(f"{esp}/api/lab/mess", "POST", {"enable": True, "reset": True, "mode": "ram_local", "mark": "fav_B"})
    http_json(f"{esp}/api/lab/situation", "POST", {"name": "media_remount", "keepIdentity": True})
    time.sleep(1.0)
    sgio(args.host, args.pct, args.sg, 33, 8)  # root
    sgio(args.host, args.pct, args.sg, 65, 8)  # Favoriten DIR
    time.sleep(0.3)
    http_json(f"{esp}/api/lab/mess", "POST", {"stop": True, "reason": "B"})
    sum_b = summarize(mess_cmds(esp), "B_root_and_favoriten_dir_sgio")

    # C: SG_IO heads of fav0/1/2
    st = http_json(f"{esp}/api/status")
    slots = {(s.get("uid")): s for s in ((st.get("msc") or {}).get("slotMap") or [])}
    http_json(f"{esp}/api/lab/mess", "POST", {"enable": True, "reset": True, "mode": "ram_local", "mark": "fav_C"})
    for uid in ("fav0", "fav1", "fav2"):
        lba0 = int((slots.get(uid) or {}).get("lba0") or {"fav0": 81, "fav1": 16465, "fav2": 17489}[uid])
        sgio(args.host, args.pct, args.sg, lba0, 16)
        time.sleep(0.05)
    time.sleep(0.3)
    http_json(f"{esp}/api/lab/mess", "POST", {"stop": True, "reason": "C"})
    sum_c = summarize(mess_cmds(esp), "C_three_station_heads_sgio")

    result = {
        "version": st.get("version"),
        "phases": [sum_a, sum_b, sum_c],
        "method_note": "All host triggers are SG_IO (METHODIK-MSC-WAHRHEIT).",
        "gate": {
            "C_all_three": set(sum_c["unique_file_bands"]) >= {"file_fav0", "file_fav1", "file_fav2"},
            "B_no_fav12": "file_fav1" not in sum_b["unique_file_bands"] and "file_fav2" not in sum_b["unique_file_bands"],
        },
    }
    (out / "ERGEBNIS.json").write_text(json.dumps(result, indent=2) + "\n")
    lines = ["# Favoriten read-behavior (SG_IO)", "", f"FW `{result.get('version')}`", ""]
    for s in result["phases"]:
        lines.append(f"- **{s['label']}**: READ10={s['read10_n']} file={s['file_slot_reads']} bands={s['unique_file_bands']}")
    lines += ["", f"gate: {result['gate']}", ""]
    (out / "ERGEBNIS.md").write_text("\n".join(lines))
    print(json.dumps(result, indent=2))
    return 0 if result["gate"]["C_all_three"] else 2


if __name__ == "__main__":
    sys.exit(main())

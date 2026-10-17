#!/usr/bin/env python3
"""Q10 calibration: known SG_IO READ10 sizes vs ESP MessCapture.

Method rule (2026-10-17): host read()/dd on /dev/sda can hit page cache while
ESP Δbytes=0. This tool always uses SG_IO on /dev/sg0 (via CT100 pct exec).

Example:
  python3 tools/lab_q10_calibrate.py \\
    --esp http://192.168.178.88 \\
    --host root@192.168.178.108 --pct 100 \\
    -o docs/betrieb/artifacts-2026-10-17-lab/q10-calib-01
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
SGIO_SRC = ROOT / "tools" / "sgio_read10.py"

Q10_PLAN = [
    ("r512", 300, 1),
    ("r4k", 0, 8),
    ("r16k", 100, 32),
    ("r64k", 200, 128),
    ("r120k", 400, 240),
]


def http_json(url: str, method: str = "GET", body: dict | None = None, timeout: float = 20) -> dict:
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
    # host filesystem then pct push
    subprocess.run(
        ["scp", "-o", "BatchMode=yes", str(SGIO_SRC), f"{host}:/tmp/sgio_read10.py"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["ssh", "-o", "BatchMode=yes", host, "pct", "push", str(pct), "/tmp/sgio_read10.py", "/tmp/sgio_read10.py"],
        check=True,
        capture_output=True,
    )


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
    return cmds


def analyze(requested: list[dict], cmds: list[dict], bytes_before: int, bytes_after: int) -> dict:
    read10 = [c for c in cmds if int(c.get("op") or 0) == 40]
    hist = Counter(int(c.get("blocks") or 0) for c in read10)
    by_lba = {int(c["lba"]): c for c in read10 if c.get("lba") is not None}
    matches = []
    for req in requested:
        lba = int(req["lba"])
        want = int(req["blocks"])
        hit = by_lba.get(lba)
        got_blocks = int(hit.get("blocks") or 0) if hit else None
        matches.append(
            {
                "tag": req.get("tag"),
                "lba": lba,
                "req_blocks": want,
                "esp_blocks": got_blocks,
                "match": got_blocks == want,
                "esp_bytes": int(hit.get("bytes") or 0) if hit else None,
            }
        )
    return {
        "esp_delta_bytes": bytes_after - bytes_before,
        "esp_read10_n": len(read10),
        "esp_blocks_hist": {str(k): v for k, v in sorted(hist.items())},
        "matches": matches,
        "all_match": all(m["match"] for m in matches) and len(matches) == len(requested),
        "method": "SG_IO on /dev/sg0 + MessCapture ram_local",
        "note": "Host read()/dd is NOT valid for Q10; page-cache can show data with ESP Δbytes=0.",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--esp", default="http://192.168.178.88")
    ap.add_argument("--host", default="root@192.168.178.108")
    ap.add_argument("--pct", type=int, default=100)
    ap.add_argument("--sg", default="/dev/sg0")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    prediction = {
        "claim": "Each SG_IO READ10 (lba,blocks) appears as one ESP MessCapture op=40 with same lba/blocks",
        "plan": [{"tag": t, "lba": l, "blocks": b, "bytes": b * 512} for t, l, b in Q10_PLAN],
        "reject_if": "ESP hist differs from requested, or ESP Δbytes == 0 while host got data",
    }
    (out / "VORHERSAGE.json").write_text(json.dumps(prediction, indent=2) + "\n")

    if args.dry_run:
        print(json.dumps(prediction, indent=2))
        return 0

    st0 = http_json(f"{args.esp.rstrip('/')}/api/status")
    bytes0 = int((st0.get("msc") or {}).get("bytesRead") or 0)
    (out / "status-before.json").write_text(json.dumps(st0, indent=2))

    http_json(
        f"{args.esp.rstrip('/')}/api/lab/mess",
        "POST",
        {"enable": True, "reset": True, "mode": "ram_local", "mark": "q10_calib"},
    )

    push_sgio(args.host, args.pct)
    remote = (
        "python3 - <<'PY'\n"
        "import json, sys\n"
        "sys.path.insert(0, '/tmp')\n"
        "import sgio_read10 as s\n"
        f"plan = {[(t, l, b) for t, l, b in Q10_PLAN]!r}\n"
        f"rows = s.run_plan({args.sg!r}, plan)\n"
        "print(json.dumps(rows))\n"
        "PY"
    )
    r = host_exec(args.host, args.pct, remote, timeout=90)
    (out / "host-sgio.stdout").write_text(r.stdout or "")
    (out / "host-sgio.stderr").write_text(r.stderr or "")
    if r.returncode != 0:
        print("host SG_IO failed", r.returncode, r.stderr[:500], file=sys.stderr)
        http_json(f"{args.esp.rstrip('/')}/api/lab/mess", "POST", {"stop": True, "reason": "q10_host_fail"})
        return 2

    try:
        host_rows = json.loads((r.stdout or "").strip().splitlines()[-1])
    except Exception as e:
        print("parse host rows failed", e, r.stdout[:300], file=sys.stderr)
        return 2
    (out / "host-sgio.json").write_text(json.dumps(host_rows, indent=2) + "\n")

    time.sleep(0.3)
    stop = http_json(
        f"{args.esp.rstrip('/')}/api/lab/mess",
        "POST",
        {"stop": True, "reason": "q10_calib_done", "mark": "q10_stop"},
    )
    cmds = mess_cmds(args.esp)
    (out / "mess-cmds.json").write_text(json.dumps(cmds, indent=2) + "\n")

    st1 = http_json(f"{args.esp.rstrip('/')}/api/status")
    bytes1 = int((st1.get("msc") or {}).get("bytesRead") or 0)
    (out / "status-after.json").write_text(json.dumps(st1, indent=2))

    result = analyze(host_rows, cmds, bytes0, bytes1)
    result["host_rows"] = host_rows
    result["stop"] = {"ok": bool(stop)}
    result["version"] = st1.get("version")
    (out / "ERGEBNIS.json").write_text(json.dumps(result, indent=2) + "\n")

    lines = [
        "# Q10 Kalibrierung (SG_IO)",
        "",
        f"- ESP `{args.esp}` · FW `{result.get('version')}`",
        f"- Methode: **SG_IO** `{args.sg}` via `{args.host}` pct {args.pct}",
        f"- ESP Δbytes: **{result['esp_delta_bytes']}** · READ10 n={result['esp_read10_n']}",
        f"- blocks_hist: `{result['esp_blocks_hist']}`",
        f"- all_match: **{result['all_match']}**",
        "",
        "| tag | LBA | req | esp | match |",
        "|-----|----:|----:|----:|:-----:|",
    ]
    for m in result["matches"]:
        lines.append(
            f"| {m['tag']} | {m['lba']} | {m['req_blocks']} | {m['esp_blocks']} | {'☑' if m['match'] else '☐'} |"
        )
    lines += ["", result["note"], ""]
    (out / "ERGEBNIS.md").write_text("\n".join(lines))
    print(json.dumps({k: result[k] for k in ("all_match", "esp_delta_bytes", "esp_blocks_hist", "matches")}, indent=2))
    return 0 if result["all_match"] and result["esp_delta_bytes"] > 0 else 3


if __name__ == "__main__":
    sys.exit(main())

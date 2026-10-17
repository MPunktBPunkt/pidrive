#!/usr/bin/env python3
"""Lab M22: Head-Tip play.guess on Favoriten-layout slots (SG_IO only).

Field 0.4.53 Bayern LIVE had playGuessCount=0 while stream.active — Stall scope=1
would not arm (R30). This probe checks MSC Head-READ on fav0/fav1 under FAVORITEN/.

Example:
  python3 tools/lab_play_guess_favoriten.py \\
    -o docs/betrieb/artifacts-2026-10-17-lab/play-guess-favoriten-01
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))


def http_json(url: str, method: str = "GET", body: dict | None = None, timeout: float = 12) -> dict:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data is not None else {},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        return json.loads(raw.decode()) if raw else {}


def snap(esp: str) -> dict:
    d = http_json(f"{esp.rstrip('/')}/api/status")
    m = d.get("msc") or {}
    st = d.get("stream") or m.get("stream") or {}
    stall = m.get("stall") or {}
    return {
        "version": d.get("version"),
        "playingUid": d.get("playingUid"),
        "playGuessCount": m.get("playGuessCount"),
        "playRejectCount": m.get("playRejectCount"),
        "stream_active": st.get("active"),
        "stream_uid": st.get("uid"),
        "stall_enable": stall.get("enable"),
        "stall_armed": stall.get("armed"),
        "slotMap": [
            {"uid": s.get("uid"), "path": s.get("path"), "lba0": s.get("lba0")}
            for s in (m.get("slotMap") or [])
        ],
    }


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


def sgio_read(host: str, pct: int, sg: str, lba: int, blocks: int) -> dict:
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
        "meta['first16']=data[:16].hex()\n"
        "meta['starts_id3']=data.startswith(b'ID3')\n"
        "print(json.dumps(meta))\n"
        "PY"
    )
    r = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", host, "pct", "exec", str(pct), "--", "bash", "-lc", remote],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if r.returncode != 0:
        return {"error": "host_fail", "stderr": (r.stderr or "")[:500]}
    try:
        return json.loads((r.stdout or "").strip().splitlines()[-1])
    except Exception as e:
        return {"error": str(e), "stdout": (r.stdout or "")[:300]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--esp", default="http://192.168.178.88")
    ap.add_argument("--host", default="root@192.168.178.108")
    ap.add_argument("--pct", type=int, default=100)
    ap.add_argument("--sg", default="/dev/sg0")
    ap.add_argument("--uids", default="fav0,fav1")
    ap.add_argument("-o", required=True)
    args = ap.parse_args()
    out = Path(args.o)
    out.mkdir(parents=True, exist_ok=True)

    http_json(f"{args.esp.rstrip('/')}/api/config", "POST", {"stallEnable": False})
    try:
        http_json(f"{args.esp.rstrip('/')}/api/lab/stop", "POST", {})
    except Exception:
        pass
    time.sleep(0.2)
    try:
        http_json(
            f"{args.esp.rstrip('/')}/api/lab/situation",
            "POST",
            {"name": "media_remount", "keepIdentity": True},
        )
    except Exception:
        pass
    time.sleep(1.0)

    push_sgio(args.host, args.pct)
    before = snap(args.esp)
    (out / "before.json").write_text(json.dumps(before, indent=2) + "\n")
    slots = {s["uid"]: s for s in before.get("slotMap") or []}

    rows = []
    for uid in [u.strip() for u in args.uids.split(",") if u.strip()]:
        slot = slots.get(uid)
        if not slot or slot.get("lba0") is None:
            rows.append({"uid": uid, "error": "no_lba0", "slot": slot})
            continue
        g0 = int(snap(args.esp).get("playGuessCount") or 0)
        # clear playing between tips so already_playing does not block re-arm
        try:
            http_json(f"{args.esp.rstrip('/')}/api/lab/stop", "POST", {})
        except Exception:
            pass
        time.sleep(0.2)
        host = sgio_read(args.host, args.pct, args.sg, int(slot["lba0"]), 16)
        time.sleep(0.5)
        after = snap(args.esp)
        g1 = int(after.get("playGuessCount") or 0)
        row = {
            "uid": uid,
            "path": slot.get("path"),
            "lba0": slot.get("lba0"),
            "host": host,
            "guess_before": g0,
            "guess_after": g1,
            "guess_delta": g1 - g0,
            "playingUid": after.get("playingUid"),
            "stall_armed": after.get("stall_armed"),
        }
        rows.append(row)
        (out / f"step-{uid}.json").write_text(json.dumps(row, indent=2) + "\n")
        print(json.dumps(row, ensure_ascii=False), flush=True)

    summary = {
        "fw": before.get("version"),
        "method": "SG_IO Head 16 blocks @ slot.lba0 (METHODIK)",
        "rows": rows,
        "any_guess": any(int(r.get("guess_delta") or 0) > 0 for r in rows),
        "field_note": "Bayern LIVE had playGuessCount=0 — lab must still arm via Head-READ before Stall scope=1",
    }
    (out / "SUMMARY.json").write_text(json.dumps(summary, indent=2) + "\n")
    lines = [
        "# Play-Guess Favoriten (Lab M22)",
        "",
        f"FW `{summary['fw']}` · SG_IO Head",
        "",
        "| uid | path | Δguess | playing | id3 |",
        "|---|---|---:|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r.get('uid')} | `{r.get('path')}` | {r.get('guess_delta')} | "
            f"{r.get('playingUid')!r} | {(r.get('host') or {}).get('starts_id3')} |"
        )
    lines += ["", f"**any_guess:** {summary['any_guess']}", ""]
    (out / "ERGEBNIS.md").write_text("\n".join(lines))
    return 0 if summary["any_guess"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

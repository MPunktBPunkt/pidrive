#!/usr/bin/env python3
"""Lab overnight: soft-usb cycle + targeted host READ10 capture, looping until deadline."""
from __future__ import annotations
import datetime as dt
import json
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

ESP = "http://192.168.178.88"
HOST_SSH = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", "root@192.168.178.108"]
OUT = Path(__file__).resolve().parent
INTERVAL_S = 480  # 8 min
# run until 05:00 UTC = 07:00 CEST
DEADLINE = dt.datetime(2026, 10, 17, 5, 0, tzinfo=dt.timezone.utc)

def http(method: str, path: str, body=None, timeout=20):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        ESP + path,
        data=data,
        headers={"Content-Type": "application/json"} if data else {},
        method=method,
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)

def status():
    return http("GET", "/api/status")

def append(name: str, obj):
    with (OUT / name).open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n")

def panicish(st: dict) -> str | None:
    reason = str(st.get("resetReason") or "").lower()
    if any(x in reason for x in ("panic", "brownout", "watchdog", "wdt")):
        return reason
    return None

def host_read() -> dict:
    cmd = (
        "pct exec 100 -- bash -lc "
        "'dd if=/dev/sda of=/dev/null bs=512 count=64 status=none; "
        "dd if=/dev/sda of=/dev/null bs=512 skip=8000 count=32 status=none; "
        "echo OK'"
    )
    try:
        p = subprocess.run(HOST_SSH + [cmd], capture_output=True, text=True, timeout=40)
        return {"rc": p.returncode, "out": (p.stdout or "").strip(), "err": (p.stderr or "").strip()[:300]}
    except Exception as e:
        return {"rc": -1, "error": f"{type(e).__name__}: {e}"}

def one_round(n: int) -> dict:
    t0 = time.time()
    before = status()
    up0 = before.get("uptimeMs")
    if panicish(before):
        return {"n": n, "hard_stop": "panic-before", "reason": panicish(before), "status": before}

    http("POST", "/api/lab/mess", {"enable": True, "reset": True, "mode": "ram_local", "mark": f"ovn_{n}"})
    # soft usb cycle keepIdentity
    sit = http("POST", "/api/lab/situation", {"name": "usb_cycle", "holdMs": 900, "keepIdentity": True})
    time.sleep(2.5)
    hr = host_read()
    time.sleep(0.6)
    stop = http("POST", "/api/lab/mess", {"stop": True, "reason": f"ovn_{n}_done", "mark": f"ovn_{n}_stop"})
    mess = http("GET", "/api/lab/mess")
    after = status()
    up1 = after.get("uptimeMs")
    cmds = mess.get("cmds") or []
    read10 = [c for c in cmds if c.get("op") == 40]
    hard = None
    if panicish(after):
        hard = f"panic:{panicish(after)}"
    elif up0 is not None and up1 is not None and int(up1) < int(up0):
        hard = "uptime-rollback"
    row = {
        "n": n,
        "wall": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "dur_s": round(time.time() - t0, 2),
        "sit_ok": sit.get("ok"),
        "host": hr,
        "read10_n": len(read10),
        "cmds": mess.get("mess", mess).get("cmds") if isinstance(mess.get("mess"), dict) else mess.get("cmds"),
        "mess_cmds": (stop.get("mess") or {}).get("cmds"),
        "mess_complete": (stop.get("mess") or {}).get("complete"),
        "usb_detach_n": (after.get("mess") or {}).get("usbDetachN"),
        "ser": (after.get("msc") or {}).get("usbSerial"),
        "phase": (after.get("msc") or {}).get("phase"),
        "uptime_ms": up1,
        "hard_stop": hard,
        "lbAs": [c.get("lba") for c in read10[:8]],
    }
    # fix cmds count from stop mess
    row["mess_cmds"] = (stop.get("mess") or {}).get("cmds")
    row["read10_n"] = sum(1 for c in cmds if c.get("op") == 40)
    if not cmds and (stop.get("mess") or {}).get("cmds"):
        # pageless: use count only
        pass
    append("rounds.jsonl", row)
    return row

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    meta = {
        "esp": ESP,
        "interval_s": INTERVAL_S,
        "deadline": DEADLINE.isoformat(),
        "started": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "method": "usb_cycle keepIdentity + CT100 dd READ + ram_local capture",
    }
    (OUT / "run-manifest.json").write_text(json.dumps(meta, indent=2) + "\n")
    append("events.jsonl", {"event": "run.start", **meta})
    n = 0
    while dt.datetime.now(dt.timezone.utc) < DEADLINE:
        n += 1
        try:
            row = one_round(n)
        except Exception as e:
            row = {"n": n, "error": f"{type(e).__name__}: {e}", "wall": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
            append("rounds.jsonl", row)
            append("events.jsonl", {"event": "round.error", **row})
            time.sleep(30)
            continue
        append("events.jsonl", {"event": "round.ok" if not row.get("hard_stop") else "round.hard_stop", "n": n, "read10_n": row.get("read10_n"), "hard_stop": row.get("hard_stop")})
        print(json.dumps({"n": n, "read10": row.get("read10_n"), "hard": row.get("hard_stop"), "host": row.get("host")}, ensure_ascii=False), flush=True)
        if row.get("hard_stop"):
            append("events.jsonl", {"event": "run.hard_stop", "n": n, "reason": row["hard_stop"]})
            break
        # sleep remaining interval
        left = (DEADLINE - dt.datetime.now(dt.timezone.utc)).total_seconds()
        if left <= 0:
            break
        time.sleep(min(INTERVAL_S, left))
    append("events.jsonl", {"event": "run.end", "rounds": n, "wall": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")})
    # summary
    rounds = [json.loads(l) for l in (OUT / "rounds.jsonl").read_text().splitlines() if l.strip()]
    summary = {
        "rounds": len(rounds),
        "read10_total": sum(int(r.get("read10_n") or 0) for r in rounds),
        "hard_stops": [r for r in rounds if r.get("hard_stop")],
        "errors": [r for r in rounds if r.get("error")],
        "last": rounds[-1] if rounds else None,
    }
    (OUT / "ERGEBNIS.json").write_text(json.dumps(summary, indent=2) + "\n")
    print("DONE", json.dumps(summary), flush=True)

if __name__ == "__main__":
    main()

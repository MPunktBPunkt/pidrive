#!/usr/bin/env python3
"""E7 Delay-/Pacing-Leiter (Audit msc-lba-timing-instrument × Stall-Build-Spec).

Stufe A — Host-Toleranz (künstliche Wartezeit je 4‑KiB-Callback):
  Misst, ab welchem cmd-Timeout der Lab-Host (Linux SG) abbricht.
  Mit Stall-FW: stallMaxMs-Leiter + stallEnable (Daten warten).
  Ohne Stall-FW: nur --cmd-timeout-ms Leiter gegen heutiges Burst-Verhalten (Baseline).

Stufe B — Live-Pacing-Protokoll (Sollwerte Spec L1/L2):
  Erwartet stallEnable + Producer @bps; prüft sg_ms_per_4k ≈ 4096/bps*1000
  und Lesedauer ≈ Slot/bps nach Vorsprung.

Beispiele:
  python3 tools/lab_e7_delay_ladder.py --mode math
  python3 tools/lab_e7_delay_ladder.py --mode A --esp http://192.168.4.1 --sg /dev/sg0
  python3 tools/lab_e7_delay_ladder.py --mode B --esp http://192.168.4.1 --sg /dev/sg0 \\
      --stall-ready --bps 6000

Siehe docs/planung/MASSNAHMEN-E7-AUDIT-ABGLEICH-2026-10-12.md
     docs/planung/STALL-BUILD-SPEC-2026-10-08.md
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

# Spec / Audit defaults
STUFE_A_MS = [100, 250, 500, 700, 1000, 2000, 5000, 11000]
STUFE_A_INJECT_US = [0, 100, 250, 500, 700, 1000, 2000, 5000, 10000, 100000, 1000000]
SLOT_BYTES = 512 * 1024
CALLBACK = 4096


def http_json(url: str, method: str = "GET", body: dict | None = None, timeout: float = 12) -> dict:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def math_report(bps: int) -> dict:
    ms_4k = CALLBACK / bps * 1000.0
    ms_512 = 512 / bps * 1000.0
    ms_64k = 65536 / bps * 1000.0
    slot_s = SLOT_BYTES / bps
    return {
        "bps": bps,
        "callback_B": CALLBACK,
        "ms_per_4kib": round(ms_4k, 2),
        "ms_per_512B": round(ms_512, 2),
        "ms_per_64kib_cmd": round(ms_64k, 2),
        "slot_read_s_paced": round(slot_s, 2),
        "ring_48kib_s": round(49152 / bps, 2),
        "note": "E7 braucht Host-Toleranz ≥ ms_per_4kib (Gesamtdauer) oder "
        "Inaktivität-Reset durch 512-B-Teilantworten alle ms_per_512B",
    }


def set_stall(esp: str, **fields: Any) -> dict:
    """POST /api/config stall* fields (no-op keys ignored by older FW)."""
    body = dict(fields)
    try:
        return http_json(f"{esp.rstrip('/')}/api/config", "POST", body)
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}", "body": e.read().decode(errors="replace")[:400]}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


def get_status(esp: str) -> dict:
    return http_json(f"{esp.rstrip('/')}/api/status")


def run_stufe_a_config_ladder(esp: str, out: Path, dry: bool) -> list[dict]:
    """Drive stallMaxMs ladder via config (requires Stall-Build)."""
    rows = []
    for ms in STUFE_A_MS:
        row: dict[str, Any] = {"stallMaxMs": ms}
        if dry:
            row["action"] = "dry"
            rows.append(row)
            print(f"A dry stallMaxMs={ms}")
            continue
        cfg = set_stall(
            esp,
            stallEnable=True,
            stallScope=1,
            stallTimer=0,
            stallMaxMs=ms,
            stallChunkBytes=4096,
            stallRetryMs=2,
        )
        row["config"] = cfg
        try:
            st = get_status(esp)
            stall = (st.get("msc") or {}).get("stall") or {}
            row["stall_status"] = stall
            row["ok"] = stall.get("enable") is True or cfg.get("config", {}).get("stallEnable") is True
        except Exception as e:
            row["ok"] = False
            row["status_error"] = f"{type(e).__name__}: {e}"
        rows.append(row)
        print(f"A stallMaxMs={ms} ok={row.get('ok')} stall={row.get('stall_status')}")
        time.sleep(0.3)
    (out / "stufe-a-config.json").write_text(json.dumps(rows, indent=2))
    return rows


def run_stufe_a_sg_timeout(
    sim_py: Path, esp: str, sg: str, out: Path, timeouts_ms: list[int]
) -> list[dict]:
    """Baseline: REPLUG with shrinking SG cmd-timeout (Linux host patience)."""
    import subprocess

    rows = []
    for tmo in timeouts_ms:
        dest = out / f"sg-timeout-{tmo}"
        dest.mkdir(parents=True, exist_ok=True)
        cmd = [
            sys.executable,
            str(sim_py),
            "--golden",
            "REPLUG",
            "--esp",
            esp,
            "--sg",
            sg,
            "--out",
            str(dest),
            "--cmd-timeout-ms",
            str(tmo),
            "--replug-cmd-kib",
            "4",
        ]
        print("RUN", " ".join(cmd))
        p = subprocess.run(cmd, capture_output=True, text=True)
        row: dict[str, Any] = {
            "cmd_timeout_ms": tmo,
            "returncode": p.returncode,
            "out": str(dest),
        }
        report = dest / "report.json"
        if report.exists():
            try:
                row["report"] = json.loads(report.read_text())
            except json.JSONDecodeError:
                row["report_error"] = "bad json"
        if p.returncode != 0:
            row["stderr_tail"] = (p.stderr or "")[-500:]
        rows.append(row)
        print(f"  rc={p.returncode}")
    (out / "stufe-a-sg-timeout.json").write_text(json.dumps(rows, indent=2))
    return rows


def eval_stufe_b_report(report: dict, bps: int) -> dict:
    """Pass/fail hints against Spec L1 numbers."""
    want_ms = CALLBACK / bps * 1000.0
    sg = report.get("sg_ms_per_4k") or {}
    p50 = sg.get("p50") if isinstance(sg, dict) else None
    und = report.get("undDelta")
    live_s = report.get("live_s_at_bps") or report.get("live_s")
    return {
        "want_ms_per_4k": round(want_ms, 1),
        "got_ms_per_4k_p50": p50,
        "paced_like_L1": p50 is not None and abs(float(p50) - want_ms) < want_ms * 0.35,
        "undDelta": und,
        "undDelta_ok": und == 0 or und is None,
        "live_s": live_s,
        "hint": "Nach Vorsprung p50≈683ms @48k; undDelta=0; Lesedauer≈87s",
    }


def run_stufe_b(
    sim_py: Path, esp: str, sg: str, out: Path, bps: int, chunk: int, stall_max_ms: int
) -> dict:
    import subprocess

    set_stall(
        esp,
        stallEnable=True,
        stallScope=1,
        stallTimer=0 if chunk >= 4096 else 1,
        stallMaxMs=stall_max_ms,
        stallChunkBytes=chunk,
        stallRetryMs=2,
    )
    dest = out / f"stufe-b-chunk{chunk}"
    dest.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        str(sim_py),
        "--golden",
        "REPLUG",
        "--esp",
        esp,
        "--sg",
        sg,
        "--out",
        str(dest),
        "--replug-bps",
        str(bps),
        "--replug-cmd-kib",
        "4",
        "--cmd-timeout-ms",
        str(max(5000, stall_max_ms + 2000)),
    ]
    print("RUN", " ".join(cmd))
    p = subprocess.run(cmd, capture_output=True, text=True)
    result: dict[str, Any] = {"returncode": p.returncode, "out": str(dest), "chunk": chunk}
    report_path = dest / "report.json"
    if report_path.exists():
        rep = json.loads(report_path.read_text())
        result["report"] = rep
        result["eval"] = eval_stufe_b_report(rep, bps)
    else:
        result["stderr_tail"] = (p.stderr or "")[-800:]
    (out / f"stufe-b-chunk{chunk}.json").write_text(json.dumps(result, indent=2))
    return result


def protocol_checklist() -> dict:
    return {
        "stufe_A": {
            "goal": "Host-Abort-Schwelle je 4 KiB Callback",
            "steps_ms": STUFE_A_MS,
            "inject_us_audit": STUFE_A_INJECT_US,
            "hosts": ["PC/dd", "Lab-ESP+nbt_hu_sim", "BMW NBT"],
            "pass": "max dt ohne Abort bekannt; HU vs PC getrennt",
        },
        "stufe_B": {
            "goal": "Live-Pacing: return 0 + Teilantwort 512 B",
            "L1": "stallMaxMs=1000 chunk=4096 → sg_ms_per_4k≈683 @48k",
            "L2": "chunk=512 → partials>0, gleiche Lesedauer",
            "L3": "stallMaxMs=300 → timeouts>0, Stille-Fallback",
            "L4": "cmd-timeout 500 < stall → botResets, ESP stabil",
        },
        "freeze": "stallEnable default false; Auto nur mit Go",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="E7 delay/pacing ladder (Audit × Stall-Spec)")
    ap.add_argument("--mode", choices=("math", "A", "B", "protocol"), default="math")
    ap.add_argument("--esp", default="http://192.168.4.1")
    ap.add_argument("--sg", default="")
    ap.add_argument("--bps", type=int, default=6000)
    ap.add_argument("--out", type=Path, default=Path("artifacts/lab-e7-ladder"))
    ap.add_argument("--stall-ready", action="store_true", help="FW has stall* config keys")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--chunk", type=int, default=4096, choices=(512, 1024, 2048, 4096))
    ap.add_argument("--stall-max-ms", type=int, default=1000)
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1]
    sim_py = root / "tools" / "nbt_hu_sim.py"
    args.out.mkdir(parents=True, exist_ok=True)

    summary: dict[str, Any] = {
        "mode": args.mode,
        "math": math_report(args.bps),
        "protocol": protocol_checklist(),
    }

    if args.mode == "math":
        print(json.dumps(summary["math"], indent=2))
    elif args.mode == "protocol":
        print(json.dumps(summary["protocol"], indent=2))
    elif args.mode == "A":
        if args.stall_ready:
            summary["stufe_A_config"] = run_stufe_a_config_ladder(args.esp, args.out, args.dry)
        if args.sg and not args.dry:
            summary["stufe_A_sg"] = run_stufe_a_sg_timeout(
                sim_py, args.esp, args.sg, args.out, [5000, 2000, 1000, 500, 300]
            )
        elif not args.stall_ready:
            print(
                "Hinweis: ohne --stall-ready und ohne --sg nur Math/Protokoll. "
                "SG-Timeout-Baseline: --sg /dev/sgN; Config-Leiter: --stall-ready",
                file=sys.stderr,
            )
    elif args.mode == "B":
        if not args.stall_ready:
            print("Stufe B braucht Stall-Build (--stall-ready) und --sg", file=sys.stderr)
            return 2
        if not args.sg and not args.dry:
            print("--sg erforderlich", file=sys.stderr)
            return 2
        if args.dry:
            summary["stufe_B"] = {"dry": True, "eval_want": eval_stufe_b_report({}, args.bps)}
        else:
            summary["stufe_B"] = run_stufe_b(
                sim_py, args.esp, args.sg, args.out, args.bps, args.chunk, args.stall_max_ms
            )

    (args.out / "summary.json").write_text(json.dumps(summary, indent=2))
    print(f"wrote {args.out / 'summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

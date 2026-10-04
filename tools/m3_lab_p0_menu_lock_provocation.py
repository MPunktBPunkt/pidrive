#!/usr/bin/env python3
"""P0 provocation: Pi-UI menu change must not overwrite MSC names while USB plugged.

Starts pump_bridge locally against lab ESP, seals favorites, then rewrites
/tmp/pidrive_menu.json to Zurueck/Ausgang/Auto and checks /api/menu unchanged.

Example:
  python3 tools/m3_lab_p0_menu_lock_provocation.py --esp-ip 192.168.178.88
"""
from __future__ import annotations

import argparse
import json
import subprocess
import time
import urllib.request
from pathlib import Path

MENU = Path("/tmp/pidrive_menu.json")
LOCK_LOG = Path("/tmp/pidrive_msc_lock.jsonl")
BRIDGE = Path("/home/martin/projects/esphub/esp32.pidrive/tools/pump_bridge.py")


def http_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=8) as r:
        return json.loads(r.read().decode())


def menu_names(esp: str) -> list[str]:
    doc = http_json(esp.rstrip("/") + "/api/menu")
    return [str(i.get("name") or "") for i in (doc.get("menu") or {}).get("items") or []]


def write_menu(rev: int, nodes: list[dict], path_ids: list | None = None) -> None:
    MENU.write_text(
        json.dumps(
            {
                "rev": rev,
                "path_ids": path_ids or ["root"],
                "nodes": nodes,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--esp", default="http://192.168.178.88")
    ap.add_argument("--esp-ip", default="192.168.178.88")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    stamp = time.strftime("%H%M")
    day = time.strftime("%Y-%m-%d")
    out = Path(args.out) if args.out else Path(
        f"docs/betrieb/artifacts-{day}-lab/lab88-p0-lock-{stamp}"
    )
    out.mkdir(parents=True, exist_ok=True)

    st = http_json(args.esp.rstrip("/") + "/api/status")
    plugged = bool((st.get("msc") or {}).get("plugged"))
    if not plugged:
        raise SystemExit("ESP not plugged — P0 provocation needs USB host session")

    try:
        LOCK_LOG.write_text("")
    except OSError:
        pass

    # Root menu → bridge publishes station presets (fav*)
    write_menu(
        5001,
        [
            {"uid": "folder:x", "id": "x", "label": "Ignore", "type": "folder"},
        ],
        ["root"],
    )

    log_path = out / "bridge.log"
    proc = subprocess.Popen(
        [
            "python3",
            str(BRIDGE),
            "--transport",
            "tcp",
            "--host",
            args.esp_ip,
            "--no-audio",
            "--msc-lock",
            "--interval",
            "0.4",
        ],
        stdout=log_path.open("w"),
        stderr=subprocess.STDOUT,
        text=True,
    )

    sealed_names: list[str] = []
    try:
        deadline = time.time() + 25
        while time.time() < deadline:
            time.sleep(0.5)
            text = log_path.read_text(encoding="utf-8", errors="replace")
            if "MSC_MAP_FROZEN" in text:
                sealed_names = menu_names(args.esp)
                break
        if not sealed_names:
            raise SystemExit(f"timeout waiting for freeze; see {log_path}")

        (out / "menu-after-seal.json").write_text(
            json.dumps(http_json(args.esp.rstrip("/") + "/api/menu"), indent=2)
        )
        print(f"sealed={sealed_names}", flush=True)

        # Provoke Pi-UI overwrite (historic field failure mode)
        write_menu(
            5002,
            [
                {
                    "uid": "1977938832270506073",
                    "id": "back",
                    "label": "Zurueck",
                    "type": "action",
                },
                {
                    "uid": "18330258143618563731",
                    "id": "out",
                    "label": "Ausgang klinke",
                    "type": "info",
                },
                {
                    "uid": "16678805154550120858",
                    "id": "auto",
                    "label": "Auto",
                    "type": "action",
                },
                {
                    "uid": "pump:page_next",
                    "id": "more",
                    "label": "Mehr... (+7)",
                    "type": "action",
                },
            ],
            ["settings"],  # non-root → page_items, not presets
        )

        time.sleep(6.0)
        after = menu_names(args.esp)
        (out / "menu-after-provoke.json").write_text(
            json.dumps(http_json(args.esp.rstrip("/") + "/api/menu"), indent=2)
        )
        bridge_tail = log_path.read_text(encoding="utf-8", errors="replace")
        lock_txt = LOCK_LOG.read_text(encoding="utf-8", errors="replace") if LOCK_LOG.exists() else ""
        (out / "msc_lock.jsonl").write_text(lock_txt)

        rejected = "frozen_reject" in bridge_tail or '"op":"reject"' in lock_txt
        stable = after == sealed_names
        # Also fail if classic bug names appeared
        bug = any(n in after for n in ("Zurueck", "Ausgang klinke", "Auto"))
        verdict = "PASS" if stable and rejected and not bug else "FAIL"
        report = {
            "verdict": verdict,
            "sealed_names": sealed_names,
            "after_names": after,
            "stable": stable,
            "rejected_logged": rejected,
            "bug_names_present": bug,
            "fw": st.get("version"),
            "serial": (st.get("msc") or {}).get("usbSerial"),
        }
        (out / "report.json").write_text(json.dumps(report, indent=2))
        (out / "EAR.txt").write_text(
            "\n".join(
                [
                    f"P0 menu-lock provocation {day} {stamp}",
                    f"verdict={verdict}",
                    f"sealed={sealed_names}",
                    f"after={after}",
                    f"stable={stable} rejected_logged={rejected} bug={bug}",
                    "",
                ]
            )
        )
        print(json.dumps(report, indent=2))
        print(f"artefacts: {out}")
        return 0 if verdict == "PASS" else 1
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())

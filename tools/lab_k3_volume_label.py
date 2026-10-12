#!/usr/bin/env python3
"""K3b Volume-Label-Isolation (P2) — braucht FW mit volumeLabel + keepIdentity.

Serial bleibt (remountKeepIdentity), nur FAT-Volume-Label wechselt.
Ziel: prüfen, ob die HU P / Cache über das Label mit-indexiert.

  # Label setzen + Remount ohne Serial-Bump
  python3 tools/lab_k3_volume_label.py --esp http://192.168.4.1 --label PIDRIVE2

  # Zurück auf Kopplung an remountGen (leerer Override)
  python3 tools/lab_k3_volume_label.py --esp http://192.168.4.1 --label '' --bump

Siehe docs/planung/MASSNAHMEN-E7-AUDIT-ABGLEICH-2026-10-12.md
"""
from __future__ import annotations

import argparse
import json
import urllib.request


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


def main() -> int:
    ap = argparse.ArgumentParser(description="Volume-Label isolieren (Serial konstant)")
    ap.add_argument("--esp", default="http://192.168.4.1")
    ap.add_argument("--label", default="PIDRIVE2", help="FAT label ≤11; '' = Override aus")
    ap.add_argument("--bump", action="store_true", help="auch Serial bumpen (klassischer Remount)")
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    esp = args.esp.rstrip("/")
    label = (args.label or "")[:11]
    cfg_body = {"volumeLabel": label}
    remount_body = {"keepIdentity": not args.bump, "volumeLabel": label}

    before = http_json(f"{esp}/api/status")
    msc0 = before.get("msc") or {}
    print(
        f"before serial={msc0.get('usbSerial')} vol={msc0.get('volumeLabel')} "
        f"gen={msc0.get('remountGen')}"
    )

    if args.dry:
        print("dry config", cfg_body, "remount", remount_body)
        return 0

    http_json(f"{esp}/api/config", "POST", cfg_body)
    http_json(f"{esp}/api/lab/remount", "POST", remount_body)

    after = http_json(f"{esp}/api/status")
    msc1 = after.get("msc") or {}
    print(
        f"after  serial={msc1.get('usbSerial')} vol={msc1.get('volumeLabel')} "
        f"gen={msc1.get('remountGen')}"
    )
    same_ser = msc0.get("usbSerial") == msc1.get("usbSerial")
    print(f"serial_unchanged={same_ser} (want True without --bump)")
    return 0 if (args.bump or same_ser) else 1


if __name__ == "__main__":
    raise SystemExit(main())

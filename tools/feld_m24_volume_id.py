#!/usr/bin/env python3
"""Feld M24: rotate ONLY BPB Volume-ID (keep USB serial) — NBT folder-cache probe.

Hypothesis (Grok/Claude): NBT shows flat titles because media index is keyed on
Volume-ID; DIR clusters are read but UI stays cached until BPB ID changes.

Lab already proved config+SG_IO BPB update (claude-triage-lab-01).
This script is for the car: change ID → remount → operator checks NBT folders.

Example (OTG unplugged or after unplug recommended):
  python3 tools/feld_m24_volume_id.py --esp http://192.168.178.89 \\
    -o docs/betrieb/artifacts-2026-10-17-feld/m24-volume-id-01

Then: OTG plug, note whether Favoriten/Menue appear. Do NOT bump serial (M25 is separate).
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.request
from pathlib import Path


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


def identity(esp: str) -> dict:
    d = http_json(f"{esp.rstrip('/')}/api/status")
    m = d.get("msc") or {}
    return {
        "version": d.get("version"),
        "otgUp": d.get("otgUp"),
        "resetReason": d.get("resetReason"),
        "uptime": d.get("uptime"),
        "usbSerial": m.get("usbSerial"),
        "bpbVolumeId": m.get("bpbVolumeId"),
        "bpbVolumeIdOverride": m.get("bpbVolumeIdOverride"),
        "volumeLabel": m.get("volumeLabel"),
        "rootLabel": m.get("rootLabel"),
        "remountGen": m.get("remountGen"),
        "productRevision": m.get("productRevision"),
        "paths": [s.get("path") for s in (m.get("slotMap") or [])],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--esp", default="http://192.168.178.89")
    ap.add_argument("--new-vid", type=lambda x: int(x, 0), default=0, help="0 = time-based")
    ap.add_argument("-o", required=True)
    ap.add_argument("--apply", action="store_true", help="write config + remount (default: dry status only)")
    args = ap.parse_args()
    out = Path(args.o)
    out.mkdir(parents=True, exist_ok=True)

    before = identity(args.esp)
    (out / "before.json").write_text(json.dumps(before, indent=2) + "\n")
    print("BEFORE", json.dumps(before, ensure_ascii=False))

    if not args.apply:
        print("dry-run only (pass --apply to rotate Volume-ID)")
        (out / "ERGEBNIS.md").write_text(
            "# M24 dry-run\n\nPass `--apply` with OTG preferably out, then plug and check folders.\n"
        )
        return 0

    if before.get("otgUp"):
        print("WARN: otgUp=true — prefer unplug before identity change, continuing anyway")

    new_vid = args.new_vid or (int(time.time()) & 0xFFFFFFFF)
    if new_vid == 0:
        new_vid = 0x51F17D01
    if new_vid == before.get("bpbVolumeId"):
        new_vid = (new_vid + 0x11111111) & 0xFFFFFFFF

    cfg = http_json(f"{args.esp.rstrip('/')}/api/config", "POST", {"fatVolumeId": new_vid})
    (out / "config.json").write_text(json.dumps({"requested": new_vid, "response_ok": cfg.get("ok")}, indent=2) + "\n")

    sit = http_json(
        f"{args.esp.rstrip('/')}/api/lab/situation",
        "POST",
        {"name": "media_remount", "keepIdentity": True},
    )
    (out / "remount.json").write_text(json.dumps(sit, indent=2) + "\n")
    time.sleep(1.5)

    after = identity(args.esp)
    (out / "after.json").write_text(json.dumps(after, indent=2) + "\n")
    print("AFTER", json.dumps(after, ensure_ascii=False))

    ok_vol = after.get("bpbVolumeId") == new_vid
    ok_ser = after.get("usbSerial") == before.get("usbSerial") and after.get("usbSerial")
    gate = {
        "volume_id_changed": ok_vol and after.get("bpbVolumeId") != before.get("bpbVolumeId"),
        "serial_unchanged": ok_ser,
        "new_vid": new_vid,
        "operator": [
            "OTG stecken",
            "NBT: erscheinen Favoriten/Menue als Ordner?",
            "falls flach: Ansicht 'Ordner' vs 'Alle Titel' prüfen",
            "resetReason/uptime notieren; UART wenn möglich",
        ],
    }
    (out / "GATE.json").write_text(json.dumps(gate, indent=2) + "\n")
    md = [
        "# M24 Volume-ID only (NBT Ordner-Cache)",
        "",
        f"- before vol `{before.get('bpbVolumeId')}` serial `{before.get('usbSerial')}`",
        f"- after  vol `{after.get('bpbVolumeId')}` serial `{after.get('usbSerial')}`",
        f"- volume_id_changed: **{gate['volume_id_changed']}**",
        f"- serial_unchanged: **{gate['serial_unchanged']}**",
        "",
        "## Operator",
        "",
    ]
    md += [f"- [ ] {x}" for x in gate["operator"]]
    md += ["", "PASS wenn Ordner sichtbar; FAIL wenn weiter flach trotz vol-change.", ""]
    (out / "ERGEBNIS.md").write_text("\n".join(md))
    return 0 if gate["volume_id_changed"] and gate["serial_unchanged"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

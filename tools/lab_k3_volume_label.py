#!/usr/bin/env python3
"""FAT-/USB-Identity isolieren und am realen Blockdevice verifizieren.

Das frühere Werkzeug prüfte nur den Root-Directory-Label-Override. Das ist
keine vollständige FAT-Volume-Identity. Diese Version erfasst zusätzlich:
USB-Serial/Product-Revision, BPB Volume-ID, BPB-Label und Root-Label.

Beispiel (Linux/Proxmox; Device bewusst explizit angeben):
  python3 tools/lab_k3_volume_label.py --esp http://192.168.4.1 \
      --label PIDRIVE2 --volume-id 0x5044A002 --device /dev/sdb \
      --artifact-dir artifacts/k3-label

Leere Labels und Volume-ID 0 schalten die Overrides aus; dann folgen beide
FAT-Labels und die BPB Volume-ID wieder remountGen.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import time
import urllib.request


def http_json(url: str, method: str = "GET", body: dict | None = None, timeout: float = 12) -> dict:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.load(response)


def read_sector(fd: int, lba: int) -> bytes:
    data = os.pread(fd, 512, lba * 512)
    if len(data) != 512:
        raise OSError(f"short read at LBA {lba}: {len(data)} bytes")
    return data


def fat_text(raw: bytes) -> str:
    return raw.decode("ascii", errors="replace").rstrip(" \x00")


def parse_boot(sector: bytes) -> dict:
    if sector[510:512] != b"\x55\xaa":
        raise ValueError("boot sector has no 0x55AA signature")
    bps = int.from_bytes(sector[11:13], "little")
    reserved = int.from_bytes(sector[14:16], "little")
    fats = sector[16]
    root_entries = int.from_bytes(sector[17:19], "little")
    spf = int.from_bytes(sector[22:24], "little")
    if bps != 512 or reserved == 0 or fats == 0 or spf == 0:
        raise ValueError(
            f"unsupported/invalid FAT BPB: bps={bps} reserved={reserved} fats={fats} spf={spf}"
        )
    volume_id = int.from_bytes(sector[39:43], "little")
    return {
        "bytesPerSector": bps,
        "reservedSectors": reserved,
        "fatCount": fats,
        "rootEntries": root_entries,
        "sectorsPerFat": spf,
        "rootLba": reserved + fats * spf,
        "volumeId": volume_id,
        "volumeIdHex": f"0x{volume_id:08X}",
        "bpbLabel": fat_text(sector[43:54]),
        "fsType": fat_text(sector[54:62]),
    }


def parse_root_label(sectors: bytes) -> str | None:
    for off in range(0, len(sectors), 32):
        entry = sectors[off : off + 32]
        if len(entry) < 32 or entry[0] == 0x00:
            break
        if entry[0] != 0xE5 and entry[11] == 0x08:
            return fat_text(entry[:11])
    return None


def inspect_device(device: str) -> tuple[dict, bytes, bytes]:
    fd = os.open(device, os.O_RDONLY)
    try:
        boot = read_sector(fd, 0)
        parsed = parse_boot(boot)
        root_bytes = ((parsed["rootEntries"] * 32 + 511) // 512) * 512
        root = os.pread(fd, root_bytes, parsed["rootLba"] * 512)
        if len(root) != root_bytes:
            raise OSError(f"short root read: {len(root)}/{root_bytes} bytes")
        parsed["rootLabel"] = parse_root_label(root)
        return parsed, boot, root
    finally:
        os.close(fd)


def main() -> int:
    parser = argparse.ArgumentParser(description="USB- und vollständige FAT-Identity isolieren")
    parser.add_argument("--esp", default="http://192.168.4.1")
    parser.add_argument("--label", default="PIDRIVE2", help="BPB+Root label ≤11; '' = auto")
    parser.add_argument(
        "--volume-id",
        type=lambda value: int(value, 0),
        default=0,
        help="BPB Volume-ID (z. B. 0x5044A002); 0 = auto aus remountGen",
    )
    parser.add_argument("--bump", action="store_true", help="auch Serial bumpen")
    parser.add_argument("--device", help="MSC-Blockdevice, z. B. /dev/sdb (nicht Partition)")
    parser.add_argument("--settle", type=float, default=1.5, help="Sekunden vor Blockdevice-Read")
    parser.add_argument("--artifact-dir", type=Path, help="Status, Sektoren und Bericht ablegen")
    parser.add_argument("--dry", action="store_true")
    args = parser.parse_args()

    esp = args.esp.rstrip("/")
    label = (args.label or "")[:11]
    volume_id = args.volume_id & 0xFFFFFFFF
    cfg_body = {"volumeLabel": label, "fatVolumeId": volume_id}
    remount_body = {
        "keepIdentity": not args.bump,
        "volumeLabel": label,
        "fatVolumeId": volume_id,
    }

    before = http_json(f"{esp}/api/status")
    msc0 = before.get("msc") or {}
    print(
        f"before serial={msc0.get('usbSerial')} rev={msc0.get('productRevision')} "
        f"id={msc0.get('bpbVolumeId')} bpb={msc0.get('bpbLabel')} "
        f"root={msc0.get('rootLabel')} gen={msc0.get('remountGen')}"
    )

    if args.dry:
        print("dry config", cfg_body, "remount", remount_body)
        return 0

    http_json(f"{esp}/api/config", "POST", cfg_body)
    http_json(f"{esp}/api/lab/remount", "POST", remount_body)
    if args.settle > 0:
        time.sleep(args.settle)

    after = http_json(f"{esp}/api/status")
    msc1 = after.get("msc") or {}
    print(
        f"after  serial={msc1.get('usbSerial')} rev={msc1.get('productRevision')} "
        f"id={msc1.get('bpbVolumeId')} bpb={msc1.get('bpbLabel')} "
        f"root={msc1.get('rootLabel')} gen={msc1.get('remountGen')}"
    )
    same_serial = msc0.get("usbSerial") == msc1.get("usbSerial")
    status_labels_equal = msc1.get("bpbLabel") == msc1.get("rootLabel")
    checks = {
        "serialExpectation": (not same_serial) if args.bump else same_serial,
        "statusLabelsEqual": status_labels_equal and (not label or msc1.get("bpbLabel") == label),
        "statusVolumeId": volume_id == 0 or msc1.get("bpbVolumeId") == volume_id,
    }

    media = None
    boot = root = None
    if args.device:
        media, boot, root = inspect_device(args.device)
        checks.update(
            {
                "deviceVsStatusVolumeId": media["volumeId"] == msc1.get("bpbVolumeId"),
                "deviceVsStatusBpbLabel": media["bpbLabel"] == msc1.get("bpbLabel"),
                "deviceVsStatusRootLabel": media["rootLabel"] == msc1.get("rootLabel"),
                "deviceLabelsEqual": media["bpbLabel"] == media["rootLabel"],
            }
        )
        print(
            f"device id={media['volumeIdHex']} bpb={media['bpbLabel']!r} "
            f"root={media['rootLabel']!r} rootLba={media['rootLba']}"
        )
    else:
        print("WARN: --device fehlt; BPB/Root nicht unabhängig vom ESP-Status geprüft")
    checks["completeBlockVerification"] = bool(args.device)

    report = {
        "schema": 1,
        "capturedUtc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "request": remount_body,
        "device": args.device,
        "before": before,
        "after": after,
        "media": media,
        "checks": checks,
        "completeBlockVerification": bool(args.device),
        "ok": all(checks.values()),
    }
    if args.artifact_dir:
        args.artifact_dir.mkdir(parents=True, exist_ok=True)
        (args.artifact_dir / "identity-report.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        if boot is not None and root is not None:
            (args.artifact_dir / "boot-sector.bin").write_bytes(boot)
            (args.artifact_dir / "root-directory.bin").write_bytes(root)
        print(f"artifacts={args.artifact_dir}")

    for name, ok in checks.items():
        print(f"{name}={ok}")
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())

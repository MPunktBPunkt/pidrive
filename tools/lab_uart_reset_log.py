#!/usr/bin/env python3
"""Reset-safe UART logger correlated with ESP status.

The serial port is configured with DTR=False and RTS=False before it is opened;
on POSIX, HUPCL and CRTSCTS are cleared immediately after open. The report
detects an uptime rollback and classifies common ESP boot messages.

Requires pyserial on the Debian lab host:
  python3 -m pip install -r tools/requirements-lab.txt

Example:
  python3 tools/lab_uart_reset_log.py --port /dev/ttyACM0 \
    --esp http://192.168.178.88 --seconds 120 --out artifacts/uart-q11
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import time
import urllib.request
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def http_status(esp: str, timeout: float = 4.0) -> dict:
    with urllib.request.urlopen(f"{esp.rstrip('/')}/api/status", timeout=timeout) as response:
        return json.load(response)


def slim_status(status: dict, mono_s: float) -> dict:
    return {
        "wall": utc_now(),
        "mono_s": round(mono_s, 6),
        "uptimeMs": status.get("uptimeMs"),
        "resetReason": status.get("resetReason"),
        "resetReasonCode": status.get("resetReasonCode"),
        "version": status.get("version"),
        "otgUp": status.get("otgUp"),
        "uartUp": status.get("uartUp"),
        "usbSerial": (status.get("msc") or {}).get("usbSerial"),
    }


def classify_boot_text(text: str) -> list[str]:
    patterns = {
        "rom_reset": r"\brst:0x[0-9a-f]+",
        "brownout": r"brownout",
        "watchdog": r"\b(?:task|interrupt)?\s*w(?:atchdog|dt)\b",
        "panic": r"(?:guru meditation|panic'ed|backtrace:)",
        "firmware_boot": r"===\s*esp32\.pidrive",
    }
    lowered = text.lower()
    return [name for name, pattern in patterns.items() if re.search(pattern, lowered, re.I)]


def uptime_rollback(rows: list[dict]) -> bool:
    previous: int | None = None
    for row in rows:
        value = row.get("uptimeMs")
        if value is None:
            continue
        current = int(value)
        if previous is not None and current < previous:
            return True
        previous = current
    return False


def configure_posix_no_reset(serial_port: Any) -> dict:
    """Clear hangup/hardware-flow flags without touching modem lines."""
    if os.name != "posix":
        return {"applied": False, "reason": f"os={os.name}"}
    import termios

    attrs = termios.tcgetattr(serial_port.fileno())
    attrs[2] &= ~termios.HUPCL
    if hasattr(termios, "CRTSCTS"):
        attrs[2] &= ~termios.CRTSCTS
    termios.tcsetattr(serial_port.fileno(), termios.TCSANOW, attrs)
    return {"applied": True, "hupcl": False, "crtscts": False}


def self_test() -> int:
    assert classify_boot_text("rst:0x1 (POWERON_RESET)") == ["rom_reset"]
    assert "brownout" in classify_boot_text("Brownout detector was triggered")
    assert "watchdog" in classify_boot_text("Task watchdog got triggered")
    assert uptime_rollback([{"uptimeMs": 1000}, {"uptimeMs": 1200}, {"uptimeMs": 50}])
    assert not uptime_rollback([{"uptimeMs": 1000}, {"uptimeMs": 1200}])
    print("self-test PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--port", default="/dev/ttyACM0")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--esp", default="http://192.168.178.88")
    parser.add_argument("--seconds", type=float, default=120.0)
    parser.add_argument("--status-interval", type=float, default=0.5)
    parser.add_argument("--out", type=Path, default=Path("artifacts/lab-uart-reset"))
    args = parser.parse_args()
    if args.self_test:
        return self_test()

    try:
        import serial
    except ImportError:
        parser.error("pyserial fehlt; installiere tools/requirements-lab.txt auf dem Debian-Labhost")

    args.out.mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()
    status_rows: list[dict] = []
    uart_text: list[str] = []
    serial_cfg: dict[str, Any] = {
        "port": args.port,
        "baud": args.baud,
        "dtr": False,
        "rts": False,
    }

    port = serial.Serial(port=None, baudrate=args.baud, timeout=0.05, write_timeout=1)
    # Set desired modem-line state before assigning/opening the port.
    port.dtr = False
    port.rts = False
    port.port = args.port
    port.open()
    serial_cfg["posix"] = configure_posix_no_reset(port)
    serial_cfg["is_open"] = port.is_open

    next_status = t0
    end = t0 + max(0.0, args.seconds)
    with (args.out / "uart.jsonl").open("w", encoding="utf-8") as uart_out, (
        args.out / "status.jsonl"
    ).open("w", encoding="utf-8") as status_out:
        try:
            while time.monotonic() < end:
                now = time.monotonic()
                waiting = int(getattr(port, "in_waiting", 0) or 0)
                raw = port.read(max(1, min(waiting, 4096)))
                if raw:
                    text = raw.decode("utf-8", errors="replace")
                    uart_text.append(text)
                    row = {
                        "wall": utc_now(),
                        "mono_s": round(now - t0, 6),
                        "n": len(raw),
                        "text": text,
                    }
                    uart_out.write(json.dumps(row, ensure_ascii=False) + "\n")
                    uart_out.flush()
                if now >= next_status:
                    try:
                        row = slim_status(http_status(args.esp), now - t0)
                    except Exception as exc:
                        row = {
                            "wall": utc_now(),
                            "mono_s": round(now - t0, 6),
                            "error": f"{type(exc).__name__}: {exc}",
                        }
                    status_rows.append(row)
                    status_out.write(json.dumps(row, ensure_ascii=False) + "\n")
                    status_out.flush()
                    next_status = now + max(0.1, args.status_interval)
        finally:
            # Keep modem outputs inactive before close; HUPCL is already clear.
            port.dtr = False
            port.rts = False
            port.close()

    boot_classes = classify_boot_text("".join(uart_text))
    rollback = uptime_rollback(status_rows)
    missing_uptime = not any(row.get("uptimeMs") is not None for row in status_rows)
    report = {
        "schema": 1,
        "capturedUtc": utc_now(),
        "duration_s": round(time.monotonic() - t0, 3),
        "serial": serial_cfg,
        "status_samples": len(status_rows),
        "status_errors": sum(1 for row in status_rows if "error" in row),
        "uart_chunks": len(uart_text),
        "boot_classes": boot_classes,
        "uptime_rollback": rollback,
        "missing_uptimeMs": missing_uptime,
        "reset_observed": bool(rollback or boot_classes),
        "pass": bool(not rollback and not boot_classes and not missing_uptime),
        "note": "PASS means no reset observed while this logger held the port; it is not a power-rail proof.",
    }
    (args.out / "UART-RESET-REPORT.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"OUT {args.out}")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

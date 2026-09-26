#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
usb_pump_client.py — PiDrive ESP / PUMP Presence (U2)

Erkennt den esp32.pidrive und schreibt /tmp/pidrive_usb_status.json,
das ipc.write_status unter dem Key ``usb`` einbettet.

UART bleibt bei der Lab-Bridge (`pump_bridge.py`) als Option; ab FW 0.4.15
kann dieselbe Bridge PUMP auch über TCP (:9090 SoftAP/STA) fahren.

Dieser Prozess:
  - prüft Serial-Nodes (/dev/ttyACM*, by-id)
  - pollt SoftAP/STA ``GET /api/status`` (otg/pump/stream/fw/pumpTcp*)
  - optional ``--uart``: HELLO nur wenn Port freigegeben (nicht parallel zur Bridge)

systemd: ``pidrive_pump.service`` (optional).
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import time
import urllib.error
import urllib.request

_HERE = os.path.dirname(os.path.abspath(__file__))
_PKG = os.path.dirname(_HERE)
if _PKG not in sys.path:
    sys.path.insert(0, _PKG)

USB_STATUS_FILE = "/tmp/pidrive_usb_status.json"


def _load_settings() -> dict:
    try:
        from settings import load_settings
        return load_settings()
    except Exception:
        return {}


def _write_status(data: dict) -> None:
    """Write /tmp/pidrive_usb_status.json.

    /tmp is typically sticky (1777): os.replace fails if the existing file is
    owned by another uid. Fall back to unlink + rewrite / in-place truncate.
    """
    payload = dict(data)
    payload["ts"] = int(time.time())
    text = json.dumps(payload, ensure_ascii=False)
    path = USB_STATUS_FILE
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                pass
        try:
            os.replace(tmp, path)
        except OSError:
            try:
                os.unlink(path)
            except OSError:
                pass
            try:
                os.replace(tmp, path)
            except OSError:
                # sticky /tmp or immutable dest — overwrite in place
                with open(path, "w", encoding="utf-8") as f:
                    f.write(text)
                    f.flush()
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
        try:
            os.chmod(path, 0o666)
        except OSError:
            pass
    except Exception:
        pass


def _serial_candidates(preferred: str) -> list[str]:
    found: list[str] = []
    if preferred and os.path.exists(preferred):
        found.append(preferred)
    for path in sorted(glob.glob("/dev/ttyACM*")) + sorted(
        glob.glob("/dev/serial/by-id/*")
    ):
        if path not in found:
            found.append(path)
    return found


def _http_esp_status(host: str, port: int, timeout: float = 2.5) -> dict | None:
    if not host:
        return None
    url = f"http://{host}:{int(port)}/api/status"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", errors="replace"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError, ValueError):
        return None


def _uart_hello(port: str, baud: int = 115200, timeout_s: float = 2.0) -> dict | None:
    """Optional HELLO when bridge is not holding the port."""
    try:
        import serial  # type: ignore
    except ImportError:
        return {"ok": False, "err": "pyserial_missing"}
    try:
        ser = serial.Serial(port, baud, timeout=0.05)
    except Exception as e:
        return {"ok": False, "err": str(e)[:120]}
    try:
        line = (json.dumps({"t": "hello", "ver": 1}) + "\n").encode()
        ser.reset_input_buffer()
        ser.write(line)
        ser.flush()
        deadline = time.time() + timeout_s
        buf = b""
        while time.time() < deadline:
            chunk = ser.read(256)
            if chunk:
                buf += chunk
                while b"\n" in buf:
                    raw, buf = buf.split(b"\n", 1)
                    raw = raw.strip()
                    if not raw or raw[:1] == b"\x01":
                        continue
                    try:
                        msg = json.loads(raw.decode("utf-8", errors="replace"))
                    except json.JSONDecodeError:
                        continue
                    if msg.get("t") == "hello_ack":
                        return {
                            "ok": True,
                            "fw": msg.get("ver") or msg.get("fw"),
                            "slots": msg.get("slots"),
                            "page": bool(msg.get("page")),
                            "audio": bool(msg.get("audio")),
                            "bin": bool(msg.get("bin")),
                        }
            else:
                time.sleep(0.02)
        return {"ok": False, "err": "hello_timeout"}
    finally:
        try:
            ser.close()
        except Exception:
            pass


def build_snapshot(
    settings: dict | None = None,
    *,
    try_uart: bool = False,
) -> dict:
    settings = settings if settings is not None else _load_settings()
    host = str(settings.get("usb_esp_host") or "").strip()
    port = int(settings.get("usb_esp_port") or 80)
    preferred = str(settings.get("usb_pump_port") or "/dev/ttyACM0")
    baud = int(settings.get("usb_pump_baud") or 115200)

    serials = _serial_candidates(preferred)
    http = _http_esp_status(host, port) if host else None

    stream = {}
    if isinstance(http, dict):
        stream = (http.get("msc") or {}).get("stream") or http.get("stream") or {}

    online = bool(http) or bool(serials)
    uart_hello = None
    if try_uart and serials:
        uart_hello = _uart_hello(serials[0], baud=baud)
        if uart_hello and uart_hello.get("ok"):
            online = True

    fw = None
    if http:
        fw = http.get("version") or http.get("fw")
    if uart_hello and uart_hello.get("ok") and uart_hello.get("fw"):
        fw = uart_hello.get("fw")

    return {
        "online": online,
        "http_ok": bool(http),
        "serial_present": bool(serials),
        "serial_ports": serials[:6],
        "port": preferred,
        "esp_host": host,
        "fw": fw or "",
        "pump_up": bool(http.get("pumpUp")) if http else False,
        "pump_tcp": bool(http.get("pumpTcp")) if http else False,
        "pump_tcp_port": int(http.get("pumpTcpPort") or 0) if http else 0,
        "pump_tcp_up": bool(http.get("pumpTcpUp")) if http else False,
        "otg_up": bool(http.get("otgUp")) if http else False,
        "otg_suspended": bool(http.get("otgSuspended")) if http else False,
        "uart_up": bool(http.get("uartUp")) if http else False,
        "msc_ready": bool(http.get("mscReady")) if http else False,
        "playing_name": (http.get("playingName") or "") if http else "",
        "playing_uid": (http.get("playingUid") or "") if http else "",
        "id3_len": int(stream.get("id3Len") or 0),
        "stream_active": bool(stream.get("active")),
        "stream_bytes": int(stream.get("size") or 0),
        "stream_cap": int(stream.get("cap") or 0),
        "buffer_ms": int(http.get("bufferMs") or 0) if http else 0,
        "lab_mode": bool(http.get("labMode")) if http else False,
        "uart_hello": uart_hello,
        "source": "http+serial" if http and serials else ("http" if http else ("serial" if serials else "none")),
    }


def poll_once(try_uart: bool = False) -> dict:
    snap = build_snapshot(try_uart=try_uart)
    _write_status(snap)
    return snap


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="PiDrive USB/ESP PUMP presence client")
    ap.add_argument("--once", action="store_true", help="ein Snapshot, dann Exit")
    ap.add_argument("--uart", action="store_true", help="UART HELLO versuchen (nicht mit Bridge parallel)")
    ap.add_argument("--interval", type=float, default=None, help="Poll-Intervall Sekunden")
    args = ap.parse_args(argv)

    settings = _load_settings()
    interval = args.interval
    if interval is None:
        try:
            interval = float(settings.get("usb_poll_s") or 2.0)
        except (TypeError, ValueError):
            interval = 2.0
    interval = max(0.5, float(interval))

    if args.once:
        snap = poll_once(try_uart=args.uart)
        print(json.dumps(snap, ensure_ascii=False, indent=2))
        return 0 if snap.get("online") else 1

    print(
        f"[usb_pump] host={settings.get('usb_esp_host')!r} "
        f"port={settings.get('usb_pump_port')!r} interval={interval}s",
        flush=True,
    )
    while True:
        snap = poll_once(try_uart=args.uart)
        tag = "UP" if snap.get("online") else "down"
        print(
            f"[usb_pump] {tag} http={snap.get('http_ok')} serial={snap.get('serial_present')} "
            f"otg={snap.get('otg_up')} pump={snap.get('pump_up')} fw={snap.get('fw') or '-'}",
            flush=True,
        )
        time.sleep(interval)


if __name__ == "__main__":
    raise SystemExit(main())

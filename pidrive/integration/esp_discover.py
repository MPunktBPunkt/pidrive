#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""esp_discover.py — ESP32.pidrive im LAN finden (HTTP /api/status).

Strategien (schnell → breit):
  1. SoftAP 192.168.4.1 + gespeicherter ``usb_esp_host``
  2. mDNS via ``avahi-browse`` (falls installiert) — Hostnamen ``pidrive-*``
  3. Parallel-Scan der lokalen /24-Subnetze (IPv4)

Kein Extra-Dependency (kein zeroconf-Paket).
"""

from __future__ import annotations

import concurrent.futures
import ipaddress
import json
import os
import re
import socket
import subprocess
import urllib.error
import urllib.request
from typing import Any


SOFTAP_IP = "192.168.4.1"
_STATUS_PATH = "/api/status"
_HOSTNAME_RE = re.compile(r"^pidrive-[0-9a-fA-F]{4,}$", re.I)


def _load_settings() -> dict:
    try:
        from settings import load_settings
        return load_settings()
    except Exception:
        return {}


def is_pidrive_status(data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    ft = str(data.get("fwType") or "").lower()
    if ft == "pidrive":
        return True
    # Robust gegen ältere FW ohne fwType
    if data.get("pumpTcp") is not None and (
        data.get("mscReady") is not None or data.get("otgUp") is not None
    ):
        return True
    name = str(data.get("name") or "")
    if "pidrive" in name.lower() and data.get("version"):
        return True
    return False


def probe_host(
    host: str,
    port: int = 80,
    timeout: float = 0.45,
) -> dict | None:
    """GET /api/status — bei Treffer Snapshot, sonst None."""
    host = (host or "").strip()
    if not host:
        return None
    url = f"http://{host}:{int(port)}{_STATUS_PATH}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            raw = r.read().decode("utf-8", errors="replace")
        data = json.loads(raw)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError, ValueError):
        return None
    if not is_pidrive_status(data):
        return None
    return {
        "host": host,
        "port": int(port),
        "ip": str(data.get("ip") or host),
        "softApIp": str(data.get("softApIp") or ""),
        "softApSsid": str(data.get("softApSsid") or ""),
        "name": str(data.get("name") or ""),
        "fw": str(data.get("version") or data.get("fw") or ""),
        "fwType": str(data.get("fwType") or ""),
        "mac": str(data.get("mac") or ""),
        "pumpTcp": bool(data.get("pumpTcp")),
        "pumpTcpPort": int(data.get("pumpTcpPort") or 0),
        "pumpUp": bool(data.get("pumpUp")),
        "otgUp": bool(data.get("otgUp")),
        "mscReady": bool(data.get("mscReady")),
        "source": "http",
    }


def local_v4_subnets() -> list[ipaddress.IPv4Network]:
    """Aktive IPv4-/24-Netze (größere Prefixe auf /24 begrenzen)."""
    nets: list[ipaddress.IPv4Network] = []
    seen: set[str] = set()
    try:
        out = subprocess.check_output(
            ["ip", "-4", "-o", "addr", "show", "scope", "global"],
            text=True,
            timeout=3,
        )
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        out = ""
    for line in out.splitlines():
        # 2: eth0    inet 192.168.178.187/24 ...
        parts = line.split()
        if "inet" not in parts:
            continue
        try:
            idx = parts.index("inet")
            cidr = parts[idx + 1]
            iface_net = ipaddress.ip_interface(cidr)
            if not isinstance(iface_net.ip, ipaddress.IPv4Address):
                continue
            net = iface_net.network
            if net.prefixlen < 24:
                # nicht das ganze /16 scannen
                net = ipaddress.IPv4Network(f"{iface_net.ip}/24", strict=False)
            elif net.prefixlen > 24:
                net = ipaddress.IPv4Network(f"{iface_net.ip}/24", strict=False)
            key = str(net)
            if key not in seen:
                seen.add(key)
                nets.append(net)
        except (ValueError, IndexError):
            continue
    return nets


def _avahi_pidrive_hosts(timeout: float = 2.5) -> list[str]:
    """Hostnamen/IPs aus avahi-browse, falls vorhanden."""
    found: list[str] = []
    try:
        proc = subprocess.run(
            ["avahi-browse", "-atrk", "-t", "_http._tcp"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (FileNotFoundError, subprocess.SubprocessError, OSError):
        return []
    # hostname = [pidrive-A1B2C3.local]
    for m in re.finditer(r"hostname\s*=\s*\[([^\]]+)\]", proc.stdout or "", re.I):
        hn = m.group(1).strip().rstrip(".")
        short = hn.split(".")[0]
        if _HOSTNAME_RE.match(short) or short.lower().startswith("pidrive-"):
            found.append(hn if "." in hn else f"{hn}.local")
    # address = [192.168.x.y]
    # paired loosely: also collect any address near pidrive lines
    for line in (proc.stdout or "").splitlines():
        if "pidrive-" not in line.lower():
            continue
        am = re.search(r"address\s*=\s*\[([0-9.]+)\]", line, re.I)
        if am:
            found.append(am.group(1))
    # second pass: full blocks
    block_hosts: list[str] = []
    cur_host = ""
    for line in (proc.stdout or "").splitlines():
        hm = re.search(r"hostname\s*=\s*\[([^\]]+)\]", line, re.I)
        if hm:
            cur_host = hm.group(1).strip()
        am = re.search(r"address\s*=\s*\[([0-9.]+)\]", line, re.I)
        if am and cur_host:
            short = cur_host.split(".")[0]
            if short.lower().startswith("pidrive-"):
                block_hosts.append(am.group(1))
                block_hosts.append(cur_host if "." in cur_host else f"{cur_host}.local")
    found.extend(block_hosts)
    # unique preserve order
    out: list[str] = []
    seen: set[str] = set()
    for h in found:
        if h not in seen:
            seen.add(h)
            out.append(h)
    return out


def seed_hosts(settings: dict | None = None) -> list[str]:
    settings = settings if settings is not None else _load_settings()
    hosts: list[str] = [SOFTAP_IP]
    saved = str(settings.get("usb_esp_host") or "").strip()
    if saved and saved not in hosts:
        hosts.append(saved)
    for h in _avahi_pidrive_hosts():
        if h not in hosts:
            hosts.append(h)
    return hosts


def discover(
    *,
    timeout_s: float = 5.0,
    port: int = 80,
    scan_subnet: bool = True,
    max_workers: int = 64,
    settings: dict | None = None,
) -> dict:
    """Scan und Trefferliste.

    Returns:
        ``{"ok": True, "hosts": [...], "scanned": N, "ms": …, "subnets": [...]}``
    """
    import time

    t0 = time.time()
    settings = settings if settings is not None else _load_settings()
    port = int(port or settings.get("usb_esp_port") or 80)

    candidates: list[str] = list(seed_hosts(settings))
    subnets_s: list[str] = []

    if scan_subnet:
        for net in local_v4_subnets():
            subnets_s.append(str(net))
            # skip huge
            if net.num_addresses > 256:
                continue
            for ip in net.hosts():
                s = str(ip)
                if s not in candidates:
                    candidates.append(s)

    hits: list[dict] = []
    seen_ip: set[str] = set()
    per_timeout = min(0.5, max(0.25, timeout_s / 8.0))

    def _one(h: str) -> dict | None:
        return probe_host(h, port=port, timeout=per_timeout)

    workers = min(max_workers, max(8, len(candidates) // 4 or 8))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(_one, h): h for h in candidates}
        try:
            for fut in concurrent.futures.as_completed(futs, timeout=timeout_s + 1.0):
                hit = fut.result()
                if not hit:
                    continue
                key = hit.get("ip") or hit.get("host") or ""
                if key in seen_ip:
                    continue
                seen_ip.add(key)
                # Prefer numeric host for settings when hostname was used
                if not re.match(r"^\d+\.\d+\.\d+\.\d+$", str(hit.get("host") or "")):
                    if hit.get("ip") and re.match(r"^\d+\.\d+\.\d+\.\d+$", hit["ip"]):
                        hit["host"] = hit["ip"]
                hits.append(hit)
        except concurrent.futures.TimeoutError:
            pass

    hits.sort(key=lambda h: (0 if h.get("host") == SOFTAP_IP else 1, h.get("host") or ""))
    ms = int((time.time() - t0) * 1000)
    return {
        "ok": True,
        "hosts": hits,
        "count": len(hits),
        "scanned": len(candidates),
        "subnets": subnets_s,
        "port": port,
        "ms": ms,
        "saved_host": str(settings.get("usb_esp_host") or ""),
    }


def apply_host(
    host: str,
    *,
    http_port: int | None = None,
    tcp_port: int | None = None,
) -> dict:
    """``usb_esp_host`` (und Ports) in settings.json speichern."""
    host = (host or "").strip()
    if not host:
        return {"ok": False, "error": "host fehlt"}
    from settings import load_settings, save_settings

    s = load_settings()
    s["usb_esp_host"] = host
    if http_port is not None:
        s["usb_esp_port"] = int(http_port)
    if tcp_port is not None and int(tcp_port) > 0:
        s["usb_pump_tcp_port"] = int(tcp_port)
    # Prefer TCP when we just found WLAN ESP
    if not s.get("usb_pump_transport") or s.get("usb_pump_transport") == "auto":
        s["usb_pump_transport"] = "auto"
    save_settings(s)
    return {
        "ok": True,
        "usb_esp_host": s["usb_esp_host"],
        "usb_esp_port": s.get("usb_esp_port", 80),
        "usb_pump_tcp_port": s.get("usb_pump_tcp_port", 9090),
        "usb_pump_transport": s.get("usb_pump_transport", "auto"),
        "hint": "pump_bridge neu starten: systemctl restart pidrive_pump_bridge",
    }


if __name__ == "__main__":
    import pprint

    pprint.pp(discover(timeout_s=4.0))

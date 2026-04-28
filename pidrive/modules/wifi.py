"""
modules/wifi.py — WiFi-Verbindung via nmcli
Aufrufer: main_core.py
Abhängig von: ipc.py
"""


import subprocess
import time
import ipc
import log


def _run(cmd):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=12)
        return r.stdout.strip()
    except Exception:
        return ""


def _bg(cmd):
    try:
        subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def _has_nmcli():
    try:
        r = subprocess.run("which nmcli", shell=True, capture_output=True, text=True, timeout=3)
        return r.returncode == 0 and bool(r.stdout.strip())
    except Exception:
        return False


def wifi_toggle(S):
    if S.get("wifi"):
        log.info("WiFi toggle: OFF")
        _bg("rfkill block wifi")
        S["wifi"] = False
        S["wifi_ssid"] = ""
    else:
        log.info("WiFi toggle: ON")
        _bg("rfkill unblock wifi; ip link set wlan0 up")
    S["ts"] = 0
    S["menu_rev"] = S.get("menu_rev", 0) + 1


def scan_networks(S, settings):
    """WLAN scannen, Ergebnis in JSON speichern."""
    ipc.write_progress("WiFi", "Scanne Netzwerke...", color="blue")
    networks = []
    try:
        r = subprocess.run(
            ["sudo", "iwlist", "wlan0", "scan"],
            capture_output=True, text=True, timeout=20
        )
        seen = set()
        for line in r.stdout.splitlines():
            if "ESSID:" in line:
                p = line.strip().split('"')
                if len(p) > 1:
                    ssid = p[1].strip()
                    if ssid and ssid not in seen:
                        seen.add(ssid)
                        networks.append({"ssid": ssid})
        log.info(f"WiFi scan: {len(networks)} Netzwerke")
    except Exception as e:
        log.error("WiFi scan: " + str(e))
        ipc.write_progress("WiFi Scan", "Fehler", color="red")
        time.sleep(2)
        ipc.clear_progress()
        return

    ipc.write_json("/tmp/pidrive_wifi_nets.json", {"networks": networks})
    ipc.clear_progress()
    msg = str(len(networks)) + " Netz(e) — Verbindungen > Netzwerke"
    ipc.write_progress("WiFi Scan", msg, color="green" if networks else "orange")
    time.sleep(2)
    ipc.clear_progress()
    S["menu_rev"] = S.get("menu_rev", 0) + 1


def connect_network(ssid, S, settings):
    """WLAN-Netzwerk verbinden."""
    ipc.write_progress("WiFi", "Verbinde " + ssid[:20] + "...", color="blue")
    log.info("WiFi: verbinde " + ssid)
    try:
        ok = False
        if _has_nmcli():
            r = subprocess.run(
                ["sudo", "nmcli", "d", "wifi", "connect", ssid],
                capture_output=True, text=True, timeout=40
            )
            ok = (r.returncode == 0
                  or "successfully" in (r.stdout or "").lower()
                  or "successfully" in (r.stderr or "").lower())
        else:
            log.warn("WiFi: nmcli nicht gefunden — nur Status-Aktualisierung möglich")
        if ok:
            ipc.write_progress("WiFi", "Verbunden: " + ssid[:22], color="green")
            log.info("WiFi: verbunden mit " + ssid)
            S["wifi"] = True
            S["wifi_ssid"] = ssid
        else:
            ipc.write_progress("WiFi", "Verbindung fehlgeschlagen", color="red")
            log.warn("WiFi: Verbindung fehlgeschlagen: " + ssid)
    except Exception as e:
        log.error("WiFi connect: " + str(e))
        ipc.write_progress("WiFi", "Fehler: " + str(e)[:20], color="red")
    time.sleep(2)
    ipc.clear_progress()
    S["menu_rev"] = S.get("menu_rev", 0) + 1

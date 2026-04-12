"""
modules/wifi.py - WiFi Modul
PiDrive v0.6.1 - pygame-frei
"""
import subprocess, time, ipc

def _run(cmd):
    try: return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=8).stdout.strip()
    except: return ""

def _bg(cmd):
    try: subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except: pass

def wifi_toggle(S):
    _bg("rfkill block wifi" if S["wifi"] else "rfkill unblock wifi; ip link set wlan0 up; dhcpcd wlan0")
    S["ts"] = 0

# build_items entfernt

def scan_networks(S, settings):
    """WLAN scannen, Ergebnis in JSON speichern (-> Submenu)."""
    import ipc, time, subprocess, json
    ipc.write_progress("WiFi", "Scanne Netzwerke...", color="blue")
    networks = []
    try:
        r = subprocess.run(["sudo","iwlist","wlan0","scan"],
                           capture_output=True, text=True, timeout=15)
        seen = set()
        for line in r.stdout.splitlines():
            if "ESSID:" in line:
                p = line.strip().split('"')
                if len(p) > 1 and p[1] and p[1] not in seen:
                    seen.add(p[1])
                    networks.append({"ssid": p[1]})
    except Exception as e:
        log.error("WiFi scan: " + str(e))
        ipc.write_progress("WiFi Scan", "Fehler", color="red")
        time.sleep(2); ipc.clear_progress(); return

    ipc.write_json("/tmp/pidrive_wifi_nets.json", {"networks": networks})
    ipc.clear_progress()
    msg = str(len(networks)) + " Netz(e) — Verbindungen > Netzwerke"
    ipc.write_progress("WiFi Scan", msg, color="green" if networks else "orange")
    time.sleep(2); ipc.clear_progress()
    S["menu_rev"] = S.get("menu_rev", 0) + 1


def connect_network(ssid, S, settings):
    """WLAN-Netzwerk verbinden."""
    import ipc, time, subprocess
    ipc.write_progress("WiFi", "Verbinde " + ssid[:20] + "...", color="blue")
    log.info("WiFi: verbinde " + ssid)
    try:
        r = subprocess.run(
            ["sudo","nmcli","d","wifi","connect", ssid],
            capture_output=True, text=True, timeout=30)
        ok = "successfully" in r.stdout.lower() or r.returncode == 0
        if ok:
            ipc.write_progress("WiFi", "Verbunden: " + ssid[:22], color="green")
            log.info("WiFi: verbunden mit " + ssid)
            S["wifi"] = True
        else:
            ipc.write_progress("WiFi", "Verbindung fehlgeschlagen", color="red")
            log.warn("WiFi: Verbindung fehlgeschlagen: " + ssid)
    except Exception as e:
        log.error("WiFi connect: " + str(e))
        ipc.write_progress("WiFi", "Fehler: " + str(e)[:20], color="red")
    time.sleep(2); ipc.clear_progress()



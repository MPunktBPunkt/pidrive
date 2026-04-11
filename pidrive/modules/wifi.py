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
    """WLAN Netzwerke scannen und via headless_pick auswählen."""
    import ipc, time
    from modules import wifi as _self
    ipc.write_progress("WiFi", "Scanne Netzwerke ...", color="blue")
    try:
        import subprocess
        r = subprocess.run(["sudo","iwlist","wlan0","scan"],
                           capture_output=True, text=True, timeout=10)
        ssids = []
        for line in r.stdout.splitlines():
            if "ESSID:" in line:
                s = line.strip().split('"')
                if len(s) > 1 and s[1]: ssids.append(s[1])
        ssids = list(dict.fromkeys(ssids))  # Deduplizieren
    except Exception as e:
        ipc.write_progress("WiFi Scan", f"Fehler: {e}", color="red")
        time.sleep(2); ipc.clear_progress(); return

    if not ssids:
        ipc.write_progress("WiFi Scan", "Keine Netzwerke gefunden", color="orange")
        time.sleep(2); ipc.clear_progress(); return

    chosen = ipc.headless_pick("WiFi Netzwerk", ssids)
    ipc.clear_progress()

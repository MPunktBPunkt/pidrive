"""
modules/system.py - System Modul
PiDrive v0.6.1 - pygame-frei
"""
import subprocess, time, os, ipc
from ui import Item

def _bg(cmd):
    try: subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except: pass

def _run(cmd):
    try: return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5).stdout.strip()
    except: return ""

def get_cpu_temp():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            return f"{int(f.read().strip()) / 1000:.1f}°C"
    except: return "-"

def get_uptime():
    out = _run("uptime -p 2>/dev/null")
    return out.replace("up ", "")[:20] if out else "-"

def build_items(screen, S, settings):
    def show_sysinfo():
        temp = get_cpu_temp(); uptime = get_uptime()
        disk = _run("df -h / 2>/dev/null | tail -1 | awk '{print $3\"/\"$2\" (\"$5\")\"}'")[:20]
        ipc.write_progress(f"CPU: {temp}", f"Up: {uptime} | {disk}", color="orange")
        time.sleep(4); ipc.clear_progress()

    def confirm_reboot():
        if ipc.headless_confirm("Neustart?", "System neu starten"):
            _bg("reboot")

    def confirm_shutdown():
        if ipc.headless_confirm("Ausschalten?", "System herunterfahren"):
            _bg("poweroff")

    def show_version():
        version = "?"
        try:
            with open(os.path.join(os.path.dirname(__file__), "../VERSION")) as f:
                version = f.read().strip()
        except: pass
        ipc.write_progress("PiDrive", f"Version: {version}", color="orange")
        time.sleep(3); ipc.clear_progress()

    return [
        Item("IP Adresse",    sub=lambda: S.get("ip",   "-")),
        Item("Hostname",      sub=lambda: S.get("host", "-")),
        Item("System-Info",   sub=lambda: get_cpu_temp(), action=show_sysinfo),
        Item("Version",       action=show_version),
        Item("Neustart",      action=confirm_reboot),
        Item("Ausschalten",   action=confirm_shutdown),
    ]

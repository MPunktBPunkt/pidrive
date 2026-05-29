"""
modules/system.py - System Modul
PiDrive v0.6.1 - pygame-frei
"""
import subprocess, time, os, ipc

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

# build_items entfernt

def show_info(S, settings):
    """System-Info via Progress-Overlay anzeigen."""
    import subprocess, time, ipc
    try:
        temp_r = subprocess.run(["cat","/sys/class/thermal/thermal_zone0/temp"],
                                capture_output=True, text=True)
        temp = int(temp_r.stdout.strip()) / 1000
        uptime_r = subprocess.run(["uptime","-p"], capture_output=True, text=True)
        uptime = uptime_r.stdout.strip()
        ipc.write_progress("System-Info",
                           f"Temp: {temp:.1f}°C  {uptime}", color="blue")
    except Exception as e:
        ipc.write_progress("System-Info", f"Fehler: {e}", color="red")
    time.sleep(4); ipc.clear_progress()

def show_version(S):
    """Version anzeigen."""
    import os, time, ipc
    try:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        v = open(os.path.join(base,"VERSION")).read().strip()
        ipc.write_progress("PiDrive", f"Version {v}", color="blue")
    except Exception:
        ipc.write_progress("PiDrive", "Version unbekannt", color="orange")
    time.sleep(3); ipc.clear_progress()

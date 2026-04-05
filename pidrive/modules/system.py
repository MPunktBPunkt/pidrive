"""
modules/system.py - System Modul
PiDrive Project - GPL-v3
"""

import subprocess
import time
import os
from ui import Item, show_message, C_ORANGE

def _bg(cmd):
    try:
        subprocess.Popen(cmd, shell=True,
                         stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    except Exception:
        pass

def _run(cmd):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True,
                           text=True, timeout=5)
        return r.stdout.strip()
    except Exception:
        return ""

def get_cpu_temp():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            return f"{int(f.read().strip()) / 1000:.1f}°C"
    except Exception:
        return "-"

def get_uptime():
    out = _run("uptime -p 2>/dev/null")
    return out.replace("up ", "")[:20] if out else "-"

def get_disk_usage():
    out = _run("df -h / 2>/dev/null | tail -1 | awk '{print $3\"/\"$2\" (\"$5\")\"}'")
    return out[:20] if out else "-"

def build_items(screen, S, settings):

    def show_sysinfo():
        temp   = get_cpu_temp()
        uptime = get_uptime()
        disk   = get_disk_usage()
        show_message(screen, f"CPU: {temp}",
                     f"Up: {uptime} | {disk}", color=C_ORANGE)
        time.sleep(4)

    def confirm_reboot():
        show_message(screen, "Neustart?", "Enter = Ja  ESC = Nein",
                     color=C_ORANGE)
        import pygame
        start = time.time()
        while time.time() - start < 10:
            for ev in pygame.event.get():
                if ev.type == pygame.KEYDOWN:
                    if ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        _bg("reboot")
                        return
                    elif ev.key == pygame.K_ESCAPE:
                        return
            pygame.time.wait(100)

    def confirm_shutdown():
        show_message(screen, "Ausschalten?", "Enter = Ja  ESC = Nein",
                     color=C_ORANGE)
        import pygame
        start = time.time()
        while time.time() - start < 10:
            for ev in pygame.event.get():
                if ev.type == pygame.KEYDOWN:
                    if ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        _bg("poweroff")
                        return
                    elif ev.key == pygame.K_ESCAPE:
                        return
            pygame.time.wait(100)

    def show_version():
        version = "unbekannt"
        try:
            vf = os.path.join(os.path.dirname(__file__), "../VERSION")
            with open(vf) as f:
                version = f.read().strip()
        except Exception:
            pass
        show_message(screen, "PiDrive", f"Version: {version}", color=C_ORANGE)
        time.sleep(3)

    items = [
        Item("IP Adresse",
             sub=lambda: S.get("ip", "-")),
        Item("Hostname",
             sub=lambda: S.get("host", "-")),
        Item("System-Info",
             sub=lambda: get_cpu_temp(),
             action=show_sysinfo),
        Item("Version",
             action=show_version),
        Item("Neustart",
             action=confirm_reboot),
        Item("Ausschalten",
             action=confirm_shutdown),
    ]
    return items

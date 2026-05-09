"""web/shared/system.py — Shell-Calls, Version, IP, safe_run"""
import json
import os
import socket
import subprocess
from web.shared.constants import (
    BASE_DIR
)


_ip_cache: tuple = ("", 0.0)



def get_ip() -> str:
    global _ip_cache
    import time as _t
    if _t.time() - _ip_cache[1] < 30.0 and _ip_cache[0]:
        return _ip_cache[0]
    ip = "?"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
    except Exception:
        try:
            ip = socket.gethostbyname(socket.gethostname())
        except Exception:
            pass
    _ip_cache = (ip, _t.time())
    return ip

def safe_run(cmd):
    try:
        r = subprocess.run(
            cmd,
            shell=True,
            text=True,
            capture_output=True,
            timeout=15
        )
        return {
            "ok": r.returncode == 0,
            "code": r.returncode,
            "stdout": r.stdout,
            "stderr": r.stderr,
            "cmd": cmd,
        }
    except Exception as e:
        return {
            "ok": False,
            "code": -1,
            "stdout": "",
            "stderr": str(e),
            "cmd": cmd,
        }

def get_version():
    try:
        # VERSION liegt im gleichen Verzeichnis wie webui_shared.py (pidrive/)
        _ver_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "VERSION")
        with open(_ver_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return "?"

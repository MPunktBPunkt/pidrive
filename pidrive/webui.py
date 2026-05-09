"""
DEPRECATED SHIM — Rückwärtskompatibilität  v0.10.55
Echte Implementierung: pidrive/web/app.py
Nur für alte Imports. Geplante Entfernung: v0.11.x
"""
"""webui.py — Shim für Rückwärtskompatibilität.
Echte Implementierung in web/app.py
Systemd-Service und alte Imports weiterhin gültig.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from web.app import *  # noqa: F401,F403
from web.app import app  # noqa: F401

# Entry-Point: systemd startet webui.py direkt → Flask hier starten
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)

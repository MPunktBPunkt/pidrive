"""webui.py — Shim für Rückwärtskompatibilität.
Echte Implementierung in web/app.py
Systemd-Service und alte Imports weiterhin gültig.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from web.app import *  # noqa: F401,F403
from web.app import app  # noqa: F401

"""web/app.py — PiDrive WebUI Entry Point
Alias/Proxy für pidrive/webui.py.
Neue Web-Code kann von hier aus importieren.
Die Flask-App läuft weiterhin über webui.py per systemd.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from webui import app  # noqa: F401

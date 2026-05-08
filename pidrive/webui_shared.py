"""webui_shared.py — Shim für Rückwärtskompatibilität.
Echte Implementierung in web/shared.py
"""
from web.shared import *  # noqa: F401,F403
from web.shared import ALLOWED_COMMANDS, PA_ENV  # noqa: F401

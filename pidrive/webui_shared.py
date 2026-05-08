"""
DEPRECATED SHIM — Rückwärtskompatibilität  v0.10.53
Echte Implementierung: pidrive/web/shared.py
Nur für alte Imports. Geplante Entfernung: v0.11.x
"""
"""webui_shared.py — Shim für Rückwärtskompatibilität.
Echte Implementierung in web/shared.py
"""
from web.shared import *  # noqa: F401,F403
from web.shared import ALLOWED_COMMANDS, PA_ENV  # noqa: F401

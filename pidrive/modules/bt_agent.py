"""
DEPRECATED SHIM — Rückwärtskompatibilität  v0.10.52
Echte Implementierung: pidrive/modules/bluetooth/bt_agent.py
Nur für alte Imports. Geplante Entfernung: v0.11.x
"""
from modules.bluetooth.bt_agent import *  # noqa: F401,F403
from modules.bluetooth import bt_agent as _mod  # noqa: F401

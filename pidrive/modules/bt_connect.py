"""
DEPRECATED SHIM — Rückwärtskompatibilität  v0.10.55
Echte Implementierung: pidrive/modules/bluetooth/bt_connect.py
Nur für alte Imports. Geplante Entfernung: v0.11.x
"""
from modules.bluetooth.bt_connect import *  # noqa: F401,F403
from modules.bluetooth import bt_connect as _mod  # noqa: F401

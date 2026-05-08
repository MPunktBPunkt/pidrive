"""
DEPRECATED SHIM — Rückwärtskompatibilität  v0.10.53
Echte Implementierung: pidrive/modules/bluetooth/bluetooth.py
Nur für alte Imports. Geplante Entfernung: v0.11.x
"""
from modules.bluetooth.bluetooth import *  # noqa: F401,F403
from modules.bluetooth import bluetooth as _mod  # noqa: F401

"""
DEPRECATED SHIM — Rückwärtskompatibilität  v0.10.53
Echte Implementierung: pidrive/modules/bluetooth/bt_backup.py
Nur für alte Imports. Geplante Entfernung: v0.11.x
"""
from modules.bluetooth.bt_backup import *  # noqa: F401,F403
from modules.bluetooth import bt_backup as _mod  # noqa: F401

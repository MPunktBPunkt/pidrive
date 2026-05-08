"""
DEPRECATED SHIM — Rückwärtskompatibilität  v0.10.53
Echte Implementierung: pidrive/modules/bluetooth/bt_watcher.py
Nur für alte Imports. Geplante Entfernung: v0.11.x
"""
from modules.bluetooth.bt_watcher import *  # noqa: F401,F403
from modules.bluetooth import bt_watcher as _mod  # noqa: F401

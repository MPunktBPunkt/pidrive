"""
DEPRECATED SHIM — Rückwärtskompatibilität  v0.10.52
Echte Implementierung: pidrive/modules/bluetooth/bt_devices.py
Nur für alte Imports. Geplante Entfernung: v0.11.x
"""
from modules.bluetooth.bt_devices import *  # noqa: F401,F403
from modules.bluetooth import bt_devices as _mod  # noqa: F401

# Rückwärtskompatibilitäts-Shim — echte Implementierung in modules/bluetooth/
from modules.bluetooth.bt_connect import *  # noqa: F401,F403
from modules.bluetooth import bt_connect as _mod  # noqa: F401

# Rückwärtskompatibilitäts-Shim — echte Implementierung in modules/bluetooth/
from modules.bluetooth.bt_watcher import *  # noqa: F401,F403
from modules.bluetooth import bt_watcher as _mod  # noqa: F401

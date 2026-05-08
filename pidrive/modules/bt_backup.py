# Rückwärtskompatibilitäts-Shim — echte Implementierung in modules/bluetooth/
from modules.bluetooth.bt_backup import *  # noqa: F401,F403
from modules.bluetooth import bt_backup as _mod  # noqa: F401

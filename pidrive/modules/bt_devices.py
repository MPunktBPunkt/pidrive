# Rückwärtskompatibilitäts-Shim — echte Implementierung in modules/bluetooth/
from modules.bluetooth.bt_devices import *  # noqa: F401,F403
from modules.bluetooth import bt_devices as _mod  # noqa: F401

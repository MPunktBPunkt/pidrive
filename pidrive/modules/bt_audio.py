# Rückwärtskompatibilitäts-Shim — echte Implementierung in modules/bluetooth/
from modules.bluetooth.bt_audio import *  # noqa: F401,F403
from modules.bluetooth import bt_audio as _mod  # noqa: F401

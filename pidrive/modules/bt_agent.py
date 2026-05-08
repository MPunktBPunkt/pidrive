# Rückwärtskompatibilitäts-Shim — echte Implementierung in modules/bluetooth/
from modules.bluetooth.bt_agent import *  # noqa: F401,F403
from modules.bluetooth import bt_agent as _mod  # noqa: F401

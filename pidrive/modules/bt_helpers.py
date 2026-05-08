# Rückwärtskompatibilitäts-Shim — echte Implementierung in modules/bluetooth/
from modules.bluetooth.bt_helpers import *  # noqa: F401,F403
from modules.bluetooth import bt_helpers as _mod  # noqa: F401

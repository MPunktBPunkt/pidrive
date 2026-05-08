# Rückwärtskompatibilitäts-Shim — echte Implementierung in modules/bluetooth/
from modules.bluetooth.bluetooth import *  # noqa: F401,F403
from modules.bluetooth import bluetooth as _mod  # noqa: F401

# Rückwärtskompatibilitäts-Shim — echte Implementierung in modules/radio/
from modules.radio.dab import *  # noqa: F401,F403
from modules.radio import dab as _mod  # noqa: F401

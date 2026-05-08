# Rückwärtskompatibilitäts-Shim — echte Implementierung in modules/radio/
from modules.radio.dab_scan import *  # noqa: F401,F403
from modules.radio import dab_scan as _mod  # noqa: F401

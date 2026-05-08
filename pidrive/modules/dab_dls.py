# Rückwärtskompatibilitäts-Shim — echte Implementierung in modules/radio/
from modules.radio.dab_dls import *  # noqa: F401,F403
from modules.radio import dab_dls as _mod  # noqa: F401

# Rückwärtskompatibilitäts-Shim — echte Implementierung in modules/radio/
from modules.radio.dab_play import *  # noqa: F401,F403
from modules.radio import dab_play as _mod  # noqa: F401

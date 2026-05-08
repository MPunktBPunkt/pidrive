# Rückwärtskompatibilitäts-Shim — echte Implementierung in modules/radio/
from modules.radio.spectrum import *  # noqa: F401,F403
from modules.radio import spectrum as _mod  # noqa: F401

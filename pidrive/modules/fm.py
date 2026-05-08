# Rückwärtskompatibilitäts-Shim — echte Implementierung in modules/radio/
from modules.radio.fm import *  # noqa: F401,F403
from modules.radio import fm as _mod  # noqa: F401

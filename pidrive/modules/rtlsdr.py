# Rückwärtskompatibilitäts-Shim — echte Implementierung in modules/radio/
from modules.radio.rtlsdr import *  # noqa: F401,F403
from modules.radio import rtlsdr as _mod  # noqa: F401

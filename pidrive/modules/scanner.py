# Rückwärtskompatibilitäts-Shim — echte Implementierung in modules/radio/
from modules.radio.scanner import *  # noqa: F401,F403
from modules.radio import scanner as _mod  # noqa: F401

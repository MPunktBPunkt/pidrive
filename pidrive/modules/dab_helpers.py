# Rückwärtskompatibilitäts-Shim — echte Implementierung in modules/radio/
from modules.radio.dab_helpers import *  # noqa: F401,F403
from modules.radio import dab_helpers as _mod  # noqa: F401

"""
DEPRECATED SHIM — Rückwärtskompatibilität  v0.10.52
Echte Implementierung: pidrive/modules/radio/rtlsdr.py
Nur für alte Imports. Geplante Entfernung: v0.11.x
"""
from modules.radio.rtlsdr import *  # noqa: F401,F403
from modules.radio import rtlsdr as _mod  # noqa: F401

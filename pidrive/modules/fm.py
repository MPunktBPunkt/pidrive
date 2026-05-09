"""
DEPRECATED SHIM — Rückwärtskompatibilität  v0.10.54
Echte Implementierung: pidrive/modules/radio/fm.py
Nur für alte Imports. Geplante Entfernung: v0.11.x
"""
from modules.radio.fm import *  # noqa: F401,F403
from modules.radio import fm as _mod  # noqa: F401

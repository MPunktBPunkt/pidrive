"""modules/dab.py — Compat-Shim → modules.radio.dab"""
from modules.radio.dab import *  # noqa
from modules.radio import dab as _mod
import sys
sys.modules[__name__] = sys.modules[f"modules.radio.dab"]

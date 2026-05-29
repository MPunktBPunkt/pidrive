"""modules/fm.py — Compat-Shim → modules.radio.fm"""
from modules.radio.fm import *  # noqa
from modules.radio import fm as _mod
import sys
sys.modules[__name__] = sys.modules[f"modules.radio.fm"]

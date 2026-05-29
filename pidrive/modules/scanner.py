"""modules/scanner.py — Compat-Shim → modules.radio.scanner"""
from modules.radio.scanner import *  # noqa
from modules.radio import scanner as _mod
import sys
sys.modules[__name__] = sys.modules[f"modules.radio.scanner"]

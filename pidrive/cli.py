#!/usr/bin/env python3
"""
DEPRECATED SHIM — Rückwärtskompatibilität
Echte Implementierung: pidrive/cli/cli.py
Dieses Shim wird entfernt sobald alle Imports umgestellt sind.
Geplant: v0.11.x
"""
import sys, os
_BASE = os.path.dirname(os.path.abspath(__file__))
if _BASE not in sys.path: sys.path.insert(0, _BASE)
from cli.cli import main
if __name__ == "__main__": main()

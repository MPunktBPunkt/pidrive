#!/usr/bin/env python3
"""
avrcp_trigger.py — Entry-Shim (v0.11.74)
Echte Implementierung: integration/avrcp_trigger.py

Dieser Shim existiert für Rückwärtskompatibilität.
Der systemd-Service pidrive_avrcp.service startet integration/avrcp_trigger.py direkt.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from integration.avrcp_trigger import *  # noqa
if __name__ == "__main__":
    from integration import avrcp_trigger as _at
    _at.main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""webui.py — systemd/Entry-Kompatibilität → web/app.py

Alte Units und manuelle Starts nutzen noch diesen Pfad. Die echte App liegt in
web/app.py; pidrive_web.service kann beides starten.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from web.app import app  # noqa: E402

if __name__ == "__main__":
    # threaded: /api/audio/listen darf Polling nicht blockieren
    app.run(host="0.0.0.0", port=8080, debug=False, threaded=True)

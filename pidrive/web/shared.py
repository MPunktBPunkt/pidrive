"""web/shared.py — Alias für webui_shared.py
Neue Web-Module können von hier aus importieren.
"""
from webui_shared import *  # noqa: F401,F403
from webui_shared import ALLOWED_COMMANDS, PA_ENV  # noqa: F401

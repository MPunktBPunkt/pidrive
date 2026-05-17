"""
DEPRECATED SHIM — Rückwärtskompatibilität v0.11.8
Echte Implementierung: pidrive/trigger/trigger_dispatcher.py
"""
from trigger.trigger_dispatcher import *  # noqa: F401,F403
# Private Symbole explizit re-exportieren (import * überspringt _ Präfix)
from trigger.trigger_dispatcher import (
    _set_guards, _execute_node,  # noqa: F401
    handle_trigger, _fm_manual, _debounced,  # noqa: F401
)
try:
    from trigger.td_nav import _set_nav_guards  # noqa: F401
except ImportError:
    pass

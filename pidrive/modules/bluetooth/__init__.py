"""modules/bluetooth/ — Bluetooth-Subsystem
Enthält: bluetooth, bt_agent, bt_audio, bt_backup,
         bt_connect, bt_devices, bt_helpers, bt_watcher

Re-exportiert alle öffentlichen Funktionen aus bluetooth.py (Facade).
"""
# Importiere alle öffentlichen Symbole aus der Facade-Datei
# bluetooth.py im selben Verzeichnis re-exportiert alles aus den bt_*.py Dateien
from modules.bluetooth.bluetooth import *  # noqa: F401,F403

# Explizite Exporte für bessere Erkennbarkeit
from modules.bluetooth.bt_agent import (  # noqa: F401
    start_agent_session, stop_agent_session,
    start_agent_health_thread, agent_healthcheck,
    read_agent_state, _ensure_agent,
)
from modules.bluetooth.bt_watcher import (  # noqa: F401
    start_auto_reconnect,
)
from modules.bluetooth.bt_connect import (  # noqa: F401
    reconnect_known_devices,
)

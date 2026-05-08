"""modules/bluetooth — Bluetooth-Subsystem
Proxy-Modul: importiert alle BT-Komponenten aus der flachen modules/-Ebene.
Neue Importe können modules.bluetooth statt modules.bt_* nutzen.
"""
from modules.bluetooth_impl import (  # noqa: F401,F403
    bluetooth,
    bt_agent,
    bt_audio,
    bt_backup,
    bt_connect,
    bt_devices,
    bt_helpers,
    bt_watcher,
)

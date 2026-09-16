"""BF-J: Agent-Lebendigkeit nur bei frischem ts."""
from __future__ import annotations

import time


def test_agent_healthcheck_requires_fresh_ts(monkeypatch):
    from modules.bluetooth import bt_agent as ba

    monkeypatch.setattr(ba, "read_agent_state", lambda: {
        "kind": "dbus", "ready": True, "ts": time.time(),
    })
    assert ba.agent_healthcheck() is True

    monkeypatch.setattr(ba, "read_agent_state", lambda: {
        "kind": "dbus", "ready": True, "ts": time.time() - 60,
    })
    assert ba.agent_healthcheck() is False

    monkeypatch.setattr(ba, "read_agent_state", lambda: {
        "kind": "dbus", "ready": False, "ts": time.time(),
    })
    assert ba.agent_healthcheck() is False

    monkeypatch.setattr(ba, "read_agent_state", lambda: {
        "kind": "bluetoothctl", "ready": True, "ts": time.time(),
    })
    assert ba.agent_healthcheck() is False

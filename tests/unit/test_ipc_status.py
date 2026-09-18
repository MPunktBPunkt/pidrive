"""ipc.write_status — Vertrag für WebUI/CLI (W2)."""
from __future__ import annotations

import json
from pathlib import Path

import ipc


REQUIRED_KEYS = {
    "wifi",
    "bt",
    "bt_on",
    "processes",
    "degraded_imports",
    "scanner",
    "usb",
    "control_context",
    "dab_sync_seen",
    "volume",
    "ts",
}


def test_write_status_exports_contract_fields(tmp_path, monkeypatch):
    status_file = tmp_path / "status.json"
    monkeypatch.setattr(ipc, "STATUS_FILE", str(status_file))

    S = {
        "wifi": True,
        "wifi_ssid": "TestNet",
        "bt": True,
        "bt_on": True,
        "processes": ["1234 mpv"],
        "dab_sync_seen": True,
        "radio_type": "SCANNER",
        "scanner": {"active": True, "band": "pmr446", "freq": 446.00625},
        "control_context": "scanner",
    }
    settings = {"volume": 42, "audio_output": "auto"}
    ipc.write_status(S, settings)

    data = json.loads(status_file.read_text())
    missing = REQUIRED_KEYS - set(data)
    assert not missing, f"fehlende Statusfelder: {sorted(missing)}"
    assert data["processes"] == ["1234 mpv"]
    assert data["bt_on"] is True
    assert data["volume"] == 42
    assert isinstance(data["scanner"], dict)
    assert data["scanner"].get("active") is True
    assert data["scanner"].get("band") == "pmr446"
    assert isinstance(data["degraded_imports"], list)


def test_scanner_status_from_radio_type(monkeypatch, tmp_path):
    monkeypatch.setattr(ipc, "STATUS_FILE", str(tmp_path / "s.json"))
    ipc.write_status({"radio_type": "SCANNER", "scanner_band": "cb"}, {})
    data = json.loads(Path(ipc.STATUS_FILE).read_text())
    assert data["scanner"]["active"] is True
    assert data["scanner"]["band"] == "cb"

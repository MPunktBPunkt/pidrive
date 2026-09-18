"""U1/U2: usb_gadget route + usb status IPC."""
from __future__ import annotations

import json
from pathlib import Path

import ipc
from modules.audio import decide_audio_route


def test_decide_usb_gadget_skips_pa(monkeypatch):
    monkeypatch.setattr("modules.audio._pa_ok", lambda: False)
    d = decide_audio_route({"audio_output": "usb_gadget"}, source="test")
    assert d["requested"] == "usb_gadget"
    assert d["effective"] == "usb_gadget"
    assert d["reason"] == "usb_gadget_requested"
    assert d["sink"] == ""
    assert d["pa_ok"] is True


def test_write_status_includes_usb(tmp_path, monkeypatch):
    status_file = tmp_path / "status.json"
    usb_file = tmp_path / "usb.json"
    monkeypatch.setattr(ipc, "STATUS_FILE", str(status_file))
    monkeypatch.setattr(ipc, "USB_STATUS_FILE", str(usb_file))
    usb_file.write_text(json.dumps({
        "online": True,
        "http_ok": True,
        "serial_present": True,
        "fw": "0.4.4-dev",
        "otg_up": True,
        "pump_up": True,
        "uart_up": True,
        "msc_ready": True,
        "esp_host": "192.168.178.89",
        "port": "/dev/ttyACM0",
        "ts": 9999999999,
    }))
    ipc.write_status({"wifi": False, "bt": False}, {"volume": 50, "audio_output": "usb_gadget"})
    data = json.loads(status_file.read_text())
    assert "usb" in data
    assert data["usb"]["online"] is True
    assert data["usb"]["fw"] == "0.4.4-dev"
    assert data["usb"]["otg_up"] is True
    assert data["audio_out"] == "usb_gadget"


def test_usb_status_stale_marks_offline(tmp_path, monkeypatch):
    monkeypatch.setattr(ipc, "USB_STATUS_FILE", str(tmp_path / "usb.json"))
    (tmp_path / "usb.json").write_text(json.dumps({
        "online": True,
        "fw": "x",
        "ts": 1,
    }))
    usb = ipc._usb_status()
    assert usb["online"] is False
    assert usb["age_s"] is not None and usb["age_s"] > 15

"""BT Reconnect-Hygiene (Feldtest 2026-09-16)."""
from __future__ import annotations


def test_info_has_rf_hint():
    from modules.bluetooth.bt_helpers import _info_has_rf_hint
    assert _info_has_rf_hint("Name: BMW\nConnected: yes\n") is True
    assert _info_has_rf_hint("Name: BMW\nRSSI: -60\n") is True
    assert _info_has_rf_hint("Name: HD 4.40BT\nPaired: yes\nTrusted: yes\n") is False


def test_unreachable_errors():
    from modules.bluetooth.bt_helpers import _is_unreachable_bt_error
    assert _is_unreachable_bt_error("avdtp Host is down (112)") is True
    assert _is_unreachable_bt_error("br-connection-page-timeout") is True
    assert _is_unreachable_bt_error("Connection successful") is False


def test_classify_connect_failure():
    from modules.bluetooth.bt_connect import _classify_connect_failure
    assert _classify_connect_failure("Host is down (112)") == "host_down"
    assert _classify_connect_failure("Page Timeout") == "page_timeout"
    assert _classify_connect_failure("Device or resource busy") == "busy"


def test_score_prefers_bmw_over_headphones():
    from modules.bluetooth.bt_connect import _score_reconnect_device
    bmw = {
        "mac": "D4:36:39:CF:E1:B5",
        "name": "BMW 38304",
        "paired": True,
        "trusted": True,
        "device_type": "avrcp_controller",
        "audio_candidate": True,
    }
    hd = {
        "mac": "AA:BB:CC:DD:EE:FF",
        "name": "HD 4.40BT",
        "paired": True,
        "trusted": True,
        "device_type": "headphones",
        "audio_candidate": True,
    }
    assert _score_reconnect_device(bmw, "") > _score_reconnect_device(hd, "")
    # bt_last headphones still loses to BMW when comparing raw scores without last match
    assert _score_reconnect_device(bmw, hd["mac"]) > _score_reconnect_device(hd, hd["mac"])


def test_decide_confirm_still_always():
    from modules.bluetooth.bt_agent_dbus import decide_confirm
    assert decide_confirm("always", 0, False)[0] is True

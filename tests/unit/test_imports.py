"""Import-Smoke: Module laden, die install.sh / Core brauchen."""
from __future__ import annotations

import importlib

import pytest

CRITICAL = [
    "log",
    "ipc",
    "settings",
    "status",
    "modules.source_state",
    "modules.audio",
    "modules.wifi",
    "modules.system",
    "modules.webradio",
    "modules.favorites",
    "modules.radio",
    "modules.radio.dab",
    "modules.radio.fm",
    "modules.radio.scanner",
    "modules.radio.rtlsdr",
    "modules.radio.spectrum",
    "modules.radio.dab_scan",
    "modules.bluetooth.bt_connect",
    "modules.bluetooth.bt_helpers",
    "modules.bluetooth.bt_audio",
    "modules.bluetooth.bt_watcher",
    "trigger.td_hardware",
    "trigger.td_nav",
    "trigger.td_radio",
    "trigger.td_scanner",
    "trigger.td_system",
    "trigger.trigger_dispatcher",
    "menu.menu_model",
    "menu.menu_builder",
    "menu.menu_state",
    "menu.menu_golden",
    "menu.idrive_sim",
    "cli.cli",
    "web.webui_check",
    "web.shared",
    "web.app",
    "main_core",
]


@pytest.mark.parametrize("modname", CRITICAL)
def test_import_critical(modname):
    importlib.import_module(modname)
